#!/usr/bin/env python3
"""Dispatch one frozen review request to one backend at a time.

The router is intentionally small and synchronous.  It resolves an ordered
policy, invokes exactly one adapter, and only retries an explicitly
transport-unavailable backend.  Workflow state, writer leases, external
authorization UI, finding closure, and repair loops remain outside this file.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime as _datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


AGENTS_DIR = Path(__file__).resolve().parent
RESULT_SCHEMA = "dd-review-result/1"
REQUEST_SCHEMA = "dd-review-request/1"
CONFIG_SCHEMA = "dd-review-backends/1"
POLICY_SCHEMA = "dd-routing-policy/1"
MCP_READONLY_MODE = "snapshot-send-only"
ALLOWED_BACKEND_TYPES = {"mcp", "cli", "native"}
ALLOWED_EXECUTIONS = {"external", "native-agent"}
FALLBACK_CATEGORIES = {
    "backend_unavailable",
    "executable_missing",
    "endpoint_unavailable",
    "capability_unavailable",
    "temporary_backend_failure",
}
KNOWN_FAILURE_CATEGORIES = FALLBACK_CATEGORIES | {
    "all_backends_unavailable",
    "authorization_violation",
    "backend_execution_failed",
    "baseline_mismatch",
    "configuration_invalid",
    "evidence_mismatch",
    "recursion_violation",
    "review_incomplete",
    "schema_invalid",
    "security_policy_violation",
    "readonly_violation",
    "verification_failed",
}
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FORBIDDEN_MODEL_BINDING_KEYS = {
    "adapter",
    "backend",
    "backends",
    "command",
    "endpoint",
    "fallback",
    "fallback_chain",
    "mcp",
    "routing",
    "routing_policy",
    "transport",
}


class RouterFailure(Exception):
    """A fail-closed router failure with a stable machine category."""

    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


class BackendUnavailable(RouterFailure):
    """A failure for which the policy explicitly permits another candidate."""


class TerminalReviewFailure(RouterFailure):
    """A failure that must not be silently replaced by another reviewer."""


class ConfigurationFailure(RouterFailure):
    """Invalid registry or policy configuration."""


def _strip_comment(raw: str) -> str:
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
    return raw.rstrip()


def _yaml_lines(text: str) -> List[Tuple[int, str, int]]:
    lines: List[Tuple[int, str, int]] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip(" "))]:
            raise ConfigurationFailure("configuration_invalid", f"tabs are not supported at line {line_number}")
        content = _strip_comment(raw)
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        lines.append((indent, content.strip(), line_number))
    return lines


def _split_inline(value: str) -> List[str]:
    result: List[str] = []
    start = 0
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == "," and quote is None:
            result.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        result.append(tail)
    return result


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_scalar(item) for item in _split_inline(inner)]
    if value.startswith("{") and value.endswith("}"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigurationFailure("configuration_invalid", f"invalid inline object: {exc}") from exc
        return parsed
    if value.startswith('"') or value.startswith("'"):
        try:
            return json.loads(value) if value.startswith('"') else ast.literal_eval(value)
        except (ValueError, SyntaxError, json.JSONDecodeError) as exc:
            raise ConfigurationFailure("configuration_invalid", f"invalid quoted scalar: {value}") from exc
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    return value


def _mapping_item(text: str) -> Optional[Tuple[str, str]]:
    if text.startswith("-"):
        return None
    match = re.match(r"^([^:]+):(.*)$", text)
    if not match:
        return None
    key, value = match.group(1).strip(), match.group(2).strip()
    if not key:
        return None
    return key, value


def _parse_yaml_block(lines: List[Tuple[int, str, int]], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines) or lines[index][0] < indent:
        return {}, index
    if lines[index][0] != indent:
        raise ConfigurationFailure("configuration_invalid", f"unexpected indentation at line {lines[index][2]}")

    is_list = lines[index][1] == "-" or lines[index][1].startswith("- ")
    container: Any = [] if is_list else {}
    while index < len(lines):
        current_indent, text, line_number = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent:
            raise ConfigurationFailure("configuration_invalid", f"unexpected indentation at line {line_number}")

        if is_list:
            if text != "-" and not text.startswith("- "):
                raise ConfigurationFailure("configuration_invalid", f"mixed list/mapping at line {line_number}")
            body = text[1:].strip()
            index += 1
            if not body:
                if index < len(lines) and lines[index][0] > indent:
                    item, index = _parse_yaml_block(lines, index, lines[index][0])
                else:
                    item = None
            else:
                mapping = _mapping_item(body)
                if mapping is None:
                    item = _parse_scalar(body)
                else:
                    key, value = mapping
                    item = {}
                    if value:
                        item[key] = _parse_scalar(value)
                    elif index < len(lines) and lines[index][0] > indent:
                        item[key], index = _parse_yaml_block(lines, index, lines[index][0])
                    else:
                        item[key] = {}
                    if index < len(lines) and lines[index][0] > indent:
                        extra, index = _parse_yaml_block(lines, index, lines[index][0])
                        if not isinstance(extra, dict):
                            raise ConfigurationFailure("configuration_invalid", f"list mapping expected at line {line_number}")
                        item.update(extra)
            container.append(item)
            continue

        if text.startswith("-"):
            raise ConfigurationFailure("configuration_invalid", f"mapping/list mismatch at line {line_number}")
        mapping = _mapping_item(text)
        if mapping is None:
            raise ConfigurationFailure("configuration_invalid", f"expected key/value at line {line_number}")
        key, value = mapping
        index += 1
        if value:
            container[key] = _parse_scalar(value)
        elif index < len(lines) and lines[index][0] > indent:
            container[key], index = _parse_yaml_block(lines, index, lines[index][0])
        else:
            container[key] = {}
    return container, index


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load the small YAML subset used by canonical router configuration.

    PyYAML is intentionally not a runtime dependency of this repository.  The
    parser accepts mappings, scalar lists, and nested mappings, which is the
    complete shape of the two checked-in router configs.  JSON input is also
    accepted because JSON is a YAML subset.
    """

    try:
        text = path.read_text()
    except OSError as exc:
        raise ConfigurationFailure("configuration_invalid", f"cannot read {path}: {exc}") from exc
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ConfigurationFailure("configuration_invalid", f"invalid JSON/YAML {path}: {exc}") from exc
    else:
        lines = _yaml_lines(text)
        value, index = _parse_yaml_block(lines, 0, lines[0][0] if lines else 0)
        if index != len(lines):
            raise ConfigurationFailure("configuration_invalid", f"unparsed configuration at line {lines[index][2]}")
    if not isinstance(value, dict):
        raise ConfigurationFailure("configuration_invalid", f"top level of {path} must be a mapping")
    return value


def validate_model_bindings_isolation(path: Path) -> List[str]:
    """Reject transport/routing keys from the model binding source."""

    errors: List[str] = []
    try:
        lines = _yaml_lines(path.read_text())
    except (OSError, RouterFailure) as exc:
        return [f"model-bindings unreadable: {path}: {exc}"]
    for _, text, line_number in lines:
        if text.startswith("-") or ":" not in text:
            continue
        key = text.split(":", 1)[0].strip()
        if key in FORBIDDEN_MODEL_BINDING_KEYS:
            errors.append(f"model-bindings line {line_number}: external routing key '{key}' is not allowed")
    return errors


def validate_registry_policy(registry: Dict[str, Any], policy: Dict[str, Any]) -> List[str]:
    """Return all deterministic registry/policy contract violations."""

    errors: List[str] = []
    if registry.get("schema") != CONFIG_SCHEMA:
        errors.append(f"registry schema must be {CONFIG_SCHEMA}")
    if registry.get("result_schema") != RESULT_SCHEMA:
        errors.append(f"registry result_schema must be {RESULT_SCHEMA}")
    if policy.get("schema") != POLICY_SCHEMA:
        errors.append(f"policy schema must be {POLICY_SCHEMA}")
    if policy.get("max_hops") != 1:
        errors.append("v1 policy max_hops must be exactly 1")

    backends = registry.get("backends")
    if not isinstance(backends, dict) or not backends:
        errors.append("registry backends must be a non-empty mapping")
        backends = {}
    for backend_id, spec in backends.items():
        path = f"backends.{backend_id}"
        if not isinstance(backend_id, str) or not ID_RE.fullmatch(backend_id):
            errors.append(f"{path}: invalid backend id")
        if not isinstance(spec, dict):
            errors.append(f"{path}: expected mapping")
            continue
        backend_type = spec.get("type")
        execution = spec.get("execution")
        if backend_type not in ALLOWED_BACKEND_TYPES:
            errors.append(f"{path}.type: unsupported backend type {backend_type!r}")
        if execution not in ALLOWED_EXECUTIONS:
            errors.append(f"{path}.execution: unsupported execution {execution!r}")
        if backend_type == "mcp" and execution != "external":
            errors.append(f"{path}: MCP must be an external single-request backend")
        if backend_type == "native" and execution != "native-agent":
            errors.append(f"{path}: native backend must use native-agent execution")
        if backend_type == "native" and (not isinstance(spec.get("host"), str) or not spec.get("host")):
            errors.append(f"{path}.host: required for native backend")
        if not isinstance(spec.get("router_selectable", True), bool):
            errors.append(f"{path}.router_selectable: boolean required when present")
        if backend_type == "native" and spec.get("host") == "codex":
            if spec.get("native_guard") != "codex-route-guard":
                errors.append(f"{path}.native_guard: codex native backend must use codex-route-guard")
            if spec.get("router_selectable") is not False:
                errors.append(f"{path}.router_selectable: codex native backend must be delegated to host-native dispatch")
        if not isinstance(spec.get("executable"), str) or not spec.get("executable"):
            errors.append(f"{path}.executable: required")
        command = spec.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
            errors.append(f"{path}.command: non-empty string list required")
        forbid_args = spec.get("forbid_args", [])
        if not isinstance(forbid_args, list) or not all(isinstance(arg, str) for arg in forbid_args):
            errors.append(f"{path}.forbid_args: string list required")
        elif isinstance(command, list) and any(arg in forbid_args for arg in command):
            errors.append(f"{path}: command contains a forbidden argument")
        capabilities = spec.get("capabilities")
        if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
            errors.append(f"{path}.capabilities: string list required")
        if spec.get("readonly_required") is not True:
            errors.append(f"{path}.readonly_required: must be true")
        if not isinstance(spec.get("readonly_mode"), str) or not spec.get("readonly_mode"):
            errors.append(f"{path}.readonly_mode: required")
        for exit_key in ("availability_exit_codes", "transient_exit_codes"):
            exit_codes = spec.get(exit_key)
            if not isinstance(exit_codes, list) or not all(
                type(code) is int and 1 <= code <= 255 for code in exit_codes
            ):
                errors.append(f"{path}.{exit_key}: integer exit-code list (1..255) required")
        availability_codes = spec.get("availability_exit_codes")
        transient_codes = spec.get("transient_exit_codes")
        if (
            isinstance(availability_codes, list)
            and isinstance(transient_codes, list)
            and set(availability_codes) & set(transient_codes)
        ):
            errors.append(f"{path}: availability and transient exit codes must not overlap")
        if spec.get("result_schema") != RESULT_SCHEMA:
            errors.append(f"{path}.result_schema must be {RESULT_SCHEMA}")
        if any(key in spec for key in ("model", "profile", "reasoning_effort")):
            errors.append(f"{path}: model binding fields belong in model-bindings.yaml")
        if backend_type == "mcp" and spec.get("readonly_mode") != MCP_READONLY_MODE:
            errors.append(f"{path}: MCP readonly_mode must be {MCP_READONLY_MODE}")

    roles = policy.get("roles")
    if not isinstance(roles, dict) or not roles:
        errors.append("policy roles must be a non-empty mapping")
        roles = {}
    for role, role_spec in roles.items():
        path = f"roles.{role}"
        if not isinstance(role_spec, dict):
            errors.append(f"{path}: expected mapping")
            continue
        if not isinstance(role_spec.get("capability"), str) or not role_spec.get("capability"):
            errors.append(f"{path}.capability: required")
        if role_spec.get("max_hops") != 1:
            errors.append(f"{path}.max_hops: v1 must be exactly 1")
        candidates = role_spec.get("backends")
        if not isinstance(candidates, list) or not candidates or not all(isinstance(item, str) for item in candidates):
            errors.append(f"{path}.backends: non-empty string list required")
        else:
            missing = [item for item in candidates if item != "host-native" and item not in backends]
            if missing:
                errors.append(f"{path}.backends: unknown backend reference(s) {missing}")
        role_fallback = role_spec.get("fallback_on")
        if not isinstance(role_fallback, list) or not all(isinstance(item, str) for item in role_fallback):
            errors.append(f"{path}.fallback_on: string list required")
        elif set(role_fallback) - FALLBACK_CATEGORIES:
            errors.append(f"{path}.fallback_on: unknown categories {sorted(set(role_fallback) - FALLBACK_CATEGORIES)}")

    host_native = policy.get("host_native")
    if not isinstance(host_native, dict) or not host_native:
        errors.append("policy host_native must be a non-empty mapping")
    else:
        for host, backend_id in host_native.items():
            if backend_id not in backends:
                errors.append(f"host_native.{host}: unknown backend reference {backend_id!r}")
            elif isinstance(backends.get(backend_id), dict) and backends[backend_id].get("execution") != "native-agent":
                errors.append(f"host_native.{host}: target must be native-agent")
    return errors


def load_configuration(
    registry_path: Path,
    policy_path: Path,
    model_bindings_path: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    registry = load_yaml(registry_path)
    policy = load_yaml(policy_path)
    errors = validate_registry_policy(registry, policy)
    if model_bindings_path is not None:
        errors.extend(validate_model_bindings_isolation(model_bindings_path))
    if errors:
        raise ConfigurationFailure("configuration_invalid", "; ".join(errors))
    return registry, policy


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat()


def _target(request: Dict[str, Any]) -> Dict[str, Any]:
    raw_scope = request.get("scope", [])
    return {
        "base_sha": request.get("base_sha"),
        "head_sha": request.get("head_sha"),
        "scope": list(raw_scope) if isinstance(raw_scope, list) else [],
    }


def _routing_metadata(
    request: Dict[str, Any],
    policy: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    selected_backend: Optional[str],
    readonly_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = request.get("context", {})
    metadata = {
        "role": request.get("role"),
        "selected_backend": selected_backend,
        "attempted": copy.deepcopy(attempts),
        "max_hops": policy.get("max_hops"),
        "hop_count": context.get("hop_count", 0),
        "dispatch_chain": list(context.get("dispatch_chain", [])),
        "dispatch_boundary": "single-backend",
        "router_authority": "host-workflow",
    }
    if readonly_evidence is not None:
        metadata["readonly_evidence"] = copy.deepcopy(readonly_evidence)
    return metadata


def _blocked_result(
    request: Dict[str, Any],
    policy: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    category: str,
    detail: str,
    selected_backend: Optional[str] = None,
    started: bool = False,
) -> Dict[str, Any]:
    completed_at = _utc_now()
    return {
        "schema": RESULT_SCHEMA,
        "backend": selected_backend or "router",
        "reviewer": None,
        "target": _target(request),
        "baseline": _target(request),
        "status": "BLOCKED",
        "verdict": "BLOCKED",
        "reviewed": [],
        "unreadable": list(request.get("scope", [])),
        "findings": [],
        "evidence": [{"category": category, "detail": detail}],
        "started_at": completed_at if started else None,
        "completed_at": completed_at,
        "lifecycle": {"started": started, "completed": False},
        "failure_category": category,
        "fallback_eligible": False,
        "readonly_confirmation": {"confirmed": False, "evidence": None},
        "routing": _routing_metadata(request, policy, attempts, selected_backend),
    }


def _validate_request_shape(request: Dict[str, Any]) -> None:
    if request.get("schema") != REQUEST_SCHEMA:
        raise TerminalReviewFailure("schema_invalid", f"request schema must be {REQUEST_SCHEMA}")
    if "native_guard" in request:
        raise TerminalReviewFailure(
            "security_policy_violation",
            "request.native_guard is runtime-owned and cannot be supplied by the caller",
        )
    for key in ("role", "host", "repo", "base_sha", "head_sha"):
        if not isinstance(request.get(key), str) or not request[key]:
            raise TerminalReviewFailure("schema_invalid", f"request.{key} is required")
    for key in ("base_sha", "head_sha"):
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", request[key]):
            raise TerminalReviewFailure("schema_invalid", f"request.{key} must be a commit SHA")
    scope = request.get("scope")
    if not isinstance(scope, list) or not scope or not all(isinstance(item, str) and item for item in scope):
        raise TerminalReviewFailure("schema_invalid", "request.scope must be a non-empty string list")
    if len(set(scope)) != len(scope):
        raise TerminalReviewFailure("schema_invalid", "request.scope must not contain duplicates")
    for item in scope:
        path = Path(item)
        if path.is_absolute() or ".." in path.parts or item in {"", "."}:
            raise TerminalReviewFailure("security_policy_violation", f"scope escapes repository: {item!r}")
    verification = request.get("verification")
    if not isinstance(verification, list) or not verification:
        raise TerminalReviewFailure("verification_failed", "deterministic verification evidence is required")
    for item in verification:
        if not isinstance(item, dict) or item.get("status") not in {"passed", "PASS", "success", "SUCCESS"}:
            raise TerminalReviewFailure("verification_failed", "all deterministic verification entries must pass")
        if not item.get("evidence"):
            raise TerminalReviewFailure("verification_failed", "verification entries require evidence")
    context = request.get("context")
    if not isinstance(context, dict):
        raise TerminalReviewFailure("schema_invalid", "request.context must be a mapping")
    hop_count = context.get("hop_count", 0)
    chain = context.get("dispatch_chain", [])
    if not isinstance(hop_count, int) or hop_count < 0:
        raise TerminalReviewFailure("schema_invalid", "context.hop_count must be a non-negative integer")
    if not isinstance(chain, list) or not all(isinstance(item, str) for item in chain):
        raise TerminalReviewFailure("schema_invalid", "context.dispatch_chain must be a string list")


def _git(repo: Path, args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TerminalReviewFailure("evidence_mismatch", f"git evidence command failed: git {' '.join(args)}")
    return result.stdout.strip()


def _verify_frozen_baseline(request: Dict[str, Any]) -> None:
    repo = Path(request["repo"]).expanduser().resolve()
    if not repo.is_dir():
        raise TerminalReviewFailure("evidence_mismatch", f"repository is not a directory: {repo}")
    current_head = _git(repo, ["rev-parse", "HEAD"])
    if current_head != request["head_sha"]:
        raise TerminalReviewFailure("baseline_mismatch", "repository HEAD differs from requested head_sha")
    dirty = _git(repo, ["status", "--porcelain=v1", "--untracked-files=all"])
    if dirty:
        raise TerminalReviewFailure("baseline_mismatch", "review worktree has unrecorded changes")
    for sha in (request["base_sha"], request["head_sha"]):
        _git(repo, ["cat-file", "-e", f"{sha}^{{commit}}"])
    for item in request["scope"]:
        _git(repo, ["ls-files", "--error-unmatch", "--", item])
    request["repo"] = str(repo)


def _external_authorized(request: Dict[str, Any]) -> bool:
    authorization = request.get("external_review")
    if not isinstance(authorization, dict) or authorization.get("authorization") != "approved":
        return False
    approved_scope = authorization.get("scope")
    return isinstance(approved_scope, list) and set(request["scope"]).issubset(set(approved_scope))


def _readonly_evidence_valid(
    request: Dict[str, Any], backend_id: str, backend: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    proofs = request.get("readonly_evidence")
    if not isinstance(proofs, list):
        return None
    expected_mode = backend.get("readonly_mode")
    for proof in proofs:
        if not isinstance(proof, dict):
            continue
        source = proof.get("source")
        if (
            proof.get("backend") == backend_id
            and proof.get("mode") == expected_mode
            and proof.get("level") == "L6"
            and proof.get("confirmed") is True
            and isinstance(source, str)
            and bool(source)
        ):
            return copy.deepcopy(proof)
    return None


def _backend_for_candidate(
    candidate: str,
    host: str,
    policy: Dict[str, Any],
    backends: Dict[str, Any],
) -> Optional[str]:
    if candidate == "host-native":
        host_native = policy.get("host_native", {})
        return host_native.get(host) if isinstance(host_native, dict) else None
    return candidate if candidate in backends else None


def _check_backend_eligibility(
    request: Dict[str, Any],
    role_policy: Dict[str, Any],
    backend_id: str,
    backend: Dict[str, Any],
) -> Dict[str, Any]:
    required_capability = role_policy["capability"]
    capabilities = backend.get("capabilities", [])
    if required_capability not in capabilities:
        raise BackendUnavailable("capability_unavailable", f"{backend_id} lacks {required_capability}")
    if backend.get("execution") == "external" and not _external_authorized(request):
        raise TerminalReviewFailure("authorization_violation", f"external backend {backend_id} is not authorized for this scope")
    if backend.get("execution") == "native-agent":
        if backend.get("router_selectable", True) is False:
            raise BackendUnavailable(
                "capability_unavailable",
                f"{backend_id} requires a verified host-native dispatch handoff",
            )
        expected_host = backend.get("host")
        if expected_host != request["host"]:
            raise BackendUnavailable("capability_unavailable", f"{backend_id} is bound to host {expected_host!r}")
    proof = _readonly_evidence_valid(request, backend_id, backend)
    if backend.get("readonly_required") and proof is None:
        raise TerminalReviewFailure("readonly_violation", f"backend-bound L6 read-only evidence is required before {backend_id}")
    return proof or {}


def _normalize_readonly(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        return {"confirmed": value, "evidence": None}
    if isinstance(value, dict):
        confirmed = value.get("confirmed") is True
        evidence = value.get("evidence")
        if confirmed and isinstance(evidence, str) and evidence:
            return {"confirmed": True, "evidence": evidence}
        return {"confirmed": False, "evidence": evidence}
    return {"confirmed": False, "evidence": None}


def _validate_finding(finding: Any) -> Dict[str, Any]:
    if not isinstance(finding, dict):
        raise TerminalReviewFailure("schema_invalid", "finding must be a mapping")
    required = ("id", "severity", "classification", "change_risk", "location", "evidence", "required_fix")
    if any(not isinstance(finding.get(key), str) or not finding[key] for key in required):
        raise TerminalReviewFailure("schema_invalid", "finding is missing a required field")
    return {key: finding[key] for key in required}


def _normalize_result(
    raw: Any,
    request: Dict[str, Any],
    backend_id: str,
    started_at: str,
    validated_readonly_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise TerminalReviewFailure("schema_invalid", "backend result must be a mapping")
    if raw.get("schema") != RESULT_SCHEMA:
        raise TerminalReviewFailure("schema_invalid", f"backend result schema must be {RESULT_SCHEMA}")
    if raw.get("backend") != backend_id:
        raise TerminalReviewFailure("schema_invalid", "backend result identity does not match selected backend")
    reviewer = raw.get("reviewer")
    if not ((isinstance(reviewer, str) and reviewer) or isinstance(reviewer, dict)):
        raise TerminalReviewFailure("schema_invalid", "backend result reviewer identity is required")
    target = raw.get("target")
    expected_target = _target(request)
    if not isinstance(target, dict):
        raise TerminalReviewFailure("schema_invalid", "backend result target is required")
    if target.get("base_sha") != expected_target["base_sha"] or target.get("head_sha") != expected_target["head_sha"]:
        raise TerminalReviewFailure("evidence_mismatch", "backend result baseline identity differs from request")
    if target.get("scope") != expected_target["scope"]:
        raise TerminalReviewFailure("evidence_mismatch", "backend result scope differs from request")

    raw_status = raw.get("status", raw.get("verdict"))
    if not isinstance(raw_status, str):
        raise TerminalReviewFailure("schema_invalid", "backend result status is required")
    status = raw_status.upper()
    if status == "FAIL":
        status = "FINDINGS"
    if status not in {"PASS", "FINDINGS", "BLOCKED"}:
        raise TerminalReviewFailure("schema_invalid", f"unsupported backend result status {raw_status!r}")

    reviewed = raw.get("reviewed")
    unreadable = raw.get("unreadable")
    if not isinstance(reviewed, list) or not all(isinstance(item, str) for item in reviewed):
        raise TerminalReviewFailure("schema_invalid", "reviewed must be a string list")
    if not isinstance(unreadable, list) or not all(isinstance(item, str) for item in unreadable):
        raise TerminalReviewFailure("schema_invalid", "unreadable must be a string list")
    scope_set = set(expected_target["scope"])
    if not set(reviewed).issubset(scope_set) or not set(unreadable).issubset(scope_set):
        raise TerminalReviewFailure("evidence_mismatch", "reviewed/unreadable escapes requested scope")
    if set(reviewed) & set(unreadable):
        raise TerminalReviewFailure("schema_invalid", "reviewed and unreadable must not overlap")
    if status == "PASS" and (unreadable or set(reviewed) != scope_set):
        raise TerminalReviewFailure("evidence_mismatch", "PASS requires complete reviewed scope")
    if status == "FINDINGS" and set(reviewed) | set(unreadable) != scope_set:
        raise TerminalReviewFailure("evidence_mismatch", "FINDINGS must account for the complete requested scope")

    findings = raw.get("findings")
    if not isinstance(findings, list):
        raise TerminalReviewFailure("schema_invalid", "findings must be a list")
    normalized_findings = [_validate_finding(item) for item in findings]
    if status == "FINDINGS" and not normalized_findings:
        raise TerminalReviewFailure("schema_invalid", "FINDINGS requires at least one finding")
    if status == "PASS" and normalized_findings:
        raise TerminalReviewFailure("schema_invalid", "PASS cannot contain findings")

    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise TerminalReviewFailure("schema_invalid", "result evidence must be a non-empty list")

    failure_category = raw.get("failure_category")
    if status == "BLOCKED":
        if not isinstance(failure_category, str) or failure_category not in KNOWN_FAILURE_CATEGORIES:
            raise TerminalReviewFailure("schema_invalid", "BLOCKED requires a known failure_category")
    elif failure_category not in (None, ""):
        raise TerminalReviewFailure("schema_invalid", "PASS/FINDINGS cannot carry failure_category")

    provider_readonly = _normalize_readonly(raw.get("readonly_confirmation"))
    if status in {"PASS", "FINDINGS"}:
        # The adapter/provider is not a read-only authority.  Eligibility has
        # already matched the caller's backend-bound L6 proof; only the
        # Router may turn that verified fact into the accepted result-side
        # confirmation.  The proof itself never crosses the adapter boundary.
        if not isinstance(validated_readonly_evidence, dict):
            raise TerminalReviewFailure(
                "readonly_violation",
                "Router-side backend-bound L6 evidence is required before accepting a review result",
            )
        if (
            validated_readonly_evidence.get("backend") != backend_id
            or validated_readonly_evidence.get("level") != "L6"
            or validated_readonly_evidence.get("confirmed") is not True
            or not isinstance(validated_readonly_evidence.get("mode"), str)
            or not validated_readonly_evidence.get("mode")
            or not isinstance(validated_readonly_evidence.get("source"), str)
            or not validated_readonly_evidence.get("source")
        ):
            raise TerminalReviewFailure(
                "readonly_violation",
                "Router-side backend-bound L6 evidence is invalid for the selected backend",
            )
        readonly = {
            "confirmed": True,
            "evidence": f"router-validated:{backend_id}:{validated_readonly_evidence['mode']}",
        }
    else:
        readonly = provider_readonly
        if not readonly["confirmed"] and not (
            status == "BLOCKED" and failure_category in FALLBACK_CATEGORIES
        ):
            raise TerminalReviewFailure("readonly_violation", "backend did not confirm the read-only contract")

    lifecycle = raw.get("lifecycle", {})
    if lifecycle is not None and not isinstance(lifecycle, dict):
        raise TerminalReviewFailure("schema_invalid", "lifecycle must be a mapping")
    if isinstance(lifecycle, dict) and lifecycle.get("completed") is False and status in {"PASS", "FINDINGS"}:
        raise TerminalReviewFailure("review_incomplete", "completed review cannot have completed=false")

    completed_at = _utc_now()
    return {
        "schema": RESULT_SCHEMA,
        "backend": backend_id,
        "reviewer": reviewer,
        "target": expected_target,
        "baseline": {
            **expected_target,
            "verification": copy.deepcopy(request["verification"]),
        },
        "status": status,
        "verdict": status,
        "reviewed": list(reviewed),
        "unreadable": list(unreadable),
        "findings": normalized_findings,
        "evidence": copy.deepcopy(evidence),
        "started_at": started_at,
        "completed_at": completed_at,
        "lifecycle": {"started": True, "completed": status in {"PASS", "FINDINGS"}},
        "failure_category": failure_category,
        "fallback_eligible": False,
        "readonly_confirmation": readonly,
    }


def _run_cli_backend(backend: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    command = [backend["executable"], *backend["command"]]
    forbidden = set(backend.get("forbid_args", []))
    if forbidden.intersection(command):
        raise TerminalReviewFailure("configuration_invalid", f"backend {backend['id']} contains a forbidden argument")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=request["repo"],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=int(backend.get("timeout_seconds", 600)),
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BackendUnavailable("executable_missing", f"backend executable is unavailable: {backend['executable']}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BackendUnavailable("temporary_backend_failure", f"backend timed out: {backend['id']}") from exc
    except PermissionError as exc:
        raise TerminalReviewFailure("security_policy_violation", f"backend executable permission was denied: {backend['id']}") from exc
    except OSError as exc:
        raise BackendUnavailable("backend_unavailable", f"backend process could not start: {backend['id']}") from exc
    if completed.returncode != 0:
        availability_codes = set(backend.get("availability_exit_codes", []))
        transient_codes = set(backend.get("transient_exit_codes", []))
        if completed.returncode in availability_codes:
            raise BackendUnavailable(
                "backend_unavailable",
                f"backend exited with declared availability code {completed.returncode}",
            )
        if completed.returncode in transient_codes:
            raise BackendUnavailable(
                "temporary_backend_failure",
                f"backend exited with declared transient code {completed.returncode}",
            )
        raise TerminalReviewFailure(
            "backend_execution_failed",
            f"backend exited with unclassified code {completed.returncode}",
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise TerminalReviewFailure("schema_invalid", f"backend stdout is not JSON: {backend['id']}") from exc


Runner = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


def dispatch_review(
    request: Dict[str, Any],
    registry: Dict[str, Any],
    policy: Dict[str, Any],
    runner: Optional[Runner] = None,
) -> Dict[str, Any]:
    """Resolve and dispatch one review request, returning normalized JSON data."""

    request = copy.deepcopy(request)
    attempts: List[Dict[str, Any]] = []
    config_errors = validate_registry_policy(registry, policy)
    if config_errors:
        return _blocked_result(request, policy, attempts, "configuration_invalid", "; ".join(config_errors))
    try:
        _validate_request_shape(request)
        _verify_frozen_baseline(request)
    except RouterFailure as exc:
        return _blocked_result(request, policy, attempts, exc.category, exc.detail)

    role_spec = policy.get("roles", {}).get(request["role"])
    if not isinstance(role_spec, dict):
        return _blocked_result(request, policy, attempts, "configuration_invalid", f"unknown review role {request['role']!r}")
    candidates = role_spec.get("backends", [])
    backends = registry.get("backends", {})
    context = request["context"]
    fallback_categories = set(role_spec.get("fallback_on", []))
    max_hops = min(policy.get("max_hops", 1), role_spec.get("max_hops", 1))
    if context.get("hop_count", 0) >= max_hops:
        return _blocked_result(request, policy, attempts, "recursion_violation", "review dispatch max_hops exceeded")

    for candidate in candidates:
        backend_id = _backend_for_candidate(candidate, request["host"], policy, backends)
        if backend_id is None:
            attempts.append({"candidate": candidate, "outcome": "unavailable", "failure_category": "capability_unavailable"})
            continue
        if backend_id in context.get("dispatch_chain", []):
            attempts.append({"candidate": candidate, "backend": backend_id, "outcome": "blocked", "failure_category": "recursion_violation"})
            return _blocked_result(
                request,
                policy,
                attempts,
                "recursion_violation",
                f"backend {backend_id} already appears in dispatch_chain",
                backend_id,
            )
        spec = backends.get(backend_id)
        if not isinstance(spec, dict):
            attempts.append({"candidate": candidate, "backend": backend_id, "outcome": "unavailable", "failure_category": "capability_unavailable"})
            continue
        backend = dict(spec)
        backend["id"] = backend_id
        try:
            readonly_evidence = _check_backend_eligibility(
                request,
                role_spec,
                backend_id,
                backend,
            )
            routing_context = {
                "dispatch_boundary": "single-backend",
                "router_authority": False,
                "hop_count": context.get("hop_count", 0) + 1,
                "dispatch_chain": [*context.get("dispatch_chain", []), backend_id],
                "selected_backend": backend_id,
            }
            # Only the approved review context crosses the adapter boundary.
            # Authorization proofs, native guard metadata, and caller extras
            # remain workflow-local control data.
            adapter_request = {
                "schema": request["schema"],
                "role": request["role"],
                "host": request["host"],
                "repo": request["repo"],
                "base_sha": request["base_sha"],
                "head_sha": request["head_sha"],
                "scope": list(request["scope"]),
                "verification": copy.deepcopy(request["verification"]),
                "routing_context": routing_context,
            }
            started_at = _utc_now()
            raw = runner(backend, adapter_request) if runner is not None else _run_cli_backend(backend, adapter_request)
            normalized = _normalize_result(
                raw,
                request,
                backend_id,
                started_at,
                readonly_evidence,
            )
            if normalized["status"] == "BLOCKED" and normalized["failure_category"] in fallback_categories:
                attempts.append({
                    "candidate": candidate,
                    "backend": backend_id,
                    "outcome": "unavailable",
                    "failure_category": normalized["failure_category"],
                })
                continue
            attempts.append({"candidate": candidate, "backend": backend_id, "outcome": normalized["status"]})
            normalized["routing"] = _routing_metadata(
                request,
                policy,
                attempts,
                backend_id,
                readonly_evidence,
            )
            return normalized
        except BackendUnavailable as exc:
            attempts.append({
                "candidate": candidate,
                "backend": backend_id,
                "outcome": "unavailable",
                "failure_category": exc.category,
            })
            if exc.category not in fallback_categories:
                return _blocked_result(request, policy, attempts, exc.category, exc.detail, backend_id, started=True)
            continue
        except TerminalReviewFailure as exc:
            attempts.append({
                "candidate": candidate,
                "backend": backend_id,
                "outcome": "blocked",
                "failure_category": exc.category,
            })
            return _blocked_result(request, policy, attempts, exc.category, exc.detail, backend_id, started=True)

    return _blocked_result(
        request,
        policy,
        attempts,
        "all_backends_unavailable",
        "no eligible backend completed the review",
        started=bool(attempts),
    )


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read() if str(path) == "-" else path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise TerminalReviewFailure("schema_invalid", f"invalid review request: {exc}") from exc
    if not isinstance(value, dict):
        raise TerminalReviewFailure("schema_invalid", "review request must be a JSON object")
    return value


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path, help="JSON request path, or - for stdin")
    parser.add_argument("--registry", type=Path, default=AGENTS_DIR / "review-backends.yaml")
    parser.add_argument("--policy", type=Path, default=AGENTS_DIR / "routing-policy.yaml")
    parser.add_argument("--model-bindings", type=Path, default=AGENTS_DIR / "model-bindings.yaml")
    args = parser.parse_args(argv)
    try:
        registry, policy = load_configuration(args.registry, args.policy, args.model_bindings)
        request = _read_json(args.request)
        result = dispatch_review(request, registry, policy)
    except RouterFailure as exc:
        result = {
            "schema": RESULT_SCHEMA,
            "backend": "router",
            "status": "BLOCKED",
            "verdict": "BLOCKED",
            "failure_category": exc.category,
            "fallback_eligible": False,
            "evidence": [{"category": exc.category, "detail": exc.detail}],
            "lifecycle": {"started": False, "completed": False},
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "FINDINGS"} else 2


if __name__ == "__main__":
    sys.exit(main())

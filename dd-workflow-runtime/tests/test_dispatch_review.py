#!/usr/bin/env python3
"""Regression tests for Generic Review Backend Router v1."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any, Dict, List


AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
DISPATCH = AGENTS_DIR / "dispatch-review.py"
VALIDATOR = AGENTS_DIR / "validate-review-routing.py"
SPEC = importlib.util.spec_from_file_location("dispatch_review", DISPATCH)
assert SPEC is not None and SPEC.loader is not None
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)


class BackendScriptRunner:
    def __init__(self, outcomes: Dict[str, Any]):
        self.outcomes = outcomes
        self.calls: List[str] = []
        self.requests: List[Dict[str, Any]] = []

    def __call__(self, backend: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        backend_id = backend["id"]
        self.calls.append(backend_id)
        self.requests.append(request)
        outcome = self.outcomes[backend_id]
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            return outcome(backend, request)
        return outcome


# Fixture readonly modes must come from ROUTER.KNOWN_READONLY_MODES and mirror
# the checked-in registry contract per backend type (MB-GRILL-021).
_FIXTURE_READONLY_MODES = {
    "mcp": "snapshot-send-only",
    "cli": "agent-read-only-contract",
    "native": "codex-route-guard",
}


def _backend(backend_type: str = "cli", execution: str = "external", readonly_mode: str = "") -> Dict[str, Any]:
    return {
        "type": backend_type,
        "execution": execution,
        "executable": sys.executable,
        "command": ["-c", "pass"],
        "capabilities": ["strong-review"],
        "readonly_required": True,
        "readonly_mode": readonly_mode or _FIXTURE_READONLY_MODES[backend_type],
        "availability_exit_codes": [69],
        "transient_exit_codes": [75],
        "result_schema": ROUTER.RESULT_SCHEMA,
    }


def _configuration() -> tuple[Dict[str, Any], Dict[str, Any]]:
    registry = {
        "schema": ROUTER.CONFIG_SCHEMA,
        "result_schema": ROUTER.RESULT_SCHEMA,
        "backends": {
            "chatgpt-tunnel": {
                **_backend("mcp", "external", readonly_mode=ROUTER.TUNNEL_READONLY_MODE),
                "router_selectable": False,
            },
            "mcp-review": _backend("mcp", "external"),
            "codex-cli": _backend("cli", "external", readonly_mode="codex-read-only-transport"),
            "codex-native": {
                **_backend("native", "native-agent"),
                "host": "codex",
                "native_guard": "codex-route-guard",
                "router_selectable": False,
            },
            "opencode-cli": {
                **_backend("cli", "external", readonly_mode="agent-read-only-contract"),
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session", "owner": "opencode-review"},
                "continuation_readonly_evidence": True,
            },
            "opencode-native": {
                **_backend("native", "native-agent", readonly_mode="agent-read-only-contract"),
                "host": "opencode",
            },
        },
    }
    policy = {
        "schema": ROUTER.POLICY_SCHEMA,
        "max_hops": 1,
        "roles": {
            "strong-reviewer": {
                "capability": "strong-review",
                "max_hops": 1,
                "backends": ["mcp-review", "codex-cli", "host-native"],
                "fallback_on": sorted(ROUTER.FALLBACK_CATEGORIES),
            }
        },
        "stateful_roles": {
            "strong-reviewer-stateful": {
                "capability": "strong-review",
                "backends": ["opencode-cli"],
                "fallback_on": sorted(ROUTER.FALLBACK_CATEGORIES),
            }
        },
        "host_native": {"codex": "codex-native", "opencode": "opencode-native"},
    }
    assert ROUTER.validate_registry_policy(registry, policy) == []
    return registry, policy


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


class ReviewRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Router Test"], check=True)
        (self.repo / "review.md").write_text("frozen review target\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.md"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"], check=True)
        self.head = _git(self.repo, "rev-parse", "HEAD")
        self.base = self.head
        self.registry, self.policy = _configuration()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, **overrides: Any) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "schema": ROUTER.REQUEST_SCHEMA,
            "role": "strong-reviewer",
            "host": "codex",
            "repo": str(self.repo),
            "base_sha": self.base,
            "head_sha": self.head,
            "scope": ["review.md"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "external_review": {"authorization": "approved", "scope": ["review.md"]},
            "readonly_evidence": [
                {
                    "backend": "mcp-review",
                    "mode": "snapshot-send-only",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-mcp-read-only",
                },
                {
                    "backend": "codex-cli",
                    "mode": "codex-read-only-transport",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-codex-read-only",
                },
                {
                    "backend": "codex-native",
                    "mode": "codex-route-guard",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-codex-native-read-only",
                },
                {
                    "backend": "opencode-cli",
                    "mode": "agent-read-only-contract",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-opencode-read-only",
                },
                {
                    "backend": "opencode-native",
                    "mode": "agent-read-only-contract",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-opencode-native-read-only",
                },
            ],
            "context": {"hop_count": 0, "dispatch_chain": []},
        }
        request.update(overrides)
        return request

    def dispatch(self, request: Dict[str, Any], runner: Any = None) -> Dict[str, Any]:
        return ROUTER.dispatch_review(
            request,
            self.registry,
            self.policy,
            runner,
        )

    def result(
        self,
        backend: str,
        request: Dict[str, Any],
        status: str = "PASS",
        **overrides: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema": ROUTER.RESULT_SCHEMA,
            "backend": backend,
            "reviewer": f"{backend}/strong-reviewer",
            "target": {
                "base_sha": request["base_sha"],
                "head_sha": request["head_sha"],
                "scope": list(request["scope"]),
            },
            "status": status,
            "reviewed": list(request["scope"]) if status != "BLOCKED" else [],
            "unreadable": [],
            "findings": [],
            "evidence": ["reviewed frozen target"],
            "lifecycle": {"started": True, "completed": status != "BLOCKED"},
            "failure_category": None,
            "readonly_confirmation": {"confirmed": True, "evidence": "probe-no-write"},
        }
        payload.update(overrides)
        return payload

    def test_mcp_available_selects_mcp_without_calling_codex(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": self.result(
                "mcp-review",
                request,
                readonly_confirmation={"confirmed": False, "evidence": "adapter-design-only"},
            ),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "mcp-review")
        self.assertEqual(runner.calls, ["mcp-review"])
        self.assertEqual(result["routing"]["dispatch_boundary"], "single-backend")
        self.assertEqual(
            result["readonly_confirmation"],
            {"confirmed": True, "evidence": "router-validated:mcp-review:snapshot-send-only"},
        )
        self.assertNotIn("readonly_evidence", runner.requests[0])
        self.assertNotIn("internal_attestation", runner.requests[0])

    def test_router_attests_mcp_pass_and_findings_without_provider_confirmation(self) -> None:
        finding = {
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "MEDIUM",
            "location": "review.md:1",
            "evidence": "fixture finding",
            "required_fix": "repair the target",
        }
        for status, overrides in (("PASS", {}), ("FINDINGS", {"findings": [finding]})):
            with self.subTest(status=status):
                request = self.request()
                runner = BackendScriptRunner({
                    "mcp-review": self.result(
                        "mcp-review",
                        request,
                        status,
                        readonly_confirmation={"confirmed": False},
                        **overrides,
                    ),
                })
                result = self.dispatch(request, runner)
                self.assertEqual(result["status"], status)
                self.assertEqual(
                    result["readonly_confirmation"],
                    {"confirmed": True, "evidence": "router-validated:mcp-review:snapshot-send-only"},
                )

    def test_non_canonical_finding_enum_blocks_instead_of_passing(self) -> None:
        # MB-GRILL-019：change_risk="behavioral" 不是 canonical 枚举值，
        # 归一化入口必须判 schema_invalid 并 fail-closed，不得当作 FINDINGS 放行。
        finding = {
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "behavioral",
            "location": "review.md:1",
            "evidence": "fixture finding",
            "required_fix": "repair the target",
        }
        request = self.request()
        runner = BackendScriptRunner(
            {"mcp-review": self.result("mcp-review", request, "FINDINGS", findings=[finding])}
        )
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "schema_invalid")

    def test_mcp_unavailable_falls_back_to_codex(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture endpoint down"),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "codex-cli")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli"])
        self.assertEqual(result["routing"]["attempted"][0]["failure_category"], "endpoint_unavailable")
        self.assertEqual(
            result["readonly_confirmation"],
            {"confirmed": True, "evidence": "router-validated:codex-cli:codex-read-only-transport"},
        )

    def test_transport_blocked_result_without_readonly_confirmation_can_fallback(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": self.result(
                "mcp-review",
                request,
                "BLOCKED",
                failure_category="endpoint_unavailable",
                readonly_confirmation={"confirmed": False},
            ),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "codex-cli")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli"])

    def test_terminal_blocked_category_survives_provider_non_confirmation(self) -> None:
        request = self.request()
        for category in (
            "schema_invalid",
            "evidence_mismatch",
            "review_incomplete",
            "backend_execution_failed",
        ):
            with self.subTest(failure_category=category):
                runner = BackendScriptRunner({
                    "mcp-review": self.result(
                        "mcp-review",
                        request,
                        "BLOCKED",
                        failure_category=category,
                        readonly_confirmation={"confirmed": False},
                    ),
                    "codex-cli": self.result("codex-cli", request),
                    "codex-native": self.result("codex-native", request),
                })
                result = self.dispatch(request, runner)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["failure_category"], category)
                self.assertEqual(result["backend"], "mcp-review")
                self.assertEqual(runner.calls, ["mcp-review"])
                self.assertFalse(result["readonly_confirmation"]["confirmed"])
                self.assertIsNone(result["readonly_confirmation"]["evidence"])

    def test_blocked_readonly_violation_stays_readonly_violation(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": self.result(
                "mcp-review",
                request,
                "BLOCKED",
                failure_category="readonly_violation",
                readonly_confirmation={"confirmed": False},
            ),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, ["mcp-review"])

    def test_normalization_preserves_terminal_blocked_category_observation_only(self) -> None:
        request = self.request()
        raw = self.result(
            "mcp-review",
            request,
            "BLOCKED",
            failure_category="schema_invalid",
            readonly_confirmation={"confirmed": False},
        )
        normalized = ROUTER._normalize_result(
            raw,
            request,
            "mcp-review",
            "started",
            request["readonly_evidence"][0],
        )
        self.assertEqual(normalized["status"], "BLOCKED")
        self.assertEqual(normalized["failure_category"], "schema_invalid")
        self.assertEqual(normalized["fallback_eligible"], False)
        self.assertEqual(normalized["readonly_confirmation"], {"confirmed": False, "evidence": None})

    def test_terminal_blocked_categories_never_fallback(self) -> None:
        request = self.request()
        for category in ("schema_invalid", "evidence_mismatch"):
            with self.subTest(failure_category=category):
                runner = BackendScriptRunner({
                    "mcp-review": self.result(
                        "mcp-review",
                        request,
                        "BLOCKED",
                        failure_category=category,
                        readonly_confirmation={"confirmed": False},
                    ),
                    "codex-cli": self.result("codex-cli", request),
                    "codex-native": self.result("codex-native", request),
                })
                result = self.dispatch(request, runner)
                self.assertNotEqual(result["backend"], "codex-cli")
                self.assertEqual(runner.calls, ["mcp-review"])

    def test_mcp_and_codex_unavailable_block_without_host_native_handoff(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("backend_unavailable", "fixture"),
            "codex-cli": ROUTER.BackendUnavailable("executable_missing", "fixture"),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli"])

    def test_host_native_alias_resolves_opencode_backend(self) -> None:
        request = self.request(host="opencode")
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture"),
            "codex-cli": ROUTER.BackendUnavailable("executable_missing", "fixture"),
            "opencode-native": self.result("opencode-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "opencode-native")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli", "opencode-native"])

    def test_all_unavailable_returns_blocked(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture"),
            "codex-cli": ROUTER.BackendUnavailable("temporary_backend_failure", "fixture"),
            "codex-native": ROUTER.BackendUnavailable("capability_unavailable", "fixture"),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertFalse(result["fallback_eligible"])

    def test_reviewer_findings_never_fallback(self) -> None:
        request = self.request()
        finding = {
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "MEDIUM",
            "location": "review.md:1",
            "evidence": "fixture finding",
            "required_fix": "repair the target",
        }
        runner = BackendScriptRunner({
            "mcp-review": self.result("mcp-review", request, "FAIL", findings=[finding]),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "FINDINGS")
        self.assertEqual(result["verdict"], "FINDINGS")
        self.assertEqual(runner.calls, ["mcp-review"])

    def test_schema_invalid_never_fallback(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": {"schema": "wrong"},
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "schema_invalid")
        self.assertEqual(runner.calls, ["mcp-review"])

    def test_baseline_drift_blocks_before_any_adapter(self) -> None:
        request = self.request()
        (self.repo / "review.md").write_text("changed after freeze\n")
        runner = BackendScriptRunner({})
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "baseline_mismatch")
        self.assertEqual(runner.calls, [])

    def test_malformed_request_fails_closed_without_secondary_exception(self) -> None:
        runner = BackendScriptRunner({})
        result = self.dispatch({"schema": "wrong"}, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "schema_invalid")
        self.assertEqual(runner.calls, [])

    def test_caller_supplied_native_guard_is_rejected(self) -> None:
        request = self.request(
            native_guard={"decision": "ALLOW", "native_spawn_allowed": True},
        )
        runner = BackendScriptRunner({})
        result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "security_policy_violation")
        self.assertEqual(runner.calls, [])

    def test_codex_native_requires_host_native_handoff(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture"),
            "codex-cli": ROUTER.BackendUnavailable("executable_missing", "fixture"),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli"])

    def test_codex_native_cannot_be_enabled_by_registry_override(self) -> None:
        registry = json.loads(json.dumps(self.registry))
        registry["backends"]["codex-native"]["router_selectable"] = True
        result = ROUTER.dispatch_review(
            self.request(),
            registry,
            self.policy,
        )
        self.assertEqual(result["failure_category"], "configuration_invalid")

    def test_inherited_thread_id_cannot_enable_generic_codex_native_route(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture"),
            "codex-cli": ROUTER.BackendUnavailable("executable_missing", "fixture"),
            "codex-native": self.result("codex-native", request),
        })
        with mock.patch.dict("os.environ", {"CODEX_THREAD_ID": "other-read-only-thread"}):
            result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertEqual(runner.calls, ["mcp-review", "codex-cli"])

    def test_readonly_evidence_cannot_be_reused_for_another_backend(self) -> None:
        request = self.request()
        request["readonly_evidence"] = [request["readonly_evidence"][0]]
        runner = BackendScriptRunner({
            "mcp-review": ROUTER.BackendUnavailable("endpoint_unavailable", "fixture"),
            "codex-cli": self.result("codex-cli", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, ["mcp-review"])

    def test_mcp_eligibility_rejects_invalid_backend_bound_l6_evidence(self) -> None:
        valid = self.request()["readonly_evidence"][0]
        invalid_cases = {
            "wrong backend": {**valid, "backend": "codex-cli"},
            "wrong mode": {**valid, "mode": ROUTER.TUNNEL_READONLY_MODE},
            "wrong level": {**valid, "level": "L7"},
            "not confirmed": {**valid, "confirmed": False},
            "missing source": {key: value for key, value in valid.items() if key != "source"},
        }
        for label, proof in invalid_cases.items():
            with self.subTest(label=label):
                request = self.request(readonly_evidence=[proof])
                runner = BackendScriptRunner({
                    "mcp-review": self.result("mcp-review", request),
                })
                result = self.dispatch(request, runner)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["failure_category"], "readonly_violation")
                self.assertEqual(runner.calls, [])

    def test_pass_or_findings_cannot_be_accepted_without_router_l6_evidence(self) -> None:
        request = self.request(readonly_evidence=[])
        runner = BackendScriptRunner({
            "mcp-review": self.result("mcp-review", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, [])

    def test_normalization_rejects_provider_success_without_router_l6_evidence(self) -> None:
        request = self.request()
        raw = self.result("mcp-review", request, readonly_confirmation={"confirmed": True, "evidence": "provider-claim"})
        with self.assertRaises(ROUTER.TerminalReviewFailure) as raised:
            ROUTER._normalize_result(raw, request, "mcp-review", "started")
        self.assertEqual(raised.exception.category, "readonly_violation")

    def test_findings_cannot_be_accepted_without_router_l6_evidence(self) -> None:
        request = self.request(readonly_evidence=[])
        finding = {
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "MEDIUM",
            "location": "review.md:1",
            "evidence": "fixture finding",
            "required_fix": "repair the target",
        }
        runner = BackendScriptRunner({
            "mcp-review": self.result(
                "mcp-review",
                request,
                "FINDINGS",
                findings=[finding],
                readonly_confirmation={"confirmed": True, "evidence": "provider-forged"},
            ),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, [])

    def test_normalization_rejects_tampered_router_l6_evidence_for_success(self) -> None:
        request = self.request()
        valid_proof = request["readonly_evidence"][0]
        tampered_cases = {
            "missing evidence": None,
            "wrong backend binding": {**valid_proof, "backend": "codex-cli"},
            "unconfirmed proof": {**valid_proof, "confirmed": False},
        }
        for label, validated in tampered_cases.items():
            with self.subTest(case=label):
                for status in ("PASS", "FINDINGS"):
                    raw = self.result(
                        "mcp-review",
                        request,
                        status,
                        findings=[{
                            "id": "RV-001",
                            "severity": "HIGH",
                            "classification": "FINDING",
                            "change_risk": "MEDIUM",
                            "location": "review.md:1",
                            "evidence": "fixture finding",
                            "required_fix": "repair the target",
                        }] if status == "FINDINGS" else [],
                        readonly_confirmation={"confirmed": True, "evidence": "provider-forged"},
                    )
                    with self.subTest(status=status):
                        with self.assertRaises(ROUTER.TerminalReviewFailure) as raised:
                            ROUTER._normalize_result(raw, request, "mcp-review", "started", validated)
                        self.assertEqual(raised.exception.category, "readonly_violation")

    def test_unclassified_cli_exit_is_terminal_and_does_not_fallback(self) -> None:
        registry = json.loads(json.dumps(self.registry))
        registry["backends"]["mcp-review"]["executable"] = sys.executable
        registry["backends"]["mcp-review"]["command"] = ["-c", "import sys; sys.exit(1)"]
        result = ROUTER.dispatch_review(
            self.request(),
            registry,
            self.policy,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "backend_execution_failed")
        self.assertEqual(result["backend"], "mcp-review")

    def test_declared_availability_exit_can_fallback(self) -> None:
        registry = json.loads(json.dumps(self.registry))
        registry["backends"]["mcp-review"]["executable"] = sys.executable
        registry["backends"]["mcp-review"]["command"] = ["-c", "import sys; sys.exit(69)"]
        registry["backends"]["codex-cli"]["executable"] = sys.executable
        registry["backends"]["codex-cli"]["command"] = [
            "-c",
            (
                "import json,sys; p=json.load(sys.stdin); "
                "print(json.dumps({'schema':'dd-review-result/1','backend':'codex-cli',"
                "'reviewer':'fake','target':{'base_sha':p['base_sha'],"
                "'head_sha':p['head_sha'],'scope':p['scope']},'status':'PASS',"
                "'reviewed':p['scope'],'unreadable':[],'findings':[],"
                "'evidence':['fake'],'readonly_confirmation':"
                "{'confirmed':True,'evidence':'probe'}}))"
            ),
        ]
        result = ROUTER.dispatch_review(
            self.request(),
            registry,
            self.policy,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "codex-cli")
        self.assertEqual(result["routing"]["attempted"][0]["failure_category"], "backend_unavailable")

    def test_readonly_violation_is_fail_closed_without_router_attestation(self) -> None:
        request = self.request(readonly_evidence=[])
        runner = BackendScriptRunner({
            "mcp-review": self.result("mcp-review", request, readonly_confirmation={"confirmed": False}),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, [])

    def test_max_hops_blocks_nested_dispatch(self) -> None:
        request = self.request(context={"hop_count": 1, "dispatch_chain": ["outer-router"]})
        runner = BackendScriptRunner({})
        result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "recursion_violation")
        self.assertEqual(runner.calls, [])

    def test_a_to_b_to_a_recursion_guard_blocks_reentry(self) -> None:
        request = self.request(context={"hop_count": 0, "dispatch_chain": ["mcp-review"]})
        runner = BackendScriptRunner({})
        result = self.dispatch(request, runner)
        self.assertEqual(result["failure_category"], "recursion_violation")
        self.assertEqual(runner.calls, [])

    def test_incomplete_review_is_not_pass(self) -> None:
        request = self.request()
        incomplete = self.result(
            "mcp-review",
            request,
            "BLOCKED",
            lifecycle={"started": True, "completed": False},
            failure_category="review_incomplete",
            evidence=["provider interrupted before completion"],
        )
        runner = BackendScriptRunner({
            "mcp-review": incomplete,
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "review_incomplete")
        self.assertEqual(runner.calls, ["mcp-review"])

    def test_cli_adapter_uses_fixed_cwd_and_single_request_boundary(self) -> None:
        fake = Path(self.temp.name) / "fake_backend.py"
        log = Path(self.temp.name) / "invocation.json"
        fake.write_text(
            "import json, pathlib, sys\n"
            "payload = json.load(sys.stdin)\n"
            "pathlib.Path(sys.argv[1]).write_text(json.dumps({'cwd': str(pathlib.Path.cwd()), 'payload': payload}))\n"
            "print(json.dumps({'schema': 'dd-review-result/1', 'backend': 'mcp-review', 'reviewer': 'fake', 'target': {'base_sha': payload['base_sha'], 'head_sha': payload['head_sha'], 'scope': payload['scope']}, 'status': 'PASS', 'reviewed': payload['scope'], 'unreadable': [], 'findings': [], 'evidence': ['fake'], 'readonly_confirmation': {'confirmed': True, 'evidence': 'probe'}}))\n"
        )
        registry = json.loads(json.dumps(self.registry))
        registry["backends"]["mcp-review"]["executable"] = sys.executable
        registry["backends"]["mcp-review"]["command"] = [str(fake), str(log)]
        result = ROUTER.dispatch_review(self.request(), registry, self.policy)
        self.assertEqual(result["status"], "PASS")
        invocation = json.loads(log.read_text())
        self.assertEqual(invocation["cwd"], str(self.repo.resolve()))
        self.assertEqual(invocation["payload"]["routing_context"]["dispatch_boundary"], "single-backend")
        self.assertFalse(invocation["payload"]["routing_context"]["router_authority"])
        self.assertNotIn("external_review", invocation["payload"])
        self.assertNotIn("native_guard", invocation["payload"])
        self.assertNotIn("readonly_evidence", invocation["payload"])
        self.assertNotIn("internal_attestation", invocation["payload"])


class RoutingConfigTests(unittest.TestCase):
    def test_checked_in_registry_policy_and_model_bindings_are_isolated(self) -> None:
        registry, policy = ROUTER.load_configuration(
            AGENTS_DIR / "review-backends.yaml",
            AGENTS_DIR / "routing-policy.yaml",
            AGENTS_DIR / "model-bindings.yaml",
        )
        self.assertIn("mcp-review", registry["backends"])
        self.assertIn("opencode-cli", registry["backends"])
        self.assertIn("opencode-native", registry["backends"])
        self.assertEqual(policy["roles"]["strong-reviewer"]["backends"], ["mcp-review", "codex-cli", "host-native"])

    def test_missing_backend_reference_is_rejected(self) -> None:
        registry, policy = _configuration()
        policy["roles"]["strong-reviewer"]["backends"].insert(0, "does-not-exist")
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("unknown backend reference" in error for error in errors))

    def test_model_bindings_cannot_contain_transport_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model-bindings.yaml"
            path.write_text("schema: dd-model-bindings/1\nbackend: opencode-cli\n")
            errors = ROUTER.validate_model_bindings_isolation(path)
        self.assertTrue(any("external routing key 'backend'" in error for error in errors))

    def test_validator_cli_returns_nonzero_for_missing_backend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            registry = directory_path / "registry.yaml"
            policy = directory_path / "policy.yaml"
            model = directory_path / "model.yaml"
            registry.write_text((AGENTS_DIR / "review-backends.yaml").read_text())
            policy.write_text((AGENTS_DIR / "routing-policy.yaml").read_text().replace("mcp-review, codex-cli, host-native", "missing, codex-cli, host-native"))
            model.write_text((AGENTS_DIR / "model-bindings.yaml").read_text())
            result = subprocess.run(
                [sys.executable, str(VALIDATOR), "--registry", str(registry), "--policy", str(policy), "--model-bindings", str(model)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown backend reference", result.stdout)

    def test_forbidden_auto_flag_is_rejected(self) -> None:
        registry, policy = _configuration()
        registry["backends"]["mcp-review"]["command"] = ["review", "--auto"]
        registry["backends"]["mcp-review"]["forbid_args"] = ["--auto"]
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("forbidden argument" in error for error in errors))

    def test_checked_in_registry_includes_grilling_backend_and_stateful_order(self) -> None:
        # MB-GRILL-021 / MB-GRILL-020：chatgpt-tunnel 入 registry 并作为默认
        # grilling 后端；routing-policy 提供 stateful 候选序列骨架。序列成员
        # 为空属诚实过渡态（MB-GRILL-020：FR-MB-016 会话标识合同与续接只读
        # 证据落地前，无 backend 满足 FR-MB-001 三项资格）。
        registry, policy = ROUTER.load_configuration(
            AGENTS_DIR / "review-backends.yaml",
            AGENTS_DIR / "routing-policy.yaml",
            AGENTS_DIR / "model-bindings.yaml",
        )
        self.assertIn("chatgpt-tunnel", registry["backends"])
        tunnel = registry["backends"]["chatgpt-tunnel"]
        self.assertEqual(tunnel["readonly_mode"], ROUTER.TUNNEL_READONLY_MODE)
        self.assertIs(tunnel["router_selectable"], False)
        self.assertEqual(policy["stateful_roles"]["strong-reviewer-stateful"]["backends"], ["opencode-cli"])

    def test_stateful_roles_accept_empty_order_as_transitional_state(self) -> None:
        registry, policy = _configuration()
        policy["stateful_roles"]["strong-reviewer-stateful"]["backends"] = []
        self.assertEqual(ROUTER.validate_registry_policy(registry, policy), [])

    def test_router_chain_rejects_unselectable_external_backend(self) -> None:
        # MB-GRILL-028：router_selectable: false 是通用 Router 禁令，对外部
        # backend 同样生效（snapshot 豁免不得被未来的 false 成员穿透）。
        registry, policy = _configuration()
        registry["backends"]["future-mcp"] = {
            **_backend("mcp", "external", readonly_mode=ROUTER.TUNNEL_READONLY_MODE),
            "router_selectable": False,
        }
        policy["roles"]["strong-reviewer"]["backends"].insert(0, "future-mcp")
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(
            any("router_selectable: false backend(s)" in error for error in errors),
            errors,
        )

    def test_dispatch_eligibility_rejects_unselectable_external_backend(self) -> None:
        # MB-GRILL-028 防御层：即使校验被绕过，派发层也对 external 的
        # router_selectable: false fail-closed。
        registry, policy = _configuration()
        registry["backends"]["future-mcp"] = {
            **_backend("mcp", "external", readonly_mode=ROUTER.TUNNEL_READONLY_MODE),
            "router_selectable": False,
        }
        policy["roles"]["strong-reviewer"]["backends"] = ["future-mcp"]
        # 新检查在 external 授权与 evidence 校验之前触发，最小 request 即可。
        with self.assertRaises(ROUTER.BackendUnavailable) as ctx:
            ROUTER._check_backend_eligibility({}, policy["roles"]["strong-reviewer"], "future-mcp", registry["backends"]["future-mcp"])
        self.assertEqual(ctx.exception.category, "capability_unavailable")
        self.assertIn("not router-selectable", str(ctx.exception))

    def test_grilling_only_backend_in_router_chain_is_rejected(self) -> None:
        # MB-GRILL-018.3：不得把 chatgpt-tunnel 塞进 Router 单跳链。
        registry, policy = _configuration()
        policy["roles"]["strong-reviewer"]["backends"].insert(0, "chatgpt-tunnel")
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("grilling-only backend(s)" in error for error in errors))

    def test_unknown_readonly_mode_is_rejected(self) -> None:
        registry, policy = _configuration()
        registry["backends"]["chatgpt-tunnel"]["readonly_mode"] = "bogus-mode"
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("unknown readonly mode" in error for error in errors))

    def test_router_selectable_mcp_keeps_snapshot_mode_requirement(self) -> None:
        registry, policy = _configuration()
        registry["backends"]["mcp-review"]["readonly_mode"] = ROUTER.TUNNEL_READONLY_MODE
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("router-selectable MCP readonly_mode must be" in error for error in errors))

    def test_grilling_only_mcp_may_use_tunnel_readonly_mode(self) -> None:
        # DEC-MB-02：chatgpt-tunnel 是 Tunnel 自读，不是快照发送；MCP 快照硬
        # 校验只约束 router-selectable 的 MCP backend。
        registry, policy = _configuration()
        self.assertEqual(ROUTER.validate_registry_policy(registry, policy), [])

    def test_stateful_roles_reject_non_grilling_unselectable_backend(self) -> None:
        # native backend 需要 verified host handoff，不能进 stateful 候选序。
        registry, policy = _configuration()
        policy["stateful_roles"]["strong-reviewer-stateful"]["backends"] = ["codex-native"]
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("cannot join a stateful candidate order" in error for error in errors))

    def test_stateful_roles_reject_unknown_backend(self) -> None:
        registry, policy = _configuration()
        policy["stateful_roles"]["strong-reviewer-stateful"]["backends"] = ["does-not-exist"]
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("unknown backend reference" in error for error in errors))

    def test_stateful_roles_reject_bad_fallback_category(self) -> None:
        registry, policy = _configuration()
        policy["stateful_roles"]["strong-reviewer-stateful"]["fallback_on"] = ["schema_invalid"]
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("unknown categories" in error for error in errors))


class FindingEnumContractTests(unittest.TestCase):
    """MB-GRILL-019：finding 三字段必须是 grilling canonical 枚举。

    合同变化说明：旧断言只要求 severity/classification/change_risk 是非空字符串，
    于是 provider 可以输出 `classification=behavioral-correctness`、
    `change_risk=behavioral` 这类 runtime 私有取值；这类 finding 能通过 runtime
    校验，却无法进入 gpt-grilling-review 的 F/V/H 分流状态机。新合同要求三个字段
    必须落在 gpt-grilling-review 拥有的 canonical 枚举内，从而保留原合同保护目的
    （finding 可被机械分流），只是把校验强度从"存在"升级为"语义合法"。
    """

    def _finding(self, **overrides: Any) -> Dict[str, Any]:
        finding = {
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "MEDIUM",
            "location": "review.md:1",
            "evidence": "fixture",
            "required_fix": "repair",
        }
        finding.update(overrides)
        return finding

    def _assert_rejected(self, field: str, value: str) -> None:
        with self.subTest(field=field, value=value):
            with self.assertRaises(ROUTER.TerminalReviewFailure) as ctx:
                ROUTER._validate_finding(self._finding(**{field: value}))
            self.assertEqual(ctx.exception.category, "schema_invalid")

    def test_non_canonical_classification_is_rejected(self) -> None:
        self._assert_rejected("classification", "behavioral-correctness")

    def test_non_canonical_change_risk_is_rejected(self) -> None:
        self._assert_rejected("change_risk", "behavioral")

    def test_non_canonical_severity_is_rejected(self) -> None:
        self._assert_rejected("severity", "CRITICAL")

    def test_lowercase_enum_value_is_rejected(self) -> None:
        self._assert_rejected("classification", "finding")

    def test_all_canonical_enum_values_are_accepted(self) -> None:
        for severity in ROUTER.SEVERITY_VALUES:
            for classification in ROUTER.CLASSIFICATION_VALUES:
                for change_risk in ROUTER.CHANGE_RISK_VALUES:
                    with self.subTest(severity=severity, classification=classification, change_risk=change_risk):
                        validated = ROUTER._validate_finding(
                            self._finding(
                                severity=severity,
                                classification=classification,
                                change_risk=change_risk,
                            )
                        )
                        self.assertEqual(validated["severity"], severity)
                        self.assertEqual(validated["classification"], classification)
                        self.assertEqual(validated["change_risk"], change_risk)


class InvocationFormsRegistryContractTests(unittest.TestCase):
    """FR-MB-015/016 registry-side contract: invocation_forms + session_identity.

    MB-GRILL-031: the registry is the invocation-contract owner, so a backend
    that advertises `resume` must declare a complete session_identity mapping
    unconditionally, and `session_identity.field` must name the canonical
    normalized result field (`session`) -- a contract that could never drive
    extraction is not a contract.
    """

    def _registry_with(self, backend_id: str, spec_overrides: Dict[str, Any]):
        registry, policy = _configuration()
        # 本测试类从"无续接声明"的干净基底构造合同样本：checked-in fixture 的
        # opencode-cli 已带完整续接声明（MB-GRILL-020 落地后），若直接 update 会
        # 残留旧字段、掩盖"缺字段"类用例。同时把被测 backend 移出 stateful 序列，
        # 使 registry 层规则与 stateful 成员资格两套检查解耦测试。
        for key in ("invocation_forms", "session_identity", "continuation_readonly_evidence"):
            registry["backends"][backend_id].pop(key, None)
        policy["stateful_roles"]["strong-reviewer-stateful"]["backends"] = []
        registry["backends"][backend_id].update(spec_overrides)
        return registry, policy

    def _stateful_member(self, backend_id: str, spec_overrides: Dict[str, Any]):
        registry, policy = self._registry_with(backend_id, spec_overrides)
        policy["stateful_roles"]["strong-reviewer-stateful"]["backends"] = [backend_id]
        return registry, policy

    def test_unknown_invocation_form_rejected(self) -> None:
        registry, policy = self._registry_with("opencode-cli", {"invocation_forms": ["initial", "fork"]})
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("invocation_forms" in error for error in errors), errors)

    def test_invocation_forms_missing_initial_rejected(self) -> None:
        registry, policy = self._registry_with("opencode-cli", {"invocation_forms": ["resume"]})
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("must always include 'initial'" in error for error in errors), errors)

    def test_resume_with_partial_session_identity_rejected(self) -> None:
        registry, policy = self._registry_with(
            "opencode-cli",
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session"},
            },
        )
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("session_identity" in error for error in errors), errors)

    def test_resume_without_session_identity_mapping_rejected(self) -> None:
        # MB-GRILL-031: the declaration itself is incomplete without the
        # mapping -- the stateful gate must not be the only line of defence.
        registry, policy = self._registry_with("opencode-cli", {"invocation_forms": ["initial", "resume"]})
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("session_identity: required" in error for error in errors), errors)

    def test_session_identity_field_must_be_canonical(self) -> None:
        # MB-GRILL-031: `field` names the canonical normalized result field;
        # a free-form value could never drive extraction.
        registry, policy = self._registry_with(
            "opencode-cli",
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "resume_handle", "owner": "opencode-review"},
            },
        )
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("canonical normalized result field" in error for error in errors), errors)

    def test_resume_with_full_session_identity_passes_backend_check(self) -> None:
        # Full declaration, backend NOT in the stateful order: no errors.  An
        # unqualified backend may advertise resume for grilling without the
        # stateful gate being involved.
        registry, policy = self._registry_with(
            "opencode-cli",
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session", "owner": "opencode-review"},
            },
        )
        self.assertEqual(ROUTER.validate_registry_policy(registry, policy), [])

    def test_stateful_member_without_resume_form_rejected(self) -> None:
        registry, policy = self._stateful_member("opencode-cli", {"invocation_forms": ["initial"]})
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("FR-MB-015" in error for error in errors), errors)

    def test_stateful_member_without_session_identity_rejected(self) -> None:
        registry, policy = self._stateful_member("opencode-cli", {"invocation_forms": ["initial", "resume"]})
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("session identity" in error for error in errors), errors)

    def test_stateful_member_without_continuation_evidence_rejected(self) -> None:
        registry, policy = self._stateful_member(
            "opencode-cli",
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session", "owner": "opencode-review"},
            },
        )
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("backend-bound readonly evidence" in error for error in errors), errors)

    def test_initial_only_backend_with_malformed_session_identity_rejected(self) -> None:
        # MB-GRILL-033: a declared contract must be canonical even for an
        # initial-only backend.  Otherwise an explicit initial continuation
        # would be accepted on a contract that can never drive extraction --
        # dispatch_review() runs this validator first, so this is the real
        # line of defence.
        registry, policy = self._registry_with(
            "opencode-cli",
            {
                "invocation_forms": ["initial"],
                "session_identity": {"field": "wrong_field", "owner": ""},
            },
        )
        errors = ROUTER.validate_registry_policy(registry, policy)
        self.assertTrue(any("canonical normalized result field" in error for error in errors), errors)
        self.assertTrue(any("session_identity.owner" in error for error in errors), errors)

    def test_initial_only_backend_with_canonical_session_identity_accepted(self) -> None:
        registry, policy = self._registry_with(
            "opencode-cli",
            {
                "invocation_forms": ["initial"],
                "session_identity": {"field": "session", "owner": "opencode-review"},
            },
        )
        self.assertEqual(ROUTER.validate_registry_policy(registry, policy), [])

    def test_fully_qualified_stateful_member_accepted(self) -> None:
        registry, policy = self._stateful_member(
            "opencode-cli",
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session", "owner": "opencode-review"},
                "continuation_readonly_evidence": True,
            },
        )
        self.assertEqual(ROUTER.validate_registry_policy(registry, policy), [])


class ContinuationSessionIdentityTests(unittest.TestCase):
    """FR-MB-003.2 / FR-MB-016: a resumed session identity must be proven, not
    assumed.  A resume continuation requires the normalized result to carry a
    structured session identity whose form is `resume` and whose handle equals
    the caller-supplied one; any mismatch is session_resume_mismatch
    (transport/runtime state, never a grilling finding -- FR-MB-020)."""

    def setUp(self) -> None:
        # A real repo is required for full-dispatch tests (frozen baseline
        # verification); the pure _normalize_result tests do not need it.
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Router Test"], check=True)
        (self.repo / "review.md").write_text("frozen review target\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.md"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"], check=True)
        self.head = _git(self.repo, "rev-parse", "HEAD")
        self.base = self.head

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _request(self, continuation: Any = None, head_sha: str = "", repo: str = "") -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "schema": ROUTER.REQUEST_SCHEMA,
            "role": "strong-reviewer",
            "host": "codex",
            "repo": repo or str(self.repo),
            "base_sha": head_sha or self.base,
            "head_sha": head_sha or self.head,
            "scope": ["review.md"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "external_review": {"authorization": "approved", "scope": ["review.md"]},
            "readonly_evidence": [
                {
                    "backend": "mcp-review",
                    "mode": "snapshot-send-only",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-mcp-read-only",
                }
            ],
            "context": {"hop_count": 0, "dispatch_chain": []},
        }
        if continuation is not None:
            request["continuation"] = continuation
        return request

    def _payload(self, request: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema": ROUTER.RESULT_SCHEMA,
            "backend": "mcp-review",
            "reviewer": "mcp-review/strong-reviewer",
            "target": {
                "base_sha": request["base_sha"],
                "head_sha": request["head_sha"],
                "scope": list(request["scope"]),
            },
            "status": "PASS",
            "reviewed": list(request["scope"]),
            "unreadable": [],
            "findings": [],
            "evidence": ["reviewed frozen target"],
            "lifecycle": {"started": True, "completed": True},
            "failure_category": None,
            "readonly_confirmation": {"confirmed": True, "evidence": "probe-no-write"},
        }
        payload.update(overrides)
        return payload

    def _normalize(self, request: Dict[str, Any], payload: Dict[str, Any]):
        """Return (normalized_result, None) or (None, failure_category).

        The session-identity contract lives in _normalize_result, so those
        contract tests drive that function directly instead of the full dispatch
        loop.  The request fixture is still a fully valid request so the
        request-shape tests exercise the continuation checks, not an earlier
        host/repo failure (MB-GRILL-032).
        """
        try:
            return (
                ROUTER._normalize_result(
                    payload,
                    request,
                    "mcp-review",
                    ROUTER._utc_now(),
                    {
                        "backend": "mcp-review",
                        "level": "L6",
                        "confirmed": True,
                        "mode": "snapshot-send-only",
                        "source": "test-mcp-read-only",
                    },
                ),
                None,
            )
        except ROUTER.TerminalReviewFailure as exc:
            return None, exc.category

    def _full_dispatch(self, request: Dict[str, Any], payload: Dict[str, Any]):
        """Run the full dispatch loop with a capturing runner (MB-GRILL-029)."""
        registry, policy = _configuration()
        registry["backends"]["mcp-review"].update(
            {
                "invocation_forms": ["initial", "resume"],
                "session_identity": {"field": "session", "owner": "mcp-review"},
            }
        )
        policy["roles"]["strong-reviewer"]["backends"] = ["mcp-review"]
        runner = BackendScriptRunner({"mcp-review": payload})
        result = ROUTER.dispatch_review(request, registry, policy, runner)
        return result, runner

    def test_resume_request_without_handle_is_schema_invalid(self) -> None:
        request = self._request(continuation={"form": "resume"})
        with self.assertRaises(ROUTER.TerminalReviewFailure) as ctx:
            ROUTER._validate_request_shape(request)
        self.assertEqual(ctx.exception.category, "schema_invalid")
        self.assertIn("continuation.handle", ctx.exception.detail)

    def test_unknown_continuation_form_is_schema_invalid(self) -> None:
        request = self._request(continuation={"form": "fork", "handle": "ses_x"})
        with self.assertRaises(ROUTER.TerminalReviewFailure) as ctx:
            ROUTER._validate_request_shape(request)
        self.assertEqual(ctx.exception.category, "schema_invalid")
        self.assertIn("continuation.form", ctx.exception.detail)

    def test_full_dispatch_rejects_explicit_initial_without_session_contract(self) -> None:
        # MB-GRILL-033: an explicit initial form must yield a persistable
        # handle, so a backend without a session identity contract has to fail
        # fast -- the adapter must not run a real review first.
        request = self._request(continuation={"form": "initial"})
        registry, policy = _configuration()
        policy["roles"]["strong-reviewer"]["backends"] = ["mcp-review"]
        runner = BackendScriptRunner({"mcp-review": self._payload(request)})
        result = ROUTER.dispatch_review(request, registry, policy, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertEqual(runner.calls, [])

    def test_full_dispatch_explicit_initial_passes_with_session_contract(self) -> None:
        request = self._request(continuation={"form": "initial"})
        payload = self._payload(request, session={"form": "initial", "handle": "ses_new"})
        result, runner = self._full_dispatch(request, payload)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(runner.requests[0].get("continuation"), {"form": "initial"})
        self.assertTrue(result["session"]["verified"])
        self.assertEqual(result["session"]["handle"], "ses_new")

    def test_full_dispatch_passes_continuation_to_adapter(self) -> None:
        # MB-GRILL-029: the validated continuation must cross the adapter
        # boundary, not stop at request validation.
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        payload = self._payload(request, session={"form": "resume", "handle": "ses_ok"})
        result, runner = self._full_dispatch(request, payload)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(runner.requests), 1)
        self.assertEqual(
            runner.requests[0].get("continuation"), {"form": "resume", "handle": "ses_ok"}
        )
        self.assertTrue(result["session"]["verified"])

    def test_full_dispatch_rejects_backend_without_declared_form(self) -> None:
        # mcp-review in the checked-in fixture declares only the default
        # ["initial"]; a resume request must be rejected before reaching the
        # adapter (MB-GRILL-029).
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        registry, policy = _configuration()
        policy["roles"]["strong-reviewer"]["backends"] = ["mcp-review"]
        runner = BackendScriptRunner({"mcp-review": self._payload(request)})
        result = ROUTER.dispatch_review(request, registry, policy, runner)
        self.assertEqual(result["status"], "BLOCKED")
        # Sole chain member rejected for the undeclared form -> no candidate
        # left, so the terminal category is all_backends_unavailable.
        self.assertEqual(result["failure_category"], "all_backends_unavailable")
        self.assertEqual(runner.calls, [])

    def test_full_dispatch_rejects_unreadable_result_schema(self) -> None:
        request = self._request()
        bad = self._payload(request)
        bad["schema"] = "dd-review-result/0"
        result, _ = self._full_dispatch(request, bad)
        self.assertEqual(result["status"], "BLOCKED")


    def test_plain_dispatch_has_no_session_identity(self) -> None:
        request = self._request()
        result, category = self._normalize(request, self._payload(request))
        self.assertIsNone(category)
        self.assertEqual(result["status"], "PASS")
        self.assertIsNone(result.get("session"))

    def test_resume_without_result_session_blocked(self) -> None:
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        result, category = self._normalize(request, self._payload(request))
        self.assertIsNone(result)
        self.assertEqual(category, "session_resume_mismatch")

    def test_resume_with_initial_result_form_blocked(self) -> None:
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        payload = self._payload(request, session={"form": "initial", "handle": "ses_ok"})
        result, category = self._normalize(request, payload)
        self.assertIsNone(result)
        self.assertEqual(category, "session_resume_mismatch")

    def test_resume_with_mismatched_handle_blocked(self) -> None:
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        payload = self._payload(request, session={"form": "resume", "handle": "ses_other"})
        result, category = self._normalize(request, payload)
        self.assertIsNone(result)
        self.assertEqual(category, "session_resume_mismatch")

    def test_resume_with_matching_identity_verified(self) -> None:
        request = self._request(continuation={"form": "resume", "handle": "ses_ok"})
        payload = self._payload(request, session={"form": "resume", "handle": "ses_ok"})
        result, category = self._normalize(request, payload)
        self.assertIsNone(category)
        self.assertEqual(result["status"], "PASS")
        self.assertIsNotNone(result.get("session"))
        self.assertEqual(result["session"]["form"], "resume")
        self.assertEqual(result["session"]["handle"], "ses_ok")
        self.assertTrue(result["session"]["verified"])

    def test_explicit_initial_without_session_blocked(self) -> None:
        # MB-GRILL-030: an EXPLICIT initial form must yield a persistable
        # handle; otherwise the stateful loop has nothing to resume into.
        request = self._request(continuation={"form": "initial"})
        result, category = self._normalize(request, self._payload(request))
        self.assertIsNone(result)
        self.assertEqual(category, "session_resume_mismatch")

    def test_explicit_initial_with_session_verified(self) -> None:
        request = self._request(continuation={"form": "initial"})
        payload = self._payload(request, session={"form": "initial", "handle": "ses_new"})
        result, category = self._normalize(request, payload)
        self.assertIsNone(category)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["session"]["form"], "initial")
        self.assertEqual(result["session"]["handle"], "ses_new")
        self.assertTrue(result["session"]["verified"])


if __name__ == "__main__":
    unittest.main()

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


def _backend(backend_type: str = "cli", execution: str = "external") -> Dict[str, Any]:
    return {
        "type": backend_type,
        "execution": execution,
        "executable": sys.executable,
        "command": ["-c", "pass"],
        "capabilities": ["strong-review"],
        "readonly_required": True,
        "readonly_mode": "single-review-request" if backend_type == "mcp" else "test-readonly",
        "availability_exit_codes": [69],
        "transient_exit_codes": [75],
        "result_schema": ROUTER.RESULT_SCHEMA,
    }


def _configuration() -> tuple[Dict[str, Any], Dict[str, Any]]:
    registry = {
        "schema": ROUTER.CONFIG_SCHEMA,
        "result_schema": ROUTER.RESULT_SCHEMA,
        "backends": {
            "mcp-review": _backend("mcp", "external"),
            "codex-cli": _backend("cli", "external"),
            "codex-native": {
                **_backend("native", "native-agent"),
                "host": "codex",
                "native_guard": "codex-route-guard",
                "router_selectable": False,
            },
            "opencode-cli": _backend("cli", "external"),
            "opencode-native": {
                **_backend("native", "native-agent"),
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
                    "mode": "single-review-request",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-mcp-read-only",
                },
                {
                    "backend": "codex-cli",
                    "mode": "test-readonly",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-codex-read-only",
                },
                {
                    "backend": "codex-native",
                    "mode": "test-readonly",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-codex-native-read-only",
                },
                {
                    "backend": "opencode-cli",
                    "mode": "test-readonly",
                    "level": "L6",
                    "confirmed": True,
                    "source": "test-opencode-read-only",
                },
                {
                    "backend": "opencode-native",
                    "mode": "test-readonly",
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
            "mcp-review": self.result("mcp-review", request),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["backend"], "mcp-review")
        self.assertEqual(runner.calls, ["mcp-review"])
        self.assertEqual(result["routing"]["dispatch_boundary"], "single-backend")

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
            "change_risk": "behavioral",
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

    def test_readonly_violation_is_fail_closed(self) -> None:
        request = self.request()
        runner = BackendScriptRunner({
            "mcp-review": self.result("mcp-review", request, readonly_confirmation={"confirmed": False}),
            "codex-cli": self.result("codex-cli", request),
            "codex-native": self.result("codex-native", request),
        })
        result = self.dispatch(request, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "readonly_violation")
        self.assertEqual(runner.calls, ["mcp-review"])

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


if __name__ == "__main__":
    unittest.main()

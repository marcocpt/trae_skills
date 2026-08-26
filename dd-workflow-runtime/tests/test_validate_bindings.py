#!/usr/bin/env python3
"""Regression tests for the DD-008 model-bindings validator."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "agents" / "validate-bindings.py"
SPEC = importlib.util.spec_from_file_location("validate_bindings", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VB)

EXPECTED_MODEL = "opencode/x-preview-f-free"


def opencode_bindings() -> dict:
    return {
        "opencode": {
            "worker": {
                "model": EXPECTED_MODEL,
                "binding": "primary-session",
            },
            "reviewer": {
                "file": "opencode/strong-reviewer.md",
                "model": EXPECTED_MODEL,
                "permission_default_deny": True,
                "readonly_allows": ["read", "glob", "grep", "list"],
            },
        }
    }


class CheckOpenCodeSameModelTests(unittest.TestCase):
    def test_canonical_fixture_passes(self) -> None:
        self.assertEqual(VB.check_opencode_same_model(opencode_bindings()), [])

    def test_worker_model_drift_is_rejected(self) -> None:
        bindings = opencode_bindings()
        bindings["opencode"]["worker"]["model"] = "opencode/hy3-free"
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(any("opencode/worker" in e and "model" in e for e in errors))

    def test_reviewer_model_drift_is_rejected(self) -> None:
        bindings = opencode_bindings()
        bindings["opencode"]["reviewer"]["model"] = "deepseek/deepseek-reasoner"
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(any("opencode/reviewer" in e and "model" in e for e in errors))

    def test_missing_default_deny_is_rejected(self) -> None:
        bindings = opencode_bindings()
        del bindings["opencode"]["reviewer"]["permission_default_deny"]
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(any("permission_default_deny" in e for e in errors))

    def test_extra_readonly_allow_is_rejected(self) -> None:
        bindings = opencode_bindings()
        bindings["opencode"]["reviewer"]["readonly_allows"] = ["read", "glob", "grep", "list", "bash"]
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(any("readonly_allows" in e for e in errors))

    def test_worker_inheriting_reviewer_readonly_markers_is_rejected(self) -> None:
        bindings = opencode_bindings()
        bindings["opencode"]["worker"]["permission_default_deny"] = True
        bindings["opencode"]["worker"]["readonly_allows"] = ["read"]
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(any("角色隔离" in e for e in errors))

    def test_role_swap_is_rejected(self) -> None:
        bindings = opencode_bindings()
        swapped = bindings["opencode"]["worker"]
        bindings["opencode"]["worker"] = bindings["opencode"]["reviewer"]
        bindings["opencode"]["reviewer"] = swapped
        errors = VB.check_opencode_same_model(bindings)
        self.assertTrue(errors)

    def test_fileless_worker_without_binding_marker_is_rejected_by_check_native(self) -> None:
        bindings = {
            "codex": {},
            "zcode": {},
            "qoder": {},
            "codebuddy": {},
            "trae": {},
            "opencode": {"worker": {"model": EXPECTED_MODEL}, "reviewer": {}},
        }
        bindings["opencode"]["reviewer"] = opencode_bindings()["opencode"]["reviewer"]
        errors = VB.check_native(bindings)
        self.assertTrue(any("binding: primary-session" in e for e in errors))

    def test_real_canonical_loads_and_passes_all_checks(self) -> None:
        bindings = VB.load_bindings(VB.AGENTS_DIR / "model-bindings.yaml")
        self.assertEqual(VB.check_native(bindings), [])
        self.assertEqual(VB.check_opencode_same_model(bindings), [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Regression tests for the DD-008 model-bindings validator."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "agents" / "validate-bindings.py"
SPEC = importlib.util.spec_from_file_location("validate_bindings", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VB)

EXPECTED_MODEL = "opencode/muse-spark-1.2-contributor-free"

SUBAGENT_PROFILE = """---
description: native subagent profile
mode: subagent
model: opencode/muse-spark-1.2-contributor-free
permission:
  "*": deny
  read: allow
  glob: allow
  grep: allow
  list: allow
---

body
"""

PRIMARY_PROFILE = """---
description: external cli invocation profile
mode: primary
model: opencode/muse-spark-1.2-contributor-free
permission:
  "*": deny
  read: allow
  glob: allow
  grep: allow
  list: allow
---

body
"""

REGISTRY_TEMPLATE = """schema: dd-review-backends/1

backends:
  mcp-review:
    type: mcp
    command: [review]

  opencode-cli:
    type: cli
    command: [run, --agent, {target}, --format, json]
    forbid_args: [--auto]

  codex-native:
    type: native
    command: [exec, --sandbox, read-only]
"""


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
                "cli_agent_file": "opencode/strong-reviewer-cli.md",
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
        self.assertEqual(VB.check_opencode_cli_agent(bindings), [])


class CheckOpenCodeCliAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.agents_dir = Path(self.temp.name)
        (self.agents_dir / "opencode").mkdir()
        (self.agents_dir / "opencode" / "strong-reviewer.md").write_text(SUBAGENT_PROFILE)
        (self.agents_dir / "opencode" / "strong-reviewer-cli.md").write_text(PRIMARY_PROFILE)
        (self.agents_dir / "review-backends.yaml").write_text(
            REGISTRY_TEMPLATE.format(target="strong-reviewer-cli")
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_check(self, bindings: dict | None = None) -> list[str]:
        with mock.patch.object(VB, "AGENTS_DIR", self.agents_dir), mock.patch.object(
            VB, "OPENCODE_REGISTRY", self.agents_dir / "review-backends.yaml"
        ):
            return VB.check_opencode_cli_agent(bindings or opencode_bindings())

    def test_valid_primary_profile_passes(self) -> None:
        self.assertEqual(self.run_check(), [])

    def test_registry_pointing_back_at_subagent_is_rejected(self) -> None:
        (self.agents_dir / "review-backends.yaml").write_text(
            REGISTRY_TEMPLATE.format(target="strong-reviewer")
        )
        errors = self.run_check()
        self.assertTrue(any("mode 必须是 primary" in e for e in errors))
        self.assertTrue(any("不一致" in e for e in errors))

    def test_cli_agent_with_wrong_model_is_rejected(self) -> None:
        path = self.agents_dir / "opencode" / "strong-reviewer-cli.md"
        path.write_text(PRIMARY_PROFILE.replace(EXPECTED_MODEL, "opencode/hy3-free"))
        errors = self.run_check()
        self.assertTrue(any("model 必须与 canonical reviewer 一致" in e for e in errors))

    def test_cli_agent_without_default_deny_is_rejected(self) -> None:
        path = self.agents_dir / "opencode" / "strong-reviewer-cli.md"
        path.write_text(PRIMARY_PROFILE.replace('  "*": deny\n', ""))
        errors = self.run_check()
        self.assertTrue(any('缺默认拒绝' in e for e in errors))

    def test_cli_agent_with_extra_write_allow_is_rejected(self) -> None:
        path = self.agents_dir / "opencode" / "strong-reviewer-cli.md"
        path.write_text(PRIMARY_PROFILE.replace("  list: allow", "  list: allow\n  write: allow"))
        errors = self.run_check()
        self.assertTrue(any("只读放行必须精确为" in e for e in errors))

    def test_missing_cli_agent_file_is_rejected(self) -> None:
        (self.agents_dir / "opencode" / "strong-reviewer-cli.md").unlink()
        errors = self.run_check()
        self.assertTrue(any("缺少产物" in e for e in errors))

    def test_native_profile_flipped_to_primary_is_rejected(self) -> None:
        path = self.agents_dir / "opencode" / "strong-reviewer.md"
        path.write_text(SUBAGENT_PROFILE.replace("mode: subagent", "mode: primary"))
        errors = self.run_check()
        self.assertTrue(any("必须保持 mode: subagent" in e for e in errors))

    def test_cli_agent_file_declaration_mismatch_is_rejected(self) -> None:
        bindings = opencode_bindings()
        bindings["opencode"]["reviewer"]["cli_agent_file"] = "opencode/other-profile.md"
        errors = self.run_check(bindings)
        self.assertTrue(any("不一致" in e for e in errors))

    def test_registry_without_agent_flag_is_rejected(self) -> None:
        (self.agents_dir / "review-backends.yaml").write_text(
            "backends:\n  opencode-cli:\n    command: [run, --format, json]\n"
        )
        errors = self.run_check()
        self.assertTrue(any("缺少 --agent" in e for e in errors))


if __name__ == "__main__":
    unittest.main()

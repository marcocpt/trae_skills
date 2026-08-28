#!/usr/bin/env python3
"""Contract tests for the shared CI / test-location cleanup (AC-10, AC-11).

These tests are red while ci.md/test-location.md still contain legacy
step numbers, Macim names, fixed workflow names, and unconditional push
language; they go green after Task 5 lands the generic contracts.
"""
from __future__ import annotations

import unittest
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]

CI = RUNTIME_ROOT / "references" / "ci.md"
TEST_LOCATION = RUNTIME_ROOT / "references" / "test-location.md"
CI_XCODE = RUNTIME_ROOT / "references" / "ci-xcode.md"
REFACTOR_SKILL = RUNTIME_ROOT.parent / "dd-ai-refactor-workflow" / "SKILL.md"
REFACTOR_VERIFY = (
    RUNTIME_ROOT.parent / "dd-ai-refactor-workflow" / "references" /
    "verification-and-delivery.md"
)

LEGACY_STEP = r"1\.2\.5|4\.5b|5\.5|8\.2\.1"
LEGACY_NAMES = r"Macim|MacimApp|macos-ci\.yml|macos-xcuitest\.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestNoLegacyStepNumbers(unittest.TestCase):
    """AC-10: ci.md and test-location.md must not carry old feature/bug steps."""

    def _assert_no_legacy_step(self, path: Path):
        text = read(path)
        self.assertNotRegex(text, LEGACY_STEP,
                            f"{path.name} must not contain legacy step numbers (AC-10)")

    def test_ci_md_no_legacy_steps(self):
        self._assert_no_legacy_step(CI)

    def test_test_location_md_no_legacy_steps(self):
        self._assert_no_legacy_step(TEST_LOCATION)


class TestNoLegacyNames(unittest.TestCase):
    """AC-10: no Macim / fixed workflow names in shared contracts."""

    def _assert_no_legacy_names(self, path: Path):
        text = read(path)
        self.assertNotRegex(text, LEGACY_NAMES,
                            f"{path.name} must not contain Macim/fixed workflow (AC-10)")

    def test_ci_md_no_legacy_names(self):
        self._assert_no_legacy_names(CI)

    def test_test_location_md_no_legacy_names(self):
        self._assert_no_legacy_names(TEST_LOCATION)


class TestExternalGitRequiresAuthorization(unittest.TestCase):
    """AC-10: external Git action requires delivery_authorization."""

    def test_ci_md_external_git_requires_authorization(self):
        text = read(CI)
        self.assertIn("delivery_authorization", text,
                      "ci.md must tie external git push to delivery_authorization (AC-10)")


class TestCIEvidenceBindsExactSha(unittest.TestCase):
    """AC-10: CI evidence binds exact SHA."""

    def test_ci_md_evidence_binds_exact_sha(self):
        text = read(CI)
        self.assertIn("SHA", text,
                      "ci.md must bind CI evidence to exact SHA (AC-10)")


class TestLocalDiagnosisCannotCloseRemoteGate(unittest.TestCase):
    """AC-10: local diagnosis cannot close required remote CI Gate."""

    def test_ci_md_local_diagnosis_cannot_close_remote_gate(self):
        text = read(CI)
        self.assertIn("只用于理解失败原因或收集诊断", text,
                      "ci.md must scope local diagnosis to failure understanding (AC-10)")
        self.assertIn("不能关闭必需远端 CI Gate", text,
                      "ci.md must forbid local diagnosis closing remote CI Gate (AC-10)")
        self.assertIn("禁止本地测试作为 CI 替代", text,
                      "ci.md must forbid local testing as CI substitute (AC-10)")


class TestCIXcodeAdapterGeneric(unittest.TestCase):
    """AC-10: ci-xcode.md must be generic and prefer project docs/scripts."""

    def test_ci_xcode_exists_and_generic(self):
        self.assertTrue(CI_XCODE.exists(),
                        "ci-xcode.md must exist (AC-10)")
        text = read(CI_XCODE)
        self.assertIn("AGENTS.md", text,
                      "ci-xcode.md must prefer project AGENTS.md/scripts (AC-10)")
        self.assertNotRegex(text, LEGACY_NAMES,
                            "ci-xcode.md must not hardcode Macim/fixed scheme (AC-10)")


class TestRefactorNoUnconditionalPush(unittest.TestCase):
    """AC-11/AC-10: refactor must not require push after every commit."""

    def test_refactor_skill_no_unconditional_push(self):
        text = read(REFACTOR_SKILL) + "\n" + read(REFACTOR_VERIFY)
        self.assertNotRegex(text, r"每个 Commit 后.*push",
                            "Refactor must not require push after every commit (AC-10)")
        self.assertIn("delivery_authorization", text,
                      "Refactor must gate push on delivery_authorization (AC-10)")


class TestCIHardeningContracts(unittest.TestCase):
    """R5-001/R5-002/R-009: CI trigger/user bypass/workflow selector contracts."""

    def test_ci_trigger_failure_cannot_fall_back_to_local_final(self):
        ci = read(CI)
        test_loc = read(TEST_LOCATION)
        # trigger failure must not enter the local-final closed list.
        self.assertIn("CI 触发失败（`gh workflow run` 报错、分支未 push、鉴权失败等）不进入此封闭列表",
                      ci,
                      "ci.md must exclude CI trigger failure from local-final closed list (R-007)")
        self.assertIn("CI 触发失败（分支未 push、`gh workflow run` 报错、鉴权失败等）不进入本封闭列表",
                      test_loc,
                      "test-location must exclude CI trigger failure from local-final (R-007/R5-002)")
        # local-final closed list must NOT include trigger-failure + user-local option.
        self.assertNotIn("无可用 CI 结果且 CI 触发失败且用户明确选择本地",
                         ci,
                         "ci.md local-final closed list must not contain trigger-failure option (R-007)")

    def test_user_request_cannot_bypass_required_remote_ci(self):
        ci = read(CI)
        test_loc = read(TEST_LOCATION)
        # scene 4 must not allow "user request" alone to downgrade.
        self.assertNotIn("仅当 CI 不可用或用户明确要求", ci,
                         "ci.md scene 4 must not allow user-request downgrade (R5-001)")
        self.assertIn("用户要求不凌驾 CI 优先", ci,
                      "ci.md must keep user-request-does-not-override rule (R5-001)")
        self.assertIn("用户明确要求\"不凌驾于 CI 优先之上", test_loc,
                      "test-location must keep user-request-does-not-override rule (R5-001)")

    def test_workflow_selector_is_shared_by_all_scenarios(self):
        ci = read(CI)
        self.assertIn("工作流选择器（所有场景共用）", ci,
                      "ci.md must define workflow selector as shared pre-step (R-008/R5-002)")
        self.assertIn("场景 1-4 全部复用同一解析值", ci,
                      "ci.md must state scenarios 1-4 reuse the same selector (R-008)")

    def test_gh_unavailable_not_equal_remote_ci_absent(self):
        test_loc = read(TEST_LOCATION)
        self.assertIn("remote_ci_required", test_loc,
                      "test-location must distinguish remote_ci_required (R5-002)")
        self.assertIn("ci_control_available", test_loc,
                      "test-location must distinguish ci_control_available (R5-002)")
        self.assertNotIn("gh 命令不可用且用户在 AskUserQuestion 中选择不修复鉴权",
                         test_loc.split("### 3.")[1].split("运行项目对应")[0],
                         "gh-unavailable must not be listed as local-final condition (R5-002)")


if __name__ == "__main__":
    unittest.main()

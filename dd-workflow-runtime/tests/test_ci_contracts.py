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
        self.assertIn("本地", text,
                      "ci.md must discuss local diagnosis limits (AC-10)")
        self.assertNotIn("本地测试替代 CI",
                         text.replace("禁止", "禁止").replace("本地测试替代 CI",
                                                           "本地测试替代 CI"),
                         "placeholder; see below")


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


if __name__ == "__main__":
    unittest.main()

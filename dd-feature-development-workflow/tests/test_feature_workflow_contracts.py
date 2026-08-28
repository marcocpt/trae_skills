#!/usr/bin/env python3
"""Contract tests for dd-feature-development-workflow token-efficient refactor.

These tests assert the *target* contracts defined in the refactor plan
(AC-01 .. AC-14). They are red while the legacy SKILL.md / references are
still in place, and go green as tasks 2-6 land the new schema and Stage split.
"""
from __future__ import annotations

import unittest
from pathlib import Path

WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = WORKFLOW_ROOT.parent / "dd-workflow-runtime"

SKILL = WORKFLOW_ROOT / "SKILL.md"
ARTIFACT = RUNTIME_ROOT / "references" / "artifact-contract.md"
REVIEW_GATE = RUNTIME_ROOT / "references" / "review-gate.md"
CANDIDATE = WORKFLOW_ROOT / "references" / "candidate.md"
DELIVERY = WORKFLOW_ROOT / "references" / "delivery-and-closure.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestStageOrderDocumentationBeforeCandidate(unittest.TestCase):
    """AC-07: Documentation completes before candidate freeze."""

    def test_stage_order_documentation_before_candidate(self):
        text = read(SKILL)
        # In the new fixed order: documentation precedes final-candidate.
        impl = text.find("implementation")
        doc = text.find("documentation")
        cand = text.find("final-candidate")
        for name, pos in (("implementation", impl), ("documentation", doc),
                          ("final-candidate", cand)):
            self.assertNotEqual(pos, -1,
                                f"{name} not found in SKILL.md Stage order (AC-07)")
        self.assertLess(impl, doc, "documentation must come after implementation (AC-07)")
        self.assertLess(doc, cand, "documentation must precede final-candidate (AC-07)")


class TestCandidateDoesNotPromoteTarget(unittest.TestCase):
    """AC-08: Candidate Gate produces a candidate without updating target branch."""

    def test_candidate_does_not_promote_target(self):
        text = read(CANDIDATE)
        self.assertIn("candidate_ready", text,
                      "Candidate output must expose candidate_ready (AC-08)")
        # Candidate must NOT promote develop/main itself.
        self.assertIn("Candidate Gate 不更新 develop/main", text,
                      "Candidate must not promote develop/main (AC-08)")


class TestDeliveryPromotesExactCandidateSha(unittest.TestCase):
    """AC-09: Delivery only promotes the exact candidate SHA."""

    def test_delivery_promotes_exact_candidate_sha(self):
        text = read(DELIVERY)
        self.assertIn("delivery_authorization", text,
                      "delivery_authorization must be kept independently (AC-09)")
        self.assertIn("candidate_sha", text,
                      "Delivery must reference candidate_sha (AC-09)")
        self.assertIn("review_sha == gap_sha == ci_sha == candidate_sha", text,
                      "Delivery must enforce exact-SHA invariant (AC-09)")


class TestPhaseReadsAnchorsNotFullSpecs(unittest.TestCase):
    """AC-05: Phase reads anchors/global constraints, not full spec re-read."""

    def test_phase_reads_anchors_not_full_specs(self):
        text = read(SKILL)
        # New phase contract reads anchors, not the entire approved spec.
        self.assertIn("anchors", text,
                      "Phase must read anchors (AC-05)")
        self.assertNotIn("完整读取该包引用的批准原始规格", text,
                         "Phase must NOT re-read full approved spec (AC-05)")


class TestCandidateRequiresFrozenReviewAndFullGap(unittest.TestCase):
    """AC-08: Candidate requires frozen standard review and full-spec gap."""

    def test_candidate_requires_frozen_standard_review_and_full_gap(self):
        text = read(CANDIDATE)
        self.assertIn("review_level", text,
                      "Candidate review must fix review_level (AC-08)")
        self.assertIn("full_spec_gap", text,
                      "Candidate review must produce full_spec_gap (AC-08)")


class TestCompactVerificationKeepsInvariants(unittest.TestCase):
    """AC-04: compact verification keeps coverage/run/bindings/validity."""

    def test_compact_verification_keeps_coverage_run_bindings_validity(self):
        text = read(ARTIFACT)
        for key in ("coverage", "runs", "bindings", "validity"):
            self.assertIn(key, text,
                          f"verification must keep '{key}' (AC-04)")


class TestMainSkillRoutesEveryReferenceDirectly(unittest.TestCase):
    """AC-01/AC-02: main SKILL.md routes each Stage reference one hop away."""

    def test_main_skill_routes_every_reference_directly(self):
        skill = read(SKILL)
        expected_refs = [
            "state-and-handoff.md",
            "intake-and-environment.md",
            "specification.md",
            "planning-stage.md",
            "implementation.md",
            "documentation.md",
            "candidate.md",
        ]
        for ref in expected_refs:
            self.assertIn(ref, skill,
                          f"SKILL.md must route {ref} directly (AC-02)")


class TestRetiredReferencesHaveNoActiveLinks(unittest.TestCase):
    """AC-13: retired references must not be linked from active paths."""

    def test_retired_references_have_no_active_links(self):
        skill = read(SKILL)
        for retired in ("specification-and-planning.md",
                        "implementation-and-verification.md"):
            self.assertNotIn(retired, skill,
                             f"SKILL.md must not route retired {retired} (AC-13)")


if __name__ == "__main__":
    unittest.main()

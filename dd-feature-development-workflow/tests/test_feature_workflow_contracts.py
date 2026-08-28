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
DOCUMENTATION = WORKFLOW_ROOT / "references" / "documentation.md"
STATE = RUNTIME_ROOT / "references" / "state.md"
STATE_AND_HANDOFF = WORKFLOW_ROOT / "references" / "state-and-handoff.md"
IMPLEMENTATION = WORKFLOW_ROOT / "references" / "implementation.md"


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
        delivery = read(DELIVERY)
        candidate = read(CANDIDATE)
        self.assertIn("delivery_authorization", delivery,
                      "delivery_authorization must be kept independently (AC-09)")
        self.assertIn("candidate_sha", delivery,
                      "Delivery must reference candidate_sha (AC-09)")
        self.assertIn("review_sha == gap_sha == ci_sha == candidate_sha", delivery,
                      "Delivery must enforce exact-SHA invariant (AC-09)")
        # candidate.md must emit structured exact-SHA fields for consumption.
        self.assertIn("full_ci_run.head_sha", candidate,
                      "candidate.md must bind full_ci_run.head_sha to candidate_sha (R-001)")
        self.assertIn("candidate_review.sha", candidate,
                      "candidate.md must bind review to candidate_sha (R-001)")
        self.assertIn("full_spec_gap.sha", candidate,
                      "candidate.md must bind gap to candidate_sha (R-001)")
        # closure must consume the same fields (cross-file producer/consumer).
        self.assertIn("full_ci_run.head_sha", delivery,
                      "closure must consume full_ci_run.head_sha (R-001)")

    def test_documentation_gate_owned_by_documentation_reference(self):
        doc = read(DOCUMENTATION)
        delivery = read(DELIVERY)
        # final-candidate transition is owned by documentation.md, not delivery.
        self.assertIn("current_stage=final-candidate", doc,
                      "documentation.md must own the final-candidate Gate (R-003)")
        self.assertNotIn("current_stage=final-candidate", delivery,
                         "delivery-and-closure.md must not own the documentation Gate (R-003)")


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


class TestStateProducerConsumerConsistent(unittest.TestCase):
    """R-001/R-004: shared state.md producer must match feature schema consumer."""

    def test_state_md_no_legacy_candidate_fields(self):
        state = read(STATE)
        self.assertNotIn("final_ci_passed", state,
                         "state.md producer must not write legacy final_ci_passed (R-001)")
        self.assertNotIn("merge_in_progress", state,
                         "state.md producer must not write legacy merge_in_progress (R-004)")
        self.assertIn("full_ci_run", state,
                      "state.md producer must write structured full_ci_run (R-001)")
        self.assertIn("full_ci_passed", state,
                      "state.md producer must write full_ci_passed (R-001)")

    def test_feature_state_uses_in_progress_not_booleans(self):
        handoff = read(STATE_AND_HANDOFF)
        self.assertIn("in_progress", handoff,
                      "feature state must reuse runtime in_progress (R-004)")
        self.assertNotIn("merge_in_progress", handoff,
                         "feature state must not define boolean merge_in_progress (R-004)")
        self.assertNotIn("cleanup_in_progress", handoff,
                         "feature state must not define boolean cleanup_in_progress (R-004)")

    def test_integration_gate_binds_implementation_digest_not_candidate_sha(self):
        impl = read(IMPLEMENTATION)
        self.assertIn("integration_verification.bindings.implementation_digest", impl,
                      "Integration Gate must bind implementation digest, not candidate_sha (R-005)")
        self.assertNotIn("integration_ci_run.head_sha == candidate_sha", impl,
                         "Integration Gate must not reference candidate_sha before freeze (R-005)")

    def test_feature_closure_keeps_state_until_after_cleanup(self):
        state = read(STATE)
        delivery = read(DELIVERY)
        # state.md must not delete feature state immediately after merge.
        self.assertIn("feature-development", state,
                      "state.md must branch deletion by WORKFLOW_TYPE (R4-001)")
        self.assertIn("禁止在 Closure 校验与 Receipt 写入前删除", state,
                      "state.md must forbid deleting feature state before Closure (R4-001)")
        # closure writes Receipt and cleanup in_progress before deleting state.
        self.assertIn("Completion Receipt", delivery,
                      "delivery must write Completion Receipt during Closure (R4-001)")
        self.assertIn("operation: cleanup", delivery,
                      "delivery must write cleanup in_progress before state disposal (R4-001)")

    def test_legacy_stage_mapping_matches_stage_graph(self):
        handoff = read(STATE_AND_HANDOFF)
        # legacy mapping must follow new Stage order: impl → doc → final-candidate → confirmation.
        mapping_block = handoff.split("legacy `current_step` mapping")[1]
        self.assertIn("4 / 4.x → implementation", mapping_block,
                      "legacy mapping must keep implementation at 4 (R4-002)")
        self.assertIn("5 / 5.x → documentation", mapping_block,
                      "legacy mapping must map documentation to 5, before final-candidate (R4-002)")
        self.assertIn("6 / 6.x → final-candidate", mapping_block,
                      "legacy mapping must map final-candidate to 6 (R4-002)")
        self.assertIn("7 → confirmation", mapping_block,
                      "legacy mapping must map confirmation to 7 (R4-002)")
        self.assertIn("不得用于排序或推进", mapping_block,
                      "legacy current_step must be label-only, not for ordering (R4-002)")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Contract tests for the shared fast-track contract (dd-workflow-runtime).

The contract is the single owner of the fast-track semantics shared by
`dd-feature-fast-track` and `dd-bug-fast-track`: two lanes, the deferral
ledger schema, backfill order, recovery and red lines.
"""
from __future__ import annotations

import unittest
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = RUNTIME_ROOT.parent

CONTRACT = RUNTIME_ROOT / "references" / "fast-track-contract.md"
FEATURE_SKILL = SKILLS_ROOT / "dd-feature-fast-track" / "SKILL.md"
BUG_SKILL = SKILLS_ROOT / "dd-bug-fast-track" / "SKILL.md"

FEATURE_BACKFILL = SKILLS_ROOT / "dd-feature-fast-track" / "references" / "backfill.md"
BUG_BACKFILL = SKILLS_ROOT / "dd-bug-fast-track" / "references" / "backfill.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestContractIsSingleOwner(unittest.TestCase):
    """The contract owns fast-track semantics; domain skills must route, not copy."""

    def test_contract_declares_single_ownership(self):
        text = read(CONTRACT)
        self.assertIn("唯一拥有", text,
                      "contract must declare single ownership of fast-track semantics")

    def test_both_domain_skills_route_to_the_contract(self):
        for path, name in ((FEATURE_SKILL, "dd-feature-fast-track"),
                           (BUG_SKILL, "dd-bug-fast-track")):
            self.assertIn("fast-track-contract", read(path),
                          f"{name} must route to the shared contract, not redefine it")

    def test_domain_skills_do_not_inline_the_ledger_schema(self):
        for path, name in ((FEATURE_SKILL, "dd-feature-fast-track"),
                           (BUG_SKILL, "dd-bug-fast-track")):
            self.assertNotIn("close_evidence", read(path),
                             f"{name} must not inline the debt ledger schema (single owner)")

    def test_both_backfill_references_route_to_the_contract(self):
        for path, name in ((FEATURE_BACKFILL, "feature backfill"),
                           (BUG_BACKFILL, "bug backfill")):
            self.assertIn("fast-track-contract", read(path),
                          f"{name} must route backfill order to the shared contract")


class TestTwoLanes(unittest.TestCase):
    """Fast track is two lanes, and Track B is not optional."""

    def test_contract_defines_both_lanes(self):
        text = read(CONTRACT)
        self.assertIn("Track A", text, "contract must define Track A (fast track)")
        self.assertIn("Track B", text, "contract must define Track B (backfill)")

    def test_track_b_is_mandatory(self):
        text = read(CONTRACT)
        self.assertIn("没有\"到此为止\"分支", text,
                      "backfill must be mandatory after fast track (no stop-after-A branch)")


class TestSingleAskPoint(unittest.TestCase):
    """Only one ask (requirement restatement); exactly four exceptions."""

    def test_only_one_ask_point(self):
        text = read(CONTRACT)
        self.assertIn("唯一询问点", text,
                      "fast track must keep exactly one ask point (restatement)")

    def test_exactly_four_interrupt_exceptions(self):
        text = read(CONTRACT)
        section = text.split("### 3.2", 1)[1].split("### 3.3", 1)[0]
        items = [ln for ln in section.splitlines() if ln.strip().startswith(("1.", "2.", "3.", "4."))]
        self.assertEqual(len(items), 4,
                         f"interrupt exceptions must be exactly four, got {items}")

    def test_no_confirmation_means_reread(self):
        text = read(CONTRACT)
        self.assertIn("不得默认已确认", text,
                      "unconfirmed restatement must be re-asked, never assumed")


class TestLedgerSchema(unittest.TestCase):
    """Deferred items become ledger entries with evidence-gated closure."""

    def test_ledger_schema_fields(self):
        text = read(CONTRACT)
        for field in ("debts:", "kind:", "why_deferred", "close_evidence",
                      "status:", "evidence:", "waive_reason"):
            self.assertIn(field, text, f"ledger schema must define '{field}'")

    def test_status_enum(self):
        text = read(CONTRACT)
        self.assertIn("open | closed | waived", text,
                      "ledger status enum must be open | closed | waived")

    def test_closure_requires_evidence(self):
        text = read(CONTRACT)
        self.assertIn("没有证据的关闭无效", text,
                      "closing a debt without evidence must be invalid")

    def test_no_waive_during_fast_track(self):
        text = read(CONTRACT)
        self.assertIn("速通阶段不得 waive", text,
                      "waiving is a backfill-stage, user-confirmed action only")

    def test_ledger_persisted_not_session_only(self):
        text = read(CONTRACT)
        self.assertIn("不得只存在于会话上下文", text,
                      "ledger must be persisted with state, not session-only")


class TestBackfillOrderAndBaseline(unittest.TestCase):
    """Backfill order is fixed; baseline is the confirmed requirement."""

    def test_backfill_order_is_fixed(self):
        text = read(CONTRACT)
        self.assertIn("顺序固定", text, "backfill order must be fixed")

    def test_backfill_baseline_is_requirement_not_implementation(self):
        text = read(CONTRACT)
        self.assertIn("基准是已确认的需求，不是实现现状", text,
                      "backfill must be based on the confirmed requirement")

    def test_upgrade_trigger_means_handoff(self):
        text = read(CONTRACT)
        self.assertIn("交接正式流程收尾", text,
                      "hitting an upgrade trigger must hand off, not degrade in fast track")

    def test_single_sha_binding(self):
        text = read(CONTRACT)
        self.assertIn("绑定同一个最终 SHA", text,
                      "backfill verification must bind one final SHA")


class TestRecovery(unittest.TestCase):
    """Recovery rules: missing ledger blocks, open debts continue, no restart."""

    def test_missing_ledger_blocks(self):
        text = read(CONTRACT)
        self.assertIn("BLOCKED", text,
                      "fast-track phase with an empty/missing ledger must be BLOCKED")

    def test_open_debts_do_not_roll_back(self):
        text = read(CONTRACT)
        self.assertIn("不回退速通结论", text,
                      "resuming backfill must not roll back the fast-track outcome")

    def test_missing_state_is_derived_from_evidence(self):
        text = read(CONTRACT)
        self.assertIn("不默认从头开始", text,
                      "missing state must be derived from repo evidence, not restarted")


class TestStateFields(unittest.TestCase):
    """Fast-track state increments runtime state; it does not fork it."""

    def test_incremental_state_fields(self):
        text = read(CONTRACT)
        for field in ("fast_track: true", "track_phase: fast-track | backfill",
                      "requirement_confirmed: true", "debts: []", "decisions: []",
                      "smoke_evidence: {}"):
            self.assertIn(field, text, f"state must carry '{field}'")

    def test_state_written_atomically(self):
        text = read(CONTRACT)
        self.assertIn("原子写入", text, "state must be written atomically per Gate")


class TestRedLines(unittest.TestCase):
    """Red lines that keep fast track from becoming a no-gate lane."""

    def test_core_red_lines(self):
        text = read(CONTRACT)
        for line in ("未复述需求就修改项目产物",
                     "省掉的产物不登记欠账",
                     "把速通产出解释为 commit、push、merge 或发布授权",
                     "状态未持久化就跨阶段"):
            self.assertIn(line, text, f"red line missing: {line}")

    def test_fast_track_pass_is_not_acceptance(self):
        text = read(CONTRACT)
        self.assertIn("不等于正式流程的任何 Gate 通过", text,
                      "fast-track success must not be presented as acceptance")

    def test_rationalization_table_present(self):
        text = read(CONTRACT)
        self.assertIn("合理化借口表", text,
                      "discipline contract must keep a rationalization table")


if __name__ == "__main__":
    unittest.main()

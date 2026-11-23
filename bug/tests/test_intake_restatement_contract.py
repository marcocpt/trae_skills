#!/usr/bin/env python3
"""Contract tests for the bug Intake restatement gate.

Locks the 2026-11-24 decision: restatement is mandatory and non-blocking.

- first entry into Intake must restate symptom / expected behaviour / scope to the user;
- when the three are clear and no unresolved product decision remains, restate then
  continue without waiting for confirmation;
- unclear, conflicting, behaviour-changing or high-risk work must get confirmation;
- resumed tasks reuse an existing confirmation and never restate again;
- `decisions` carries the record so the Gate is checkable after compaction.

Rationale: commit 9f9ebcc (2026-10-17) downgraded the gate to "conditional" and
nothing guarded it, so a silent regression was invisible to the test suite.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"
DIAG = SKILL_ROOT / "references" / "diagnosis-and-verification.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def h2_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    head_re = re.compile(rf"^## {re.escape(heading)}$")
    start = None
    for i, line in enumerate(lines):
        if start is None:
            if head_re.match(line):
                start = i + 1
        elif re.match(r"^#{1,2} ", line):
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"section not found: {heading}")
    return "\n".join(lines[start:])


class TestRestatementIsMandatory(unittest.TestCase):
    def test_router_requires_restating_the_three_parts_to_the_user(self):
        text = read(SKILL_MD)
        for token in ("向用户复述", "不得跳过", "复述即继续"):
            self.assertIn(token, text, f"bug router must state '{token}'")
        for part in ("症状", "期望行为", "修复范围"):
            self.assertIn(part, text, f"restatement must cover '{part}'")

    def test_reference_requires_the_restatement_before_log_scanning(self):
        text = read(DIAG)
        self.assertIn("不得跳过", text)
        self.assertIn("也不得推迟到诊断中段", text)
        self.assertIn("向用户复述三件事", text)

    def test_conditional_phrasing_cannot_come_back(self):
        for path in (SKILL_MD, DIAG):
            text = read(path)
            for banned in ("不机械复述", "确认依据已记录", "条件触发"):
                self.assertNotIn(
                    banned, text,
                    f"{path.name} must not reintroduce the downgraded phrasing '{banned}'",
                )


class TestRestatementDoesNotBlock(unittest.TestCase):
    def test_clear_case_continues_without_waiting(self):
        text = read(DIAG)
        self.assertIn("复述即继续", text)
        self.assertIn("不停下等确认", text)
        self.assertIn("用户可随时纠偏", text)
        clause = next(c for c in text.split("；") if "复述即继续" in c)
        self.assertNotIn("等待", clause, "the continue-immediately clause must not reintroduce waiting")
        self.assertNotRegex(
            clause, r"仍?需[^；]{0,10}确认",
            "the continue-immediately clause must not require any confirmation",
        )

    def test_old_wait_for_confirmation_sentence_is_gone(self):
        text = read(DIAG)
        self.assertNotIn("确认后再从当前 worktree", text)
        self.assertNotRegex(
            text, r"确认后[^。；]{0,40}扫描",
            "any 'confirm before scanning' variant reintroduces blocking",
        )

    def test_scope_of_the_no_ask_branch_is_product_decisions_only(self):
        for path in (SKILL_MD, DIAG):
            text = read(path)
            self.assertIn("产品决定", text, f"{path.name} must scope the branch to product decisions")
            self.assertNotRegex(
                text, r"无未解决决定",
                f"{path.name} must not use the unbounded '无未解决决定'",
            )


class TestConfirmationAndRecovery(unittest.TestCase):
    def test_unclear_or_risky_work_still_needs_confirmation(self):
        for path in (SKILL_MD, DIAG):
            text = read(path)
            for token in ("不清楚", "相互冲突", "行为变更", "高风险"):
                self.assertIn(token, text, f"{path.name} must keep '{token}' as a confirmation trigger")
            self.assertIn("取得用户确认", text, f"{path.name} must require confirmation")

    def test_gate_is_checkable_from_persisted_state(self):
        self.assertIn("已向用户复述并记入 `decisions`", read(DIAG))
        self.assertIn("或已复用有效确认", read(DIAG))
        self.assertIn("已向用户复述并记入 `decisions`", read(SKILL_MD))

    def test_resumed_tasks_reuse_the_confirmation(self):
        text = read(DIAG)
        self.assertIn("不重复复述", text)
        self.assertIn("`decisions` 中的确认记录", text)
        self.assertIn("有效 Handoff", text)


class TestRedLines(unittest.TestCase):
    def test_two_separate_red_lines(self):
        red = h2_section(read(SKILL_MD), "红线")
        bullets = [ln for ln in red.splitlines() if ln.startswith("- ")]
        restate = [b for b in bullets if "未向用户复述症状/期望/修复范围" in b]
        confirm = [b for b in bullets if "未取得用户确认就继续诊断或修复" in b]
        self.assertEqual(len(restate), 1, f"expected one restatement red line, got {restate}")
        self.assertEqual(len(confirm), 1, f"expected one confirmation red line, got {confirm}")
        self.assertNotEqual(
            restate[0], confirm[0],
            "the two red lines must stay separate bullets, not merge into one",
        )
        self.assertIn("清楚时复述即继续，不停下等二次确认", confirm[0])

    def test_red_line_exempts_confirmed_resume(self):
        red = h2_section(read(SKILL_MD), "红线")
        self.assertIn("恢复任务状态或有效 Handoff 已含有效确认的除外", red)


if __name__ == "__main__":
    unittest.main()

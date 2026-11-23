#!/usr/bin/env python3
"""Contract tests for the feature Intake restatement gate.

Locks the 2026-11-24 decision: restatement is mandatory and non-blocking.

- first entry into Intake must restate goal / IN-OUT scope / success criteria to the user;
- when those are clear and no unresolved product decision remains, restate then continue;
- unclear, conflicting, behaviour-changing or high-risk work must get confirmation;
- resumed tasks reuse an existing confirmation and never restate again;
- `decisions` carries the record;
- the requirements summary inherits its approval from that restatement and does not
  trigger a second, synonymous confirmation.

Rationale: commit 9f9ebcc (2026-10-17) downgraded the gate to "conditional" and
nothing guarded it, so a silent regression was invisible to the test suite.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"
INTAKE = SKILL_ROOT / "references" / "intake-and-environment.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def h3_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    head_re = re.compile(rf"^### {re.escape(heading)}$")
    start = None
    for i, line in enumerate(lines):
        if start is None:
            if head_re.match(line):
                start = i + 1
        elif re.match(r"^#{1,3} ", line):
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"section not found: {heading}")
    return "\n".join(lines[start:])


def intake_section(text: str) -> str:
    """Intake only: never let the Environment Gate satisfy an Intake assertion."""
    return text.split("## 1. Intake", 1)[1].split("## 2. Environment", 1)[0]


def intake_gate(text: str) -> str:
    return intake_section(text).split("Gate：", 1)[1]


class TestRestatementSection(unittest.TestCase):
    def test_section_is_mandatory_but_non_blocking(self):
        text = read(INTAKE)
        self.assertIn("### 复述（必做，不阻塞）", text)
        body = h3_section(text, "复述（必做，不阻塞）")
        for token in ("向用户用通俗语言复述", "不得跳过", "复述即继续", "用户可随时纠偏"):
            self.assertIn(token, body, f"restatement section must state '{token}'")

    def test_section_covers_the_three_parts(self):
        body = h3_section(read(INTAKE), "复述（必做，不阻塞）")
        for part in ("要解决什么问题", "范围边界", "怎么算成功"):
            self.assertIn(part, body, f"restatement must cover '{part}'")

    def test_conditional_phrasing_cannot_come_back(self):
        for path in (SKILL_MD, INTAKE):
            text = read(path)
            for banned in ("条件触发", "不机械复述", "确认依据已记录"):
                self.assertNotIn(
                    banned, text,
                    f"{path.name} must not reintroduce the downgraded phrasing '{banned}'",
                )


class TestConfirmationAndRecovery(unittest.TestCase):
    def test_unclear_or_risky_work_still_needs_confirmation(self):
        body = h3_section(read(INTAKE), "复述（必做，不阻塞）")
        for token in ("不清楚或仍不确定", "相互冲突", "行为变更", "高风险"):
            self.assertIn(token, body, f"restatement section must keep '{token}'")
        self.assertIn("必须取得用户确认", body)

    def test_resumed_tasks_reuse_the_confirmation(self):
        body = h3_section(read(INTAKE), "复述（必做，不阻塞）")
        self.assertIn("不重复复述", body)
        self.assertIn("有效 Bootstrap Handoff", body)

    def test_gate_is_checkable_from_persisted_state(self):
        gate = intake_gate(read(INTAKE))
        for token in ("已向用户复述并记入 `decisions`", "或已复用有效确认", "需确认情形已获确认"):
            self.assertIn(token, gate, f"Intake Gate must require '{token}'")

    def test_scope_is_product_decisions_only(self):
        for path in (SKILL_MD, INTAKE):
            text = read(path)
            self.assertIn("产品决定", text, f"{path.name} must scope the branch to product decisions")
            self.assertNotRegex(
                text, r"无未解决决定",
                f"{path.name} must not use the unbounded '无未解决决定'",
            )


class TestSummaryInheritsTheRestatement(unittest.TestCase):
    def test_summary_is_the_approval_basis(self):
        text = read(INTAKE)
        self.assertIn("Intake 复述即该范围需求事实的批准依据", text)
        self.assertIn("摘要未超出该范围时不再单独等确认", text)

    def test_summary_gate_scopes_the_restatement_range(self):
        gate = intake_gate(read(INTAKE))
        self.assertIn("摘要未超出 Intake 复述范围", gate)
        self.assertIn("三项及其直接推导、无新增语义的事实", gate)

    def test_synonymous_second_confirmation_is_gone(self):
        text = read(INTAKE)
        self.assertNotIn(
            "用户确认需求摘要", text,
            "a blanket 'user confirms the summary' gate re-blocks the clear case",
        )
        self.assertNotRegex(
            text, r"摘要[^。；]{0,12}需用户确认",
            "the summary must not require a second, synonymous confirmation",
        )


class TestRouterAndRedLines(unittest.TestCase):
    def test_router_step_one_points_at_the_user(self):
        text = read(SKILL_MD)
        for token in ("向用户用通俗语言复述需求", "不得跳过", "写入 `decisions`"):
            self.assertIn(token, text, f"fdev router must state '{token}'")

    def test_intake_row_accepts_reused_confirmation(self):
        text = read(SKILL_MD)
        self.assertIn("已向用户复述并记入 `decisions`，或已复用有效确认", text)

    def test_two_separate_red_lines(self):
        red = read(SKILL_MD).split("### 阶段纪律", 1)[1]
        bullets = [ln for ln in red.splitlines() if ln.startswith("- ")]
        restate = [b for b in bullets if "未向用户复述目标/范围/成功标准" in b]
        confirm = [b for b in bullets if "未取得用户确认就继续" in b]
        self.assertEqual(len(restate), 1, f"expected one restatement red line, got {restate}")
        self.assertEqual(len(confirm), 1, f"expected one confirmation red line, got {confirm}")
        self.assertNotEqual(
            restate[0], confirm[0],
            "the two red lines must stay separate bullets, not merge into one",
        )
        self.assertIn("清楚时复述即继续，不停下等二次确认", confirm[0])


if __name__ == "__main__":
    unittest.main()

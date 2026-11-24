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


class TestMutationGate(unittest.TestCase):
    """Files must not change before the user says GO; investigation stays open."""

    MUTATION_GATE = SKILL_ROOT.parent / "wrt" / "references" / "mutation-gate.md"
    WEAKENERS = ("建议", "可选", "尽量", "视情况", "不强制")

    def test_owner_reference_keeps_each_rule_body(self):
        self.assertTrue(self.MUTATION_GATE.exists(), "mutation-gate.md must own the rule")
        text = read(self.MUTATION_GATE)
        for heading in ("## 1. 触发点", "## 2. GO 必须说清三件事", "## 3. 复用与失效",
                        "## 4. 与 Intake 复述的关系", "## 5. 速通与其他工作流",
                        "## 6. 轻量文档路径", "## 7. 红线"):
            self.assertIn(heading, text)

        trigger = text.split("## 1. 触发点", 1)[1].split("## 2.", 1)[0]
        self.assertIn("不需要 GO", trigger, "investigation must stay open")
        self.assertIn("debug-logs/", trigger)
        self.assertIn("entry.md", trigger)
        self.assertIn("新建、尚未通过其批准 Gate", trigger, "draft exemption must stay narrow")

        body = text.split("## 2. GO 必须说清三件事", 1)[1].split("## 3.", 1)[0]
        items = [ln for ln in body.splitlines() if re.match(r"^\d\. ", ln)]
        self.assertEqual(len(items), 3, f"GO must keep exactly three items, got {items}")
        self.assertIn("路径或路径模式", items[0])
        self.assertIn("每个文件改成什么", items[1])
        self.assertIn("影响与不碰什么", items[2])

        light = text.split("## 6. 轻量文档路径", 1)[1].split("## 7.", 1)[0]
        self.assertIn("取得 GO 后再修改", light)
        self.assertIn("不写工作流状态", light)
        self.assertIn("不改变规范语义", light)

        reuse = text.split("## 3. 复用与失效", 1)[1].split("## 4.", 1)[0]
        self.assertIn("`write_scope`", reuse, "reuse must bind to the existing owner field")
        self.assertIn("未超出已批准规格/任务包声明的范围", reuse)
        self.assertIn("触及未列文件，重新 GO", reuse)

        fast = text.split("## 5. 速通与其他工作流", 1)[1].split("## 6.", 1)[0]
        self.assertIn("不适用 §2 的三项格式", fast)
        self.assertIn("不追加 GO", fast, "fast track must have a legal exit for scope growth")
        self.assertIn("欠账台账", fast)

    def test_wrt_routes_to_the_gate(self):
        wrt = read(SKILL_ROOT.parent / "wrt" / "SKILL.md")
        self.assertIn("[mutation-gate.md](references/mutation-gate.md)", wrt)
        self.assertIn("必须遵守", wrt, "the route must stay mandatory, not advisory")

    def test_phase_docs_are_routed_to_the_lightweight_path(self):
        text = read(SKILL_MD)
        self.assertIn("简单文本或纯文档修改：不走本流程", text)
        self.assertIn("轻量文档路径", text)
        self.assertIn("mutation-gate", text)

    def test_repair_needs_go_but_investigation_does_not(self):
        text = read(SKILL_MD)
        self.assertIn("只读调查与工作流内部证据不需要 GO", text)
        diag = h3_section(h2_section(text, "Stage 路由"), "Diagnosis and Repair")
        self.assertIn("定义稳定复现与只读复现不受 GO 限制", diag)
        go_sentence = next(s for s in diag.split("。") if "取得 GO" in s)
        self.assertIn(
            "写第一个项目产物", go_sentence,
            "GO must attach to the first write, not to the repro definition",
        )
        for weak in self.WEAKENERS:
            self.assertNotIn(weak, diag.split("Gate：")[0],
                             f"GO requirement must not be weakened with '{weak}'")

    def test_reproduction_reference_points_at_the_gate(self):
        self.assertIn("mutation-gate", read(DIAG))

    def test_go_cannot_be_inferred(self):
        red = h2_section(read(SKILL_MD), "红线")
        self.assertIn("未取得 GO 就写入项目产物", red)
        self.assertIn("把\"复述通过\"\"用户没反对\"当成 GO", red)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Contract tests for dd-bug-fast-track.

Asserts the bug domain fast-track contract: one symptom restatement, minimal
fix without claiming root cause, real smoke that the symptom is gone, then a
mandatory backfill that proves red/green and root cause before closing debts.
"""
from __future__ import annotations

import unittest
from pathlib import Path

WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = WORKFLOW_ROOT.parent

SKILL = WORKFLOW_ROOT / "SKILL.md"
FAST_TRACK = WORKFLOW_ROOT / "references" / "fast-track.md"
BACKFILL = WORKFLOW_ROOT / "references" / "backfill.md"

FORMAL_WORKFLOW = SKILLS_ROOT / "dd-bug-fix-workflow" / "SKILL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFrontmatter(unittest.TestCase):
    """Frontmatter must let an agent decide when to load this skill."""

    def test_name_and_description(self):
        text = read(SKILL)
        self.assertIn("name: dd-bug-fast-track", text)
        self.assertIn("description:", text)
        for trigger in ("快速修 bug", "速通", "先修好再说", "hotfix"):
            self.assertIn(trigger, text, f"description must carry trigger '{trigger}'")


class TestStageOrder(unittest.TestCase):
    """Stage order: intake → fast-fix → smoke → backfill → closure."""

    def test_stage_order_in_skill(self):
        text = read(SKILL)
        positions = {}
        for stage in ("intake", "fast-fix", "smoke", "backfill", "closure"):
            pos = text.find(stage)
            self.assertNotEqual(pos, -1, f"{stage} missing from SKILL.md")
            positions[stage] = pos
        order = ["intake", "fast-fix", "smoke", "backfill", "closure"]
        for earlier, later in zip(order, order[1:]):
            self.assertLess(positions[earlier], positions[later],
                            f"{earlier} must precede {later} in the stage order")

    def test_required_exit_stages(self):
        text = read(SKILL)
        block = text.split("required_exit_stages:", 1)[1].split("```", 1)[0]
        for stage in ("intake", "fast-fix", "smoke", "backfill", "closure"):
            self.assertIn(stage, block, f"required_exit_stages must list {stage}")


class TestSingleAsk(unittest.TestCase):
    """Exactly one ask: the symptom restatement."""

    def test_restatement_is_the_only_ask(self):
        text = read(SKILL)
        self.assertIn("唯一一次询问", text,
                      "restatement must be the only ask in the whole workflow")

    def test_restatement_covers_three_parts(self):
        text = read(FAST_TRACK)
        for part in ("症状", "期望", "修复范围"):
            self.assertIn(part, text, f"restatement must cover '{part}'")

    def test_unconfirmed_restatement_is_reasked(self):
        text = read(FAST_TRACK)
        self.assertIn("未确认（null、取消、空输入）", text,
                      "null/cancel must trigger a re-ask, not a default pass")

    def test_diagnosis_only_request_does_not_fix(self):
        text = read(FAST_TRACK)
        self.assertIn("只授权诊断", text,
                      "diagnosis-only requests must stop before Fast Fix")
        self.assertIn("不得把诊断请求扩成修复授权", text,
                      "a diagnosis request must not be expanded into fix authorization")


class TestMinimalFix(unittest.TestCase):
    """Fast fix is minimal and never claims proven root cause."""

    def test_minimal_change_scope(self):
        text = read(FAST_TRACK)
        self.assertIn("最小修复", text)
        self.assertIn("不顺手重构", text, "fast fix must not smuggle refactors")

    def test_no_root_cause_claim(self):
        text = read(SKILL)
        self.assertIn("不得宣称根因已证明", text,
                      "fast track must never claim proven root cause")

    def test_multi_variable_change_is_recorded(self):
        text = read(FAST_TRACK)
        self.assertIn("多变量修改，因果待补对照验证", text,
                      "multi-variable changes must be recorded as unproven causality")

    def test_choices_recorded_in_decisions(self):
        text = read(FAST_TRACK)
        self.assertIn("直接选推荐项", text)
        self.assertIn("decisions", text)


class TestEnvironmentIsMandatory(unittest.TestCase):
    """A new isolated fix worktree is mandatory, not a default to decline."""

    def test_new_isolated_fix_worktree_is_mandatory(self):
        text = read(FAST_TRACK)
        self.assertIn("必须新建隔离 fix worktree", text,
                      "environment must be a new isolated fix worktree, not a default")
        self.assertIn("在修改任何项目产物", text,
                      "the worktree must exist before any project artifact is modified")
        self.assertIn("不询问", text, "environment must not add an ask")

    def test_only_two_exceptions(self):
        text = read(FAST_TRACK)
        self.assertIn("复用并验证，不重新创建", text,
                      "a provided fix worktree must be reused and verified, not rebuilt")
        self.assertIn("用户明确要求在当前工作区", text,
                      "current workspace is only allowed on explicit user request")

    def test_current_workspace_records_reason(self):
        text = read(FAST_TRACK)
        self.assertIn("reason", text, "the current-workspace exception must record a reason")

    def test_no_creation_failure_escape_hatch(self):
        text = read(FAST_TRACK)
        self.assertNotIn("无法创建", text,
                         "fast track must not self-exempt from the worktree requirement")

    def test_skill_states_invariant_and_red_line(self):
        skill = read(SKILL)
        self.assertIn("首次建立执行环境必须新建隔离 fix worktree", skill,
                      "SKILL.md must state the mandatory worktree invariant")
        self.assertIn("未新建隔离 fix worktree 就修改项目产物", skill,
                      "modifying artifacts without a new worktree must be a red line")


class TestSmokeIsReal(unittest.TestCase):
    """Smoke must really run; user-visible bugs need real-path evidence."""

    def test_real_run_of_the_reported_path(self):
        text = read(FAST_TRACK)
        self.assertIn("真实运行复述时描述的操作路径", text,
                      "smoke must run the reported path for real")

    def test_ui_evidence_is_real_path(self):
        text = read(FAST_TRACK)
        self.assertIn("ui-evidence", text)
        self.assertIn("不接受内部状态、mock 或日志代替", text,
                      "user-visible bugs must not be proven by internal state")

    def test_related_existing_tests_run(self):
        text = read(FAST_TRACK)
        self.assertIn("跑与改动直接相关的既有测试", text,
                      "smoke must check nothing else broke")

    def test_smoke_is_not_regression_ci(self):
        text = read(FAST_TRACK)
        self.assertIn("不是回归 CI", text,
                      "smoke must not be presented as regression CI")

    def test_smoke_is_not_root_cause_proof(self):
        text = read(FAST_TRACK)
        self.assertIn("不得说\"根因已查明\"", text,
                      "smoke must not be presented as root-cause proof")


class TestDefaultDebts(unittest.TestCase):
    """Every skipped formal artifact becomes a ledger entry."""

    def test_default_debt_kinds(self):
        text = read(FAST_TRACK)
        for kind in ("root-cause", "regression", "determinism", "ci", "docs",
                     "ui-evidence"):
            self.assertIn(f"`{kind}`", text, f"default debt list must include {kind}")

    def test_backfill_starts_without_waiting(self):
        text = read(FAST_TRACK)
        self.assertIn("立即进入 Backfill，不等用户再次要求", text,
                      "backfill must start automatically after smoke")


class TestBackfillOrder(unittest.TestCase):
    """Backfill: repro test → root cause → regression CI → docs."""

    def _section_indexes(self):
        text = read(BACKFILL)
        marks = {
            "repro": text.find("## 1. 补复现测试与红绿对照"),
            "root_cause": text.find("## 2. 补根因证据"),
            "ci": text.find("## 3. 补回归 CI"),
            "docs": text.find("## 4. 补文档"),
        }
        for name, pos in marks.items():
            self.assertNotEqual(pos, -1, f"backfill section '{name}' missing")
        return marks

    def test_order(self):
        marks = self._section_indexes()
        self.assertLess(marks["repro"], marks["root_cause"],
                        "repro test must precede root cause proof")
        self.assertLess(marks["root_cause"], marks["ci"],
                        "root cause must precede regression CI")
        self.assertLess(marks["ci"], marks["docs"], "CI must precede docs")


class TestRedGreenEvidence(unittest.TestCase):
    """A repro test only counts with a real red-then-green pair."""

    def test_red_on_reverted_implementation(self):
        text = read(BACKFILL)
        self.assertIn("必须失败", text, "repro test must fail on the reverted fix")
        self.assertIn("恢复修复后跑同一测试，必须通过", text,
                      "the same test must pass with the fix restored")

    def test_green_only_is_invalid(self):
        text = read(BACKFILL)
        self.assertIn("没有红绿对照的复现测试无效", text,
                      "a green-only repro test must be invalid")

    def test_single_variable_control_for_multi_change(self):
        text = read(BACKFILL)
        self.assertIn("单变量对照实验", text,
                      "multi-variable fixes need single-variable control experiments")


class TestRootCauseDebt(unittest.TestCase):
    """Root cause debt cannot be closed without evidence."""

    def test_evidence_kinds(self):
        text = read(BACKFILL)
        for kind in ("日志", "数据流", "最小实验"):
            self.assertIn(kind, text, f"root cause evidence must allow '{kind}'")

    def test_unproven_root_cause_hands_off(self):
        text = read(BACKFILL)
        self.assertIn("不得关闭该欠账", text,
                      "unproven root cause must not close the debt")
        self.assertIn("交接", text, "unproven root cause must hand off")

    def test_root_cause_waiver_restricted(self):
        text = read(BACKFILL)
        self.assertIn("`root-cause` 不接受\"症状没了所以不用证明\"式的豁免", text,
                      "root cause must not be waived on 'symptom gone' grounds")


class TestRegressionCI(unittest.TestCase):
    """Regression CI binds the final SHA."""

    def test_freeze_and_bind(self):
        text = read(BACKFILL)
        self.assertIn("冻结最终候选 SHA", text)
        self.assertIn("CI 结果与修复 SHA 必须一致", text,
                      "CI result must match the fix SHA")


class TestDebtClosure(unittest.TestCase):
    """Debts close with evidence; waivers are per-item, user-confirmed."""

    def test_evidence_required(self):
        text = read(BACKFILL)
        self.assertIn("没有证据的关闭无效", text)

    def test_waive_is_per_item(self):
        text = read(BACKFILL)
        self.assertIn("逐条确认", text)
        self.assertIn("不接受\"都别补了\"的一次性豁免", text)


class TestHandoff(unittest.TestCase):
    """Upgrade triggers hand off to the formal bug workflow."""

    def test_handoff_target(self):
        text = read(SKILL)
        self.assertIn("dd-bug-fix-workflow", text,
                      "fast track must name the formal bug workflow as handoff target")

    def test_handoff_triggers(self):
        text = read(BACKFILL)
        for trigger in ("根因无法证明", "既有回归预期", "持久化格式", "复述范围外的新症状"):
            self.assertIn(trigger, text, f"handoff trigger '{trigger}' missing")

    def test_stop_signals_during_fast_fix(self):
        text = read(FAST_TRACK)
        self.assertIn("交接", text, "fast fix must hand off on stop signals")
        self.assertIn("症状无法稳定复现", text,
                      "unstable repro is a stop signal for fast track")


class TestNoSecondRuleSet(unittest.TestCase):
    """Fast track must not fork the formal workflow's shared semantics."""

    def test_routes_shared_contract(self):
        text = read(SKILL)
        self.assertIn("fast-track-contract", text)
        self.assertIn("唯一属主", text, "shared semantics must stay owned by runtime")

    def test_does_not_inline_ledger_schema(self):
        text = read(SKILL)
        self.assertNotIn("close_evidence", text,
                         "ledger schema belongs to the shared contract")

    def test_formal_workflow_still_owns_full_track(self):
        text = read(FORMAL_WORKFLOW)
        self.assertIn("dd-bug-fix-workflow", text,
                      "formal bug workflow must remain the owner of the full track")
        self.assertIn("dd-bug-fast-track", text,
                      "formal bug workflow must route fast-track intent explicitly")


class TestTrackingCallSite(unittest.TestCase):
    """task-tracking §2/§3/§12: a fast-track workflow is a long-running workflow.

    Intake owes the same one attempt-and-record call site, non-blocking, with
    every binding semantic left to `task-tracking.md`.
    """

    def _intake(self) -> str:
        return read(FAST_TRACK).split("## 1. Intake", 1)[1].split("\n## ", 1)[0]

    def test_intake_hook_routes_to_the_owner(self):
        text = self._intake()
        self.assertIn("task-tracking", text, "Intake must route to the tracking owner")
        self.assertIn("§3", text, "hook must call §3, not invent a binding rule")
        self.assertIn("绑定 Gate 就是 Intake", text, "Intake is this workflow's binding Gate")
        self.assertIn("不阻塞本 Stage", text, "binding failure must stay non-blocking")
        self.assertIn("不因此向用户发问", text, "binding must not add a second ask")

    def test_hook_does_not_restate_owner_vocabulary(self):
        text = self._intake()
        for token in ("sync_reason", "not-authorized", "issue_number", "binding-ambiguous"):
            self.assertNotIn(token, text, f"must not restate owner vocabulary ({token})")

    def test_skill_routes_tracking_and_gate_records_it(self):
        skill = read(SKILL)
        self.assertIn("references/task-tracking.md", skill,
                      "SKILL.md must route to task-tracking.md")
        self.assertIn("tracking 绑定结果已按 owner 合同落盘", skill,
                      "Intake Gate must record the owner-defined binding result")

    def test_untried_binding_is_a_red_line(self):
        self.assertIn("未做 tracking 绑定尝试", read(SKILL),
                      "passing Intake without a recorded attempt must be a red line")


class TestRedLines(unittest.TestCase):
    """Domain red lines."""

    def test_restatement_first(self):
        text = read(SKILL)
        self.assertIn("未复述症状就修改项目产物", text)

    def test_no_extra_asks_or_reviews(self):
        text = read(SKILL)
        self.assertIn("再次询问或插入复核", text)

    def test_no_multi_variable_causality_claim(self):
        text = read(SKILL)
        self.assertIn("一次改多个变量还声称因果成立", text)

    def test_no_green_by_changing_expectations(self):
        text = read(SKILL)
        self.assertIn("不得为了绿灯修改既有测试的预期", text)

    def test_git_authorization_not_implied(self):
        text = read(SKILL)
        self.assertIn("把速通产出解释为 commit、push、merge 或发布授权", text)

    def test_no_unrelated_files_on_fix_branch(self):
        text = read(SKILL)
        self.assertIn("不在 fix 分支夹带无关公共文件修改", text)


if __name__ == "__main__":
    unittest.main()

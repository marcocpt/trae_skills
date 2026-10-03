#!/usr/bin/env python3
"""Contract tests for dd-feature-fast-track.

Asserts the domain fast-track contract: one restatement ask, direct
implementation, real smoke evidence, then a mandatory backfill that closes
every deferred debt with evidence.
"""
from __future__ import annotations

import unittest
from pathlib import Path

WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = WORKFLOW_ROOT.parent

SKILL = WORKFLOW_ROOT / "SKILL.md"
FAST_TRACK = WORKFLOW_ROOT / "references" / "fast-track.md"
BACKFILL = WORKFLOW_ROOT / "references" / "backfill.md"

FORMAL_WORKFLOW = SKILLS_ROOT / "dd-feature-development-workflow" / "SKILL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFrontmatter(unittest.TestCase):
    """Frontmatter must let an agent decide when to load this skill."""

    def test_name_and_description(self):
        text = read(SKILL)
        self.assertIn("name: dd-feature-fast-track", text)
        self.assertIn("description:", text)
        for trigger in ("快速实现", "速通", "先跑起来", "精简版"):
            self.assertIn(trigger, text, f"description must carry trigger '{trigger}'")


class TestStageOrder(unittest.TestCase):
    """Stage order: intake → fast-implementation → smoke → backfill → closure."""

    def test_stage_order_in_skill(self):
        text = read(SKILL)
        positions = {}
        for stage in ("intake", "fast-implementation", "smoke", "backfill", "closure"):
            pos = text.find(stage)
            self.assertNotEqual(pos, -1, f"{stage} missing from SKILL.md")
            positions[stage] = pos
        order = ["intake", "fast-implementation", "smoke", "backfill", "closure"]
        for earlier, later in zip(order, order[1:]):
            self.assertLess(positions[earlier], positions[later],
                            f"{earlier} must precede {later} in the stage order")

    def test_required_exit_stages(self):
        text = read(SKILL)
        block = text.split("required_exit_stages:", 1)[1].split("```", 1)[0]
        for stage in ("intake", "fast-implementation", "smoke", "backfill", "closure"):
            self.assertIn(stage, block, f"required_exit_stages must list {stage}")


class TestSingleAsk(unittest.TestCase):
    """Exactly one ask: the requirement restatement."""

    def test_restatement_is_the_only_ask(self):
        text = read(SKILL)
        self.assertIn("唯一一次询问", text,
                      "restatement must be the only ask in the whole workflow")

    def test_restatement_covers_three_parts(self):
        text = read(FAST_TRACK)
        for part in ("要解决什么", "范围边界", "怎样算能用"):
            self.assertIn(part, text, f"restatement must cover '{part}'")

    def test_unconfirmed_restatement_is_reasked(self):
        text = read(FAST_TRACK)
        self.assertIn("未确认（null、取消、空输入）", text,
                      "null/cancel must trigger a re-ask, not a default pass")

    def test_implementation_choices_are_deferred_to_decisions(self):
        text = read(FAST_TRACK)
        self.assertIn("直接选推荐项", text,
                      "implementation choices must be made by recommendation")
        self.assertIn("decisions", text, "choices must be recorded in decisions")


class TestEnvironmentByRecommendation(unittest.TestCase):
    """Worktree decision is a recommendation, not another question."""

    def test_default_is_new_isolated_worktree(self):
        text = read(FAST_TRACK)
        self.assertIn("默认按推荐项新建隔离 worktree", text,
                      "environment must default to a new isolated worktree")
        self.assertIn("不询问", text, "environment must not add an ask")

    def test_fallback_records_reason(self):
        text = read(FAST_TRACK)
        self.assertIn("无法创建（非 Git 仓库、无可用基线等）时才使用当前工作区", text,
                      "current-workspace fallback must be the exception")
        self.assertIn("reason", text, "fallback must record a reason")


class TestSmokeIsReal(unittest.TestCase):
    """Smoke must be a real run; UI needs real-path evidence."""

    def test_real_build_and_main_path(self):
        text = read(FAST_TRACK)
        self.assertIn("真实构建／启动", text, "smoke must really build and run")
        self.assertIn("主路径", text, "smoke must exercise the promised main path")

    def test_ui_evidence_is_real_path(self):
        text = read(FAST_TRACK)
        self.assertIn("ui-evidence", text, "smoke must consume shared ui-evidence")
        self.assertIn("不接受内部状态、mock、日志或组件渲染代替", text,
                      "UI smoke must not be proven by internal state or mocks")

    def test_smoke_is_not_acceptance(self):
        text = read(FAST_TRACK)
        self.assertIn("不得说\"验收通过\"", text,
                      "smoke must not be presented as acceptance")

    def test_delivers_runnable_artifact(self):
        text = read(FAST_TRACK)
        self.assertIn("怎么立刻用起来", text,
                      "smoke must hand the user a way to use it immediately")


class TestDefaultDebts(unittest.TestCase):
    """Every skipped formal artifact becomes a ledger entry."""

    def test_default_debt_kinds(self):
        text = read(FAST_TRACK)
        for kind in ("spec", "plan", "test", "determinism", "ci", "review", "docs",
                     "ui-evidence"):
            self.assertIn(f"`{kind}`", text, f"default debt list must include {kind}")

    def test_backfill_starts_without_waiting(self):
        text = read(FAST_TRACK)
        self.assertIn("立即进入 Backfill，不等用户再次要求", text,
                      "backfill must start automatically after smoke")


class TestBackfillOrder(unittest.TestCase):
    """Backfill: test → spec → CI/review → docs."""

    def _section_indexes(self):
        text = read(BACKFILL)
        marks = {
            "test": text.find("## 1. 补测试与确定性验证"),
            "spec": text.find("## 2. 补规格"),
            "ci": text.find("## 3. 补 CI 与审查"),
            "docs": text.find("## 4. 补文档"),
        }
        for name, pos in marks.items():
            self.assertNotEqual(pos, -1, f"backfill section '{name}' missing")
        return marks

    def test_order(self):
        marks = self._section_indexes()
        self.assertLess(marks["test"], marks["spec"], "test must precede spec")
        self.assertLess(marks["spec"], marks["ci"], "spec must precede CI/review")
        self.assertLess(marks["ci"], marks["docs"], "CI/review must precede docs")


class TestBackfillDiscipline(unittest.TestCase):
    """Backfill must not rubber-stamp the implementation."""

    def test_ac_come_from_confirmed_requirement(self):
        text = read(BACKFILL)
        self.assertIn("AC 来源是**已确认需求**", text,
                      "AC must come from the confirmed requirement, not the code")

    def test_no_copying_implementation_as_spec(self):
        text = read(BACKFILL)
        self.assertIn("反向规格纪律", text, "backfill must state the reverse-spec rule")
        self.assertIn("不得为了让规格和实现一致而改写已确认需求", text,
                      "spec must not be bent to match the implementation")

    def test_red_green_actually_runs(self):
        text = read(BACKFILL)
        self.assertIn("红绿必须实际运行", text)
        self.assertIn("在回退实现上验证失败", text, "new tests must fail on reverted code")

    def test_tier_judgement_reuses_small_change_track(self):
        text = read(BACKFILL)
        self.assertIn("small-change-track", text,
                      "spec size judgement must reuse the existing tier owner")

    def test_single_sha_binding(self):
        text = read(BACKFILL)
        self.assertIn("冻结最终候选 SHA", text)
        self.assertIn("同一个值", text, "CI/review/gap must bind one SHA")

    def test_review_upgrade_not_overridden(self):
        text = read(BACKFILL)
        self.assertIn("review-gate", text)
        self.assertIn("速通模式不覆盖该升级", text,
                      "review-gate risk triggers still upgrade the review level")


class TestDebtClosure(unittest.TestCase):
    """Debts close with evidence; waivers are per-item, user-confirmed."""

    def test_evidence_required(self):
        text = read(BACKFILL)
        self.assertIn("没有证据的关闭无效", text)

    def test_waive_is_per_item(self):
        text = read(BACKFILL)
        self.assertIn("逐条确认", text, "waivers must be confirmed one item at a time")
        self.assertIn("不接受\"都别补了\"的一次性豁免", text,
                      "bulk waiver must be rejected")


class TestHandoff(unittest.TestCase):
    """Upgrade triggers hand off to the formal workflow."""

    def test_handoff_target(self):
        text = read(SKILL)
        self.assertIn("dd-feature-development-workflow", text,
                      "fast track must name the formal workflow as handoff target")

    def test_upgrade_triggers_listed(self):
        text = read(BACKFILL)
        for trigger in ("公共 API 签名", "架构边界", "持久化格式", "兼容性", "≥ 2 个 Phase"):
            self.assertIn(trigger, text, f"upgrade trigger '{trigger}' missing")

    def test_no_degraded_finish(self):
        text = read(BACKFILL)
        self.assertIn("不在速通内降级", text,
                      "upgrade triggers must not be finished inside fast track")

    def test_stop_signals_during_implementation(self):
        text = read(FAST_TRACK)
        self.assertIn("停止速通实现，交接", text,
                      "implementation must stop and hand off on stop signals")


class TestNoSecondRuleSet(unittest.TestCase):
    """Fast track must not fork the formal workflow's shared semantics."""

    def test_routes_shared_contract(self):
        text = read(SKILL)
        self.assertIn("fast-track-contract", text)
        self.assertIn("唯一属主", text, "shared semantics must stay owned by runtime")

    def test_does_not_redefine_review_levels(self):
        text = read(BACKFILL)
        self.assertNotIn("review_level:", text,
                         "review level semantics belong to review-gate")

    def test_formal_workflow_still_owns_full_track(self):
        self.assertIn("dd-feature-development-workflow", read(FORMAL_WORKFLOW),
                      "formal workflow must remain the owner of the full track")

    def test_formal_workflow_routes_fast_track_intent(self):
        self.assertIn("dd-feature-fast-track", read(FORMAL_WORKFLOW),
                      "formal workflow must route fast-track intent explicitly")


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
        self.assertIn("未复述需求就修改项目产物", text)

    def test_no_extra_asks_or_reviews(self):
        text = read(SKILL)
        self.assertIn("再次询问或插入复核", text,
                      "re-asking or inserting reviews mid-track is a red line")

    def test_no_evidence_free_closure(self):
        text = read(SKILL)
        self.assertIn("无 `evidence` 就把欠账标 `closed`", text)

    def test_no_shipping_on_runnable(self):
        text = read(SKILL)
        self.assertIn("用\"已经能跑起来\"替代正式流程的验收结论", text)

    def test_git_authorization_not_implied(self):
        text = read(SKILL)
        self.assertIn("内容完成不等于 Git 或外部动作授权", text)


if __name__ == "__main__":
    unittest.main()

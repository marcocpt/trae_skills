#!/usr/bin/env python3
"""W6-delivery-lite contract tests (dd-feature-development-workflow).

方法说明：本文件全部是**静态合同检查**（static）——对规范性正文的条款断言，
每条断言针对一条规则子句（动作 + 禁止项），不是裸关键词存在检查，因此不能靠
补关键词变绿。既有测试执行和补丁往返同属确定性检查，不证明agent实际行为；本轮未开展独立agent行为实验。

覆盖（对应 W6 验收清单）：
1. 未提交且禁 Git 仍能完成合法本地验证；
2. dirty 输入变化不能复用 HEAD 证据；
3. 无变更时复用有效证据、不重复 ASK；
4. 项目 CI 必需但未运行不得放行合并；
5. 已授权交付无新确认；
6. 高风险仍有必要独立审查；
7. 旧 candidate 字段恢复兼容；
8. 未要求 merge 时不检查目标分支必须含 candidate 才允许局部任务收尾；
9. Stage 标识与顺序不被叙事精简改变（保护）。
"""
from __future__ import annotations

import unittest
from pathlib import Path

WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = WORKFLOW_ROOT.parent / "dd-workflow-runtime"

SKILL = WORKFLOW_ROOT / "SKILL.md"
CANDIDATE = WORKFLOW_ROOT / "references" / "candidate.md"
DELIVERY = WORKFLOW_ROOT / "references" / "delivery-and-closure.md"
STATE_AND_HANDOFF = WORKFLOW_ROOT / "references" / "state-and-handoff.md"
SMALL = WORKFLOW_ROOT / "references" / "small-change-track.md"
RUNTIME_STATE = RUNTIME_ROOT / "references" / "state.md"
ARTIFACT_VERIFICATION = RUNTIME_ROOT / "references" / "artifact-verification.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def context(text: str, needle: str, before: int = 300, after: int = 500) -> str:
    """Return the neighbourhood of `needle`; fails loudly when it is absent."""
    idx = text.find(needle)
    if idx == -1:
        raise AssertionError(f"probe not found: {needle}")
    return text[max(0, idx - before): idx + after]


class TestUncommittedLocalVerificationIsLegal(unittest.TestCase):
    """1. 未提交且禁 Git 仍能完成合法本地验证（不为拿 SHA 强制提交）。"""

    def test_no_forced_commit_and_digest_binding(self):
        cand = read(CANDIDATE)
        self.assertIn("不为获得 SHA 强制提交", cand,
                      "candidate 必须允许未提交验证，不得为拿 SHA 强制提交")
        self.assertIn("verification_evidence.result.bindings.implementation_digest", cand,
                      "未提交验证必须复用现有 verification_evidence/implementation_digest 机制")
        self.assertIn("有 dirty 时不能只绑定 HEAD", cand,
                      "dirty 工作树不得只绑定 HEAD")

    def test_content_digest_must_not_impersonate_candidate_sha(self):
        cand = read(CANDIDATE)
        self.assertIn("不得把内容摘要塞进 `candidate_sha` 冒充 Git 提交", cand,
                      "不得用内容摘要冒充 Git 提交写入 candidate_sha")
        self.assertIn("也不新增平行 schema／账本", cand,
                      "不得为未提交验证新增平行 schema/账本")

    def test_local_verification_is_not_gated_on_push_authorization(self):
        cand = read(CANDIDATE)
        self.assertIn("本地验证不以先获得 commit/push 授权为前提", cand,
                      "本地验证不得以获得 commit/push 授权为前提")
        self.assertIn("保留已通过的 Workflow Gate，停在该 Delivery 边界", cand,
                      "授权缺失应停在动作边界并保留已通过的 Gate")

    def test_candidate_branch_pipeline_is_not_the_default(self):
        cand = read(CANDIDATE)
        self.assertIn("专用候选分支流水线不默认启用", cand,
                      "专用候选分支流水线不得是默认路径")
        self.assertIn("只在项目规则或集成流程确需时", cand,
                      "专用候选分支流水线只在项目/集成确需时按授权采用")
        seg = context(cand, "fetch 最新 develop")
        self.assertIn("不默认启用", seg,
                      "提及 fetch 最新 develop 时必须在同一段落声明不默认启用")


class TestDirtyChangeInvalidatesHeadEvidence(unittest.TestCase):
    """2. dirty 输入变化不能复用 HEAD 证据（仅 HEAD 相同不算有效绑定）。"""

    def test_candidate_declares_dirty_mismatch(self):
        cand = read(CANDIDATE)
        self.assertIn("仅 HEAD 相同但 dirty", cand,
                      "candidate 必须声明仅 HEAD 相同但 dirty 变化即失配")
        seg = context(cand, "仅 HEAD 相同但 dirty", after=120)
        self.assertIn("必须重验", seg, "dirty 失配必须重验，不得继续复用旧证据")

    def test_shared_verification_contract_declares_dirty_mismatch(self):
        av = read(ARTIFACT_VERIFICATION)
        self.assertIn("仅 HEAD 相同但 dirty", av,
                      "共享 artifact-verification 必须声明 dirty 变化即 stale")

    def test_router_states_dirty_cannot_be_masked_by_head(self):
        self.assertIn("不可用仅 HEAD 相同掩盖 dirty 变化", read(SKILL),
                      "主文件必须声明 HEAD 相同不能掩盖 dirty 变化")

    def test_implementation_digest_may_be_worktree_fingerprint(self):
        av = read(ARTIFACT_VERIFICATION)
        self.assertIn("`candidate_sha` 只记真实 Git 提交，不得以内容摘要冒充", av,
                      "共享合同必须区分 implementation_digest 与 candidate_sha")


class TestReuseValidEvidenceAndNoRepeatAsk(unittest.TestCase):
    """3. 无变更时复用有效证据、不重复 ASK。"""

    def test_no_unconditional_full_rerun(self):
        cand = read(CANDIDATE)
        self.assertIn("不无条件全量重跑", cand,
                      "未受影响且仍有效的结果必须直接复用，不得无条件全量重跑")
        self.assertIn("仍有效的结果直接复用", cand, "有效结果必须直接复用")

    def test_base_advance_does_not_invalidate_unrelated_local_evidence(self):
        cand = read(CANDIDATE)
        self.assertIn("远端 base 前进本身不使未受影响的本地验证失效", cand,
                      "远端 base 前进本身不得废弃未受影响的本地验证")
        self.assertIn("base 变化影响合并产物时重验合并结果", cand,
                      "base 变化影响合并产物时必须重验合并结果")

    def test_confirmation_does_not_ask_again_without_new_decision(self):
        skill = read(SKILL)
        self.assertIn("无新决定不泛问", skill,
                      "无新决定不得泛问继续交付还是回退")
        self.assertIn("只有缺少必要授权或出现新决定才询问", skill,
                      "只有缺少授权或出现新决定才询问")

    def test_recovery_reuses_valid_results(self):
        handoff = read(STATE_AND_HANDOFF)
        self.assertIn("不无条件全量重跑", handoff,
                      "恢复路径同样不得无条件全量重跑")


class TestProjectCiRequiredButNotRunBlocksMerge(unittest.TestCase):
    """4. 项目 CI 必需但未运行不得放行合并。"""

    def test_candidate_ci_gap_blocks(self):
        cand = read(CANDIDATE)
        self.assertIn("未执行、未绑定或结论非 success 不得声称通过，也不得放行 merge", cand,
                      "项目要求 CI 但未执行/未绑定/结论非 success 不得放行合并")
        self.assertIn("不得自行豁免", cand, "不得自行豁免必需 CI")
        self.assertIn("不得留空冒充完成", cand, "不得留空冒充 CI 完成")

    def test_delivery_keeps_blocked_on_missing_ci(self):
        delivery = read(DELIVERY)
        self.assertIn("不得用本地结果放行", delivery,
                      "不得用本地结果放行必需 CI")
        self.assertIn("BLOCKED", delivery, "缺 CI 时必须保持 BLOCKED")

    def test_ci_necessity_is_project_rule_owned(self):
        cand = read(CANDIDATE)
        self.assertIn("是否必需、范围与执行位置由项目规则决定", cand,
                      "CI 是否必需/范围/执行位置必须由项目规则决定")
        self.assertIn("项目不要求 CI", cand, "项目不要求 CI 时必须可记 not-required")


class TestAuthorizedDeliveryNeedsNoNewConfirmation(unittest.TestCase):
    """5. 已授权交付无新确认；授权必须是具体动作/范围。"""

    def test_delivery_reuses_existing_authorization(self):
        delivery = read(DELIVERY)
        self.assertIn("复用 Confirmation 已有的 action-specific `delivery_authorization`", delivery,
                      "交付必须复用已有动作级授权")
        self.assertIn("无新决定不再泛问", delivery,
                      "已授权且无新决定时不再泛问继续交付还是回退")

    def test_unauthorized_action_stops_at_boundary(self):
        delivery = read(DELIVERY)
        self.assertIn("not-required", delivery, "未要求动作必须记 not-required")
        self.assertIn("not-authorized", delivery, "未获授权动作必须记 not-authorized")

    def test_router_says_ask_only_on_missing_authorization(self):
        self.assertIn("按授权交付——复用已有动作级授权", read(SKILL),
                      "主文件第 8 步必须是按授权交付")


class TestHighRiskKeepsIndependentReview(unittest.TestCase):
    """6. 高风险仍保留必要独立审查；不由 full 档或文件数量自动升级。"""

    def test_risk_trigger_upgrade_and_coverage(self):
        cand = read(CANDIDATE)
        self.assertIn("命中 review-gate 任一风险触发器", cand, "必须按 review-gate 风险触发器升级")
        self.assertIn("执行独立强审", cand, "高风险必须执行独立强审")
        self.assertIn("全局／跨层不变量", cand, "高风险必须覆盖全局不变量")
        self.assertIn("Decision Freedom", cand, "高风险必须覆盖明确负向要求")
        self.assertIn("兼容性／迁移影响", cand, "高风险必须覆盖兼容性与迁移")

    def test_no_automatic_escalation_from_tier_or_file_count(self):
        cand = read(CANDIDATE)
        self.assertIn("不因 `change_tier=full` 或文件数量自动要求独立强审", cand,
                      "不得因 full 档或文件数量自动要求独立强审")

    def test_shared_state_routes_review_level_by_risk(self):
        state = read(RUNTIME_STATE)
        self.assertIn("不由 `change_tier` 直接决定", state,
                      "共享 state 必须声明审查等级由风险路由、不由档位决定")

    def test_coverage_form_is_compact_not_mechanical_table(self):
        cand = read(CANDIDATE)
        self.assertIn("不机械生成独立的覆盖大表", cand,
                      "覆盖可紧凑记录，不得机械生成独立大表")
        self.assertIn("每项记录 coverage/disposition", cand,
                      "紧凑记录仍必须逐项可复核")

    def test_small_track_routes_review_by_risk(self):
        small = read(SMALL)
        self.assertIn("审查按 [review-gate]", small, "small 档同样按 review-gate 风险路由")
        self.assertIn("档位不再决定审查等级", small, "档位不再决定审查等级")
        self.assertIn("绑定唯一被验证版本", small, "版本绑定不变")


class TestLegacyCandidateFieldCompatibility(unittest.TestCase):
    """7. 旧 candidate 字段恢复兼容（原样保留、不销毁、不冒充已通过）。"""

    def test_legacy_fields_are_preserved_and_read_as_unverified(self):
        handoff = read(STATE_AND_HANDOFF)
        self.assertIn("旧候选字段兼容", handoff, "必须显式声明旧候选字段兼容")
        self.assertIn("原样保留并兼容读取为线索", handoff, "旧字段必须原样保留")
        self.assertIn("缺失一律按", handoff, "必须有缺失字段的读取口径")
        self.assertIn("不因缺新字段重启或回退已通过的 Gate", handoff,
                      "不得因缺新字段重启或回退已通过 Gate")

    def test_uncommitted_binding_recorded_in_state_contract(self):
        handoff = read(STATE_AND_HANDOFF)
        self.assertIn("未提交验证时 `candidate_sha` 为空", handoff,
                      "状态合同必须说明未提交验证时的绑定方式")


class TestNoMergeGatingForLocalScope(unittest.TestCase):
    """8. 未要求 merge 时不检查目标分支必须含 candidate 才允许局部收尾。"""

    def test_target_branch_check_is_conditional(self):
        delivery = read(DELIVERY)
        self.assertIn("仅在要求的交付动作包含 merge 时校验 develop/目标分支包含该被验证版本",
                      delivery, "目标分支校验必须只在要求 merge 时进行")
        self.assertIn("未要求 merge 的已授权局部任务按实际范围收尾", delivery,
                      "未要求 merge 的局部任务必须可按实际范围收尾")
        self.assertIn("不因目标分支未含候选而阻塞", delivery,
                      "不得以目标分支未含候选阻塞局部收尾")

    def test_old_unconditional_target_branch_requirement_is_gone(self):
        delivery = read(DELIVERY)
        self.assertNotIn("- develop/目标分支包含该 `candidate_sha`；", delivery,
                         "旧的无条件目标分支要求必须被条件化")

    def test_local_closure_must_not_claim_merged(self):
        self.assertIn("也据此不宣称已合并／已发布", read(DELIVERY),
                      "局部收尾不得宣称已合并/已发布")


class TestStageIdentifiersUnchanged(unittest.TestCase):
    """9. 叙事精简不得改变共享 Stage 标识、顺序与 required_exit_stages。"""

    EXPECTED_STAGES = [
        "intake", "environment", "specification", "planning", "implementation",
        "documentation", "final-candidate", "confirmation", "delivery", "closure",
    ]

    def test_required_exit_stages_unchanged(self):
        skill = read(SKILL)
        block = skill.split("required_exit_stages:", 1)[1].split("delivery_policy", 1)[0]
        for stage in self.EXPECTED_STAGES:
            self.assertIn(f"  - {stage}\n", block, f"required_exit_stages 必须仍含 {stage}")

    def test_fixed_stage_order_unchanged(self):
        skill = read(SKILL)
        # 只归一化空白，保留 Stage 名与箭头顺序，避免换行差异掩盖真实改动
        block = " ".join(skill.split("固定 Stage 顺序：", 1)[1].split())
        order = ("intake → environment → specification → planning → implementation "
                 "→ documentation → final-candidate → confirmation → delivery → closure")
        self.assertIn(order, block, "固定 Stage 顺序必须逐字不变")

    def test_narrative_collapsed_from_three_steps_to_two(self):
        skill = read(SKILL)
        self.assertIn("7. 完成验证——绑定唯一被验证版本", skill, "第 7 步必须是合并后的完成验证")
        self.assertIn("8. 按授权交付——复用已有动作级授权", skill, "第 8 步必须是按授权交付")
        self.assertIn("9. 完成交付、清理、状态收尾和 Host Close。", skill, "第 9 步是收尾")
        self.assertNotIn("10. 完成交付、清理、状态收尾和 Host Close。", skill,
                         "旧的第 10 步必须顺延为第 9 步")




class TestConditionalIdentityBranches(unittest.TestCase):
    """Static consistency of committed/dirty and required/optional-CI branches."""

    def test_dirty_evidence_does_not_fill_sha_fields(self):
        text = read(CANDIDATE)
        section = text.split("## 4.", 1)[1].split("## 5.", 1)[0]
        self.assertIn("未提交路径：本次SHA字段保持空", section)
        self.assertIn("不得把内容摘要写入任何SHA字段", section)
        self.assertNotIn("未提交时等于绑定的 `implementation_digest`", section)

    def test_optional_ci_null_is_not_an_automatic_failure(self):
        text = read(CANDIDATE).split("## 7.", 1)[1]
        self.assertIn("项目不要求CI时`full_ci_run=null`是合法未适用表示", text)
        self.assertIn("不因此判stale/BLOCKED", text)

    def test_recorded_blocker_is_not_completed_delivery(self):
        text = read(DELIVERY)
        self.assertIn("仅当项目要求CI时", read(CANDIDATE))
        self.assertIn("未提交的局部验证保持candidate_sha及当前SHA字段为空", text)

if __name__ == "__main__":
    unittest.main()

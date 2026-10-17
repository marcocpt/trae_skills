#!/usr/bin/env python3
"""W6-delivery-lite contract tests（dd-bug-fix-workflow，同步精简交付流程）。

方法说明：本文件全部是**静态合同检查**（static）——对规范性正文的条款断言，
每条针对一条规则子句，不是裸关键词存在检查。行为证据（behavior）由既有
Bug6/Feature35/artifact29/tracking102 套件的真实执行与 changes.patch 打补丁
确定性检查提供，见 validation.json。

覆盖：
1. Bug 未 push 仍可准备并进行授权范围内的本地真实复验；
2. 复现/根因/最小修复/红绿回归/真实路径证据不被精简删除；
3. 项目要求 CI 但未运行/未授权时记明确缺口，不得伪造或降级为本地通过；
4. 修复效果的用户复验与 Git 交付批准互不替代；行为变化仍先裁决；
5. conditional/no-op 写清实际结论，不伪造 CI/merge 完成；
6. 未提交/dirty 用 implementation_digest 绑定，不冒充提交 SHA；旧状态字段兼容。
"""
from __future__ import annotations

import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"
DIAG = SKILL_ROOT / "references" / "diagnosis-and-verification.md"
DELIVERY = SKILL_ROOT / "references" / "delivery-and-closure.md"
STATE = SKILL_ROOT / "references" / "state.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestBugLocalReverifyBeforePush(unittest.TestCase):
    """1. Bug 未 push 但可准备并进行授权本地真实复验。"""

    def test_local_reverify_is_not_gated_on_push(self):
        diag = read(DIAG)
        self.assertIn("可本地执行的复验不受 push 前置约束", diag,
                      "可本地执行的复验不得被 push 前置约束")
        self.assertIn("不要求必须先 push 才能做这些复验", diag,
                      "不得要求必须先 push 才能做本地复验")

    def test_router_says_local_reverify_not_gated_on_push(self):
        self.assertIn("可本地执行的真实复验不以先 push 为前提", read(SKILL_MD),
                      "主文件必须声明本地真实复验不以 push 为前提")

    def test_uncommitted_binding_without_fake_commit_sha(self):
        diag = read(DIAG)
        self.assertIn("未获 commit 授权时不提交", diag, "未获 commit 授权时不得提交")
        self.assertIn("verification_evidence.result.bindings.implementation_digest", diag,
                      "未提交时必须用 implementation_digest 绑定真实工作树内容")
        self.assertIn("不得用内容摘要冒充提交 SHA", diag,
                      "不得用内容摘要冒充提交 SHA")

    def test_push_gap_recorded_not_fatal_to_local_evidence(self):
        diag = read(DIAG)
        self.assertIn("未授权停在动作边界并记录 `not-authorized`", diag,
                      "未授权 push 必须停在动作边界并记 not-authorized")
        self.assertIn("不因此判定本地复验无效", diag,
                      "不得因未 push 判定本地复验无效")


class TestBugCoreEvidenceKept(unittest.TestCase):
    """2. 复现、根因、最小修复、红绿回归、真实路径证据不删。"""

    def test_sync_section_references_the_full_evidence_set(self):
        diag = read(DIAG)
        seg = diag.split("## 7. Sync and CI", 1)[1].split("\n## ", 1)[0]
        for token in ("复现", "根因", "最小修复", "红绿回归", "真实路径证据"):
            self.assertIn(token, seg, f"Sync and CI 必须保留 {token} 相关证据要求")
        self.assertIn("不因精简而删减", seg, "必须显式声明不因精简删减证据")


class TestBugCiGapNotFaked(unittest.TestCase):
    """3. 项目要求 CI 但未运行/未授权 → 明确缺口，不伪造、不降级本地。"""

    def test_ci_gap_is_explicit(self):
        seg = read(DIAG).split("## 7. Sync and CI", 1)[1].split("\n## ", 1)[0]
        self.assertIn("是否必需、范围与执行位置由项目规则决定", seg,
                      "CI 是否必需/范围/执行位置由项目规则决定")
        self.assertIn("不得改成本地通过、不得自行豁免、不得留空冒充", seg,
                      "不得改成本地通过/自行豁免/留空冒充")
        self.assertIn("严格绑定被交付版本", seg, "CI 必须绑定被交付版本")

    def test_no_passed_result_without_run(self):
        seg = read(DIAG).split("## 7. Sync and CI", 1)[1].split("\n## ", 1)[0]
        self.assertIn("CI 未运行不得写 `result: passed`", seg,
                      "CI 未运行不得写 result: passed")

    def test_delivery_records_not_required_and_not_authorized(self):
        delivery = read(DELIVERY)
        self.assertIn("不伪造 CI／merge 完成", delivery, "不得伪造 CI/merge 完成")
        self.assertIn("not-required", delivery, "未要求动作记 not-required")
        self.assertIn("not-authorized", delivery, "未授权动作记 not-authorized")
        self.assertIn("记明确缺口，不得放行", delivery, "缺 CI 必须记缺口且不放行")


class TestBugUserVerificationSeparateFromGitApproval(unittest.TestCase):
    """4. 修复效果的用户复验与 Git 交付批准互不替代；行为变化仍先裁决。"""

    def test_two_authorizations_are_distinct(self):
        self.assertIn("修复效果的用户复验与 Git 交付批准是两个授权，互不替代",
                      read(SKILL_MD), "两种授权必须互不替代")
        self.assertIn("不等于 Git 交付批准", read(DELIVERY),
                      "用户复验不等于 Git 交付批准")

    def test_behavior_change_still_requires_adjudication(self):
        self.assertIn("请求用户裁决", read(SKILL_MD), "行为变化仍必须先裁决")
        self.assertIn("行为变化已裁决", read(DELIVERY), "行为变化必须裁决后才过 Gate")

    def test_manual_verification_not_removed(self):
        self.assertIn("不因精简交付移除项目要求的人工复验", read(DELIVERY),
                      "不得因精简交付移除项目要求的人工复验")


class TestBugStateBindingAndLegacyCompatibility(unittest.TestCase):
    """6. 未提交/dirty 绑定与旧状态字段兼容。"""

    def test_state_records_version_binding_and_gap(self):
        state = read(STATE)
        self.assertIn("implementation_digest", state, "状态必须记录 digest 绑定")
        self.assertIn("不得用内容摘要冒充提交 SHA", state, "不得冒充提交 SHA")
        self.assertIn("有 dirty 时不能只绑定 HEAD", state, "dirty 时不得只绑定 HEAD")
        self.assertIn("不写 `result: passed`", state, "未运行不得写 passed")

    def test_legacy_fields_preserved(self):
        state = read(STATE)
        self.assertIn("原样保留并兼容读取为线索", state, "旧字段必须原样保留")
        self.assertIn("缺失一律按", state, "必须有缺失字段读取口径")
        self.assertIn("不因缺新字段重启或回退已通过的 Gate", state,
                      "不得因缺新字段重启或回退已通过 Gate")


class TestBugStageIdentifiersUnchanged(unittest.TestCase):
    """Bug 同步精简同样不改 Stage 标识/顺序/legacy 映射。"""

    EXPECTED = [
        "intake", "environment", "diagnosis-and-repair", "sync-and-ci",
        "user-verification", "documentation", "delivery", "integration-and-closure",
    ]

    def test_required_exit_stages_unchanged(self):
        skill = read(SKILL_MD)
        block = skill.split("required_exit_stages:", 1)[1].split("delivery_policy", 1)[0]
        for stage in self.EXPECTED:
            self.assertIn(f"  - {stage}\n", block, f"required_exit_stages 必须仍含 {stage}")

    def test_legacy_current_step_mapping_unchanged(self):
        state = read(STATE)
        for line in ("0 → intake", "3 → sync-and-ci", "7 → integration-and-closure"):
            self.assertIn(line, state, f"legacy 映射必须保留 {line}")


if __name__ == "__main__":
    unittest.main()

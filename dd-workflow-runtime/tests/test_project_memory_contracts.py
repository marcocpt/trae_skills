#!/usr/bin/env python3
"""项目记忆的静态合同检查；不把文字断言当作 Agent 行为验证。

保护结案复用、证据与批准边界、按问题检索，以及消费者路由。
行为压力场景另由 writing-skills 方法执行。
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT.parent


def read(relative):
    return (SKILLS / relative).read_text(encoding="utf-8")


def section(text, heading):
    match = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^### |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"缺少可执行合同章节：{heading}")
    return match.group(1)


class TestClosureMemory(unittest.TestCase):
    def setUp(self):
        self.closure = section(read("dd-workflow-runtime/references/artifact-lifecycle.md"),
                               "3.6 任务结案与项目记忆")

    def test_existing_entry_is_the_only_closure_owner(self):
        self.assertIn("在既有持久任务入口内写结案记录", self.closure)
        self.assertIn("不另建历史总结、CHANGELOG、记忆数据库或第二套状态账本", self.closure)
        self.assertIn("Completion Receipt", self.closure)
        self.assertIn("引用既有记录", self.closure)

    def test_compact_record_keeps_why_where_and_evidence(self):
        for clause in ("任务标识、日期", "症状或目标", "根因或关键决定及理由",
                       "受影响能力、代码与测试位置", "实际验证结论与证据引用",
                       "被验证版本", "剩余限制", "授权与交付状态"):
            self.assertIn(clause, self.closure)
        self.assertIn("没有发生或没有证据的内容明确记为未执行或未知", self.closure)

    def test_closure_does_not_destroy_the_only_evidence_or_approval(self):
        self.assertIn("唯一验证证据、批准依据和仍有效约束不得因压缩丢失", self.closure)
        self.assertIn("未提交时保留可持久定位的差异或快照", self.closure)
        self.assertIn("不得只写 HEAD 或只留下摘要指纹", self.closure)
        self.assertIn("删除仍按 §3.5", self.closure)
        self.assertIn("完成后冻结", self.closure)

    def test_missing_retention_location_blocks_cleanup(self):
        self.assertIn("差异或快照须覆盖相关未跟踪输入", self.closure)
        self.assertIn("无法在已授权位置保全时停止清理", self.closure)
        self.assertIn("记录 blocker 与下一安全动作", self.closure)

    def test_compact_contracts_reuse_existing_approval_and_lifecycle(self):
        lifecycle = read("dd-workflow-runtime/references/artifact-lifecycle.md")
        canonical = next(line for line in lifecycle.splitlines()
                         if line.startswith("| `canonical` |"))
        self.assertIn("最小长期合同", canonical)
        self.assertIn("artifact-source-and-packet.md", self.closure)
        specs = read("dd-writing-specs/SKILL.md")
        paragraph = next((p for p in specs.split("\n\n")
                          if "最小长期合同" in p and "Lite 自检与确认" in p), "")
        self.assertIn("artifact-source-and-packet.md", paragraph)
        self.assertIn("不新增批准字段或 Gate", paragraph)


class TestQuestionDrivenRetrieval(unittest.TestCase):
    def setUp(self):
        self.retrieval = section(read("dd-workflow-runtime/references/artifact-lifecycle.md"),
                                 "3.7 按问题检索")

    def test_questions_have_distinct_sources(self):
        for clause in ("当前怎样工作", "为什么这样改", "做到哪里", "验证过什么"):
            self.assertIn(clause, self.retrieval)
        self.assertIn("先用任务标识、能力名、代码符号或症状检索", self.retrieval)
        self.assertIn("不默认全文加载历史目录", self.retrieval)

    def test_implementation_does_not_rewrite_intent(self):
        self.assertIn("代码说明实现事实，不自动改写目标或批准约束", self.retrieval)
        self.assertIn("结案记录只说明当时的状态", self.retrieval)
        self.assertIn("当前代码、dirty 差异", self.retrieval)
        self.assertIn("不能从最终代码反推未记录的动机", self.retrieval)

    def test_missing_evidence_is_reported_and_indexes_are_disposable(self):
        self.assertIn("证据缺失、过期或版本不符时明确说明", self.retrieval)
        self.assertIn("区分记录中的历史结论与本次实际验证", self.retrieval)
        self.assertIn("附可定位的来源", self.retrieval)
        self.assertIn("索引属于 `derived`", self.retrieval)
        self.assertIn("不作为唯一事实来源", self.retrieval)


class TestConsumerRouting(unittest.TestCase):
    def test_changed_skill_routes_resolve_to_real_files(self):
        for relative in (
            "dd-workflow-runtime/SKILL.md",
            "dd-workflow-runtime/references/state.md",
            "dd-workflow-runtime/references/artifact-contract.md",
            "dd-workflow-runtime/references/artifact-lifecycle.md",
            "dd-writing-specs/SKILL.md",
            "dd-feature-development-workflow/references/documentation.md",
            "dd-bug-fix-workflow/references/delivery-and-closure.md",
            "dd-feature-fast-track/references/fast-track.md",
            "dd-feature-fast-track/references/backfill.md",
            "dd-bug-fast-track/references/backfill.md",
        ):
            path = SKILLS / relative
            for target in re.findall(r"\]\(([^)\s]+)\)", read(relative)):
                if ":" in target or target.startswith("#"):
                    continue
                with self.subTest(path=relative, target=target):
                    self.assertTrue((path.parent / target.split("#")[0]).exists(),
                                    "按需加载路径必须可定位")

    def test_runtime_discovery_and_persistent_entry_route_to_owner(self):
        for relative in ("dd-workflow-runtime/SKILL.md",
                         "dd-workflow-runtime/references/state.md"):
            with self.subTest(path=relative):
                text = read(relative)
                self.assertIn("artifact-lifecycle.md", text)
                self.assertIn("§3.6", text)
                self.assertIn("§3.7", text)

    def test_completion_consumers_link_instead_of_redefining_record(self):
        for relative in (
            "dd-writing-specs/SKILL.md",
            "dd-feature-development-workflow/references/documentation.md",
            "dd-bug-fix-workflow/references/delivery-and-closure.md",
            "dd-feature-fast-track/references/backfill.md",
            "dd-bug-fast-track/references/backfill.md",
        ):
            with self.subTest(path=relative):
                text = read(relative)
                self.assertRegex(text, r"\]\([^\n)]*artifact-lifecycle\.md[^\n)]*\).*§3\.6")
                self.assertNotIn("任务标识、日期", text,
                                 "消费者引用结案合同，不复制字段清单")

    def test_fast_feature_does_not_turn_risk_into_document_count(self):
        text = read("dd-feature-fast-track/references/backfill.md")
        spec = text.split("## 2. 补规格", 1)[1].split("## 3.", 1)[0]
        self.assertIn("dd-writing-specs", spec)
        self.assertIn("既有持久任务入口", spec)
        self.assertIn("风险只决定审查和验证强度", spec)
        self.assertNotIn("不满足则补完整规格套件", spec)
        self.assertIn("small-change-track", spec,
                      "保留正式流程的风险准入与升级判定")
        debt = read("dd-feature-fast-track/references/fast-track.md")
        self.assertNotIn("mini-spec 或完整规格套件", debt)
        self.assertIn("内容指纹", debt)


if __name__ == "__main__":
    unittest.main()

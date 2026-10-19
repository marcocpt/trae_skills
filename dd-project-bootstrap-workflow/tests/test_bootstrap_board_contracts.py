"""Bootstrap 本地任务入口调用点与交接边界的合同回归。"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
EXECUTION = ROOT / "references/execution-contract.md"


def section(path, title):
    text = path.read_text()
    match = re.search(r"^## " + re.escape(title) + r"\n(.*?)(?=^## |\Z)",
                      text, re.M | re.S)
    if not match:
        raise AssertionError(f"{path.name} 缺少章节 {title}")
    return match.group(1)


class BootstrapBoardContracts(unittest.TestCase):
    def test_preflight_routes_to_shared_entry_after_environment(self):
        main = section(SKILL, "首步：Preflight")
        detail = section(EXECUTION, "1. Preflight")
        for text in (main, detail):
            self.assertIn("建立或复用持久任务入口", text)
            self.assertLess(text.index("持久化工作环境"), text.index("建立或复用持久任务入口"))
        board = section(SKILL, "看板与接手入口")
        self.assertIn("../dd-workflow-runtime/references/state.md#持久任务入口", board)
        self.assertIn("不另建看板", board)

    def test_node_gate_and_recovery_update_existing_entry(self):
        state = section(EXECUTION, "2. State")
        self.assertIn("恢复时先核对", state)
        self.assertIn("已有任务入口", state)
        node = section(EXECUTION, "4. Node Contract")
        for trigger in ("节点 Gate 通过", "阻塞", "暂停", "交接"):
            self.assertIn(trigger, node)
        self.assertIn("先持久化状态，再更新同一任务入口", node)
        self.assertIn("实际结果", node)
        self.assertIn("下一安全动作", node)

    def test_children_and_handoff_reuse_entry_without_payload_fork(self):
        child = section(EXECUTION, "6. Child Invocation")
        self.assertIn("复用父任务入口", child)
        self.assertIn("不另建看板", child)
        handoff = section(EXECUTION, "9. Handoff")
        self.assertIn("relevant_files", handoff)
        self.assertIn("同一任务入口", handoff)
        self.assertIn("不新增 payload 字段", handoff)
        self.assertIn("不能把首个 Feature 标为已实现", handoff)

    def test_host_close_cannot_complete_unconsumed_handoff(self):
        for path, title in ((SKILL, "宿主结束合同"), (EXECUTION, "10. Host Close")):
            text = section(path, title)
            self.assertIn("下游确认接收", text)
            self.assertIn("handoff-ready", text)
            self.assertNotIn("Exit Gate 与 Handoff 完成后先原子持久化", text)

    def test_handoff_keeps_existing_schema_and_consumer_write_order(self):
        handoff = section(EXECUTION, "9. Handoff")
        payload = re.search(r"Payload：\s*```yaml\n(.*?)```", handoff, re.S).group(1)
        fields = re.findall(r"^(\w+):", payload, re.M)
        self.assertEqual(fields, [
            "handoff_version", "source_workflow", "source_state_path", "worktree_path",
            "goal", "scope", "project_mode", "selected_feature_or_phase", "required_reading",
            "relevant_files", "constraints", "requirements_seed", "acceptance_criteria",
            "verification", "out_of_scope", "resolved_decisions", "open_non_blocking_items",
            "blocking_questions", "baseline_path", "phase_contract_path", "phase_contract_status",
            "delivery_policy",
        ])
        self.assertRegex(handoff, r"先写入自己的 Bootstrap 消费字段，再把 Bootstrap state 改为 `completed`")

    def test_local_board_does_not_enable_external_tracking(self):
        text = SKILL.read_text()
        self.assertIn("第一阶段不自动创建、不自动绑定、不自动投影", text)
        board = section(SKILL, "看板与接手入口")
        self.assertIn("本地任务入口", board)
        self.assertIn("不触发 GitHub Issue", board)


if __name__ == "__main__":
    unittest.main()

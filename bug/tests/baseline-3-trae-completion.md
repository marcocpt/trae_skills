# 基线测试 3：Bug 修复完成后的 Trae 结束合同

## 场景

用户已验证 Bug 修复，文档和 Delivery Gate 已通过，修复已合并，post-merge CI 验证的是 merge SHA，Completion Receipt 已写入，`host=trae`。

## 预期

1. 不把集成决策与 Host Close 合并；
2. 不先删除恢复证据或输出最终摘要；
3. ASK 仅提供 `结束本次任务` / `还有其他任务`；
4. “还有其他任务”创建新 `workflow_id`，从新 Intake/Preflight 开始；
5. “结束本次任务”后才输出最终摘要。

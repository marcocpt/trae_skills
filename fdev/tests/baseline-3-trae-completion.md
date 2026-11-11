# 基线测试 3：Feature 完成后的 Trae 结束合同

## 场景

Feature 的全部 Phase、最终候选 SHA、完整 CI、Documentation、Delivery 和 Closure Gate 已通过。清理前已写 Completion Receipt，`host=trae`。

## 预期

1. 不再询问规格、worktree 或清理选项；
2. 不先输出最终摘要；
3. ASK 仅提供 `结束本次任务` / `还有其他任务`；
4. “还有其他任务”创建新 `workflow_id` 并重新 Preflight；
5. “结束本次任务”后才输出最终摘要。

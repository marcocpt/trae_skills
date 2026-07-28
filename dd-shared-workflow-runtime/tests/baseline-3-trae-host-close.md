# 基线场景 3：Trae 完成后最终 ASK

## 背景

`host=trae`。Workflow Gate 与必需 Delivery Gate 均通过，`status=completed` 和 Completion Receipt 已原子写入，没有 blocker。

## 选择

A) 输出最终摘要并直接结束
B) 再询问是否启用结束合同
C) ASK `结束本次任务` / `还有其他任务`
D) ASK 清理、暂停、结束、其他任务四个选项

## 预期

**C**

资源处置必须在 Completion 前解决。Trae Host Close 只决定会话是否继续；null 必须重复同一 ASK。

# Baseline 2：Trae 最终完成

`host=trae`、`invocation_mode=standalone`，所有 Exit Gate 已通过。

正确行为：先原子持久化 `completed` 与必要 Receipt，再 ASK，且只有 `结束本次任务` / `还有其他任务`；不得直接结束。

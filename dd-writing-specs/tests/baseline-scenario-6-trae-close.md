# 基线场景 6：Trae standalone 完成

`host=trae`、`invocation_mode=standalone`，Exit Gate 已通过。

正确行为：先持久化 `completed`/Receipt，再 ASK 且只提供 `结束本次任务` / `还有其他任务`；不得直接结束。

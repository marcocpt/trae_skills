# Baseline 7：Trae 最终完成

`host=trae`、`invocation_mode=standalone`，审核已收尾，剩余 TODO 已在摘要说明，状态已可完成。

正确行为：先持久化 `completed`/Receipt，再 ASK，且只有 `结束本次任务` / `还有其他任务`；不得直接结束。

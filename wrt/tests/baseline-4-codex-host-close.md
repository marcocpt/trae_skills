# 基线场景 4：Codex 正常交付

## 背景

`host=codex`。Workflow Gate 与必需 Delivery Gate 均通过，状态已持久化为 `completed`，用户和项目规则没有要求结束确认。

## 选择

A) 强制询问 `结束本次任务` / `还有其他任务`
B) 正常输出最终摘要
C) 不输出结果，等待用户追问

## 预期

**B**

Trae 的最终 ASK 是宿主适配，不应让 Codex happy path 多一次无意义确认。

# Baseline 3：作为 child 返回

Feature workflow 以 `invocation_mode=child` 调用本技能完成结构整理。

正确行为：返回产物、Commit、CI 与 blocker 给 Feature workflow，不执行 Host Close，不询问是否结束会话。

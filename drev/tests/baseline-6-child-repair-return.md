# Baseline 6：批量修复 child 返回

本技能调用 Bug workflow 修复一批 TODO。

正确行为：传 `invocation_mode=child`；Bug workflow 返回 Commit/CI 后由本技能写 `修复SHA` 和验证摘要。Bug workflow 不执行最终结束 ASK。

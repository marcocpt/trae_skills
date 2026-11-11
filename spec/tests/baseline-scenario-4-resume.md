# 基线场景 4：Design 确认后恢复

Design 的 review、用户确认和 Commit 均有证据；Visual 尚未创建。状态文件的 `current_stage` 仍写着 Design review。

正确行为：以仓库和确认记录修正状态，从 Visual（UI Feature）继续，不重写或重问 Design。

# Baseline 5：TODO 后中断恢复

状态称已记录 TODO1-3；TODO 文件实际存在 TODO1-2，最近一次 ASK 选择 TODO3 但原子写入未成功。

正确行为：以文件证据为准，重试落盘 TODO3，保持编号 3；不重问路径、模式或前两条 disposition。

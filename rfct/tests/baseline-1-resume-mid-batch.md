# Baseline 1：批次中断恢复

状态记录当前处于 `execution`，批次 R3 已提交并 push，CI run 仍在进行；仓库证据与状态一致。

正确行为：从验证 R3 的 CI 继续，不重新生成报告、不重问 worktree、不重复提交 R3；CI 结束后再决定 Gate。

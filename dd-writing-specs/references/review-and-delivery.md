# Review and Delivery

## 目录

- [自检方向](#自检方向)
- [文档特定检查](#文档特定检查)
- [确认](#确认)
- [Delivery 边界](#delivery-边界)
- [恢复与补救](#恢复与补救)
- [Cleanup](#cleanup)

## 生命周期与派生（引用共享合同）

review 文件（逐批验证摘要、临时审查清单、已失效执行包）属于 `working`/`evidence`，详见 [dd-workflow-runtime/artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3。已关闭 finding 的逐批摘要只有在当前合同和必要证据已吸收后才可按 `retention` 清理；ADR 与当前 Gate evidence 保留（`unique_evidence=true` 需明确授权）。不在 writer 重定义生命周期表。

## 自检方向

通用 A/B/C 名称、语义和处理方式只取自 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md)。本文件只维护下列文档特有检查；三个方向都要执行并分别记录，不能把特有检查改成第二份通用定义。

## 文档特定检查

Requirements：

- A：项目章节、Scope／Out of Scope、P0 代码符号和 FR／NFR／AC 覆盖；
- B：术语、项目规则、目标与约束一致，可设计且无冲突；
- C：每个 FR 有 AC，AC 可观察。

Design：

- A：每个 FR 有模块映射，Scope 完整且 Design P0 无越界；
- B：与 Requirements／项目规则一致，模块职责、数据流、状态、耦合和扩展正确；
- C：关键状态与接口可计划、可测试，风险有可核对处置。

Visual：

- A：主流程、错误、空态、权限和边界状态覆盖完整且不展示 Out of Scope；
- B：状态名、交互和 Design 一致；
- C：UI AC 与真实可见证据映射，交互可操作。

Test Matrix：

- A：AC／失败路径覆盖、编号、Population 和 Scope 完整；
- B：测试层级、oracle、数值 policy 与上游版本一致；
- C：证据 schema、UI 可观测性、已有覆盖及缺口状态可核对。

## 确认

确认前展示自检结论：

- 三方向自检状态；
- 已修复项；
- 遗留建议；
- 综合结论。

无 blocker 后一次只 ASK 一个问题：

1. 确认本篇并进入下一篇；
2. 修改本篇并重新确认；
3. 回到上游。

即使用户口头说"直接提交"也应在已展示自检结论后获取明确选择，因为该选择是文档 Gate，而不是形式性会话结束 ASK。

确认后立即持久化文档路径、版本、内容指纹、blocker，以及 artifact-contract 定义的 `approval`。该记录允许同一 worktree 的下一篇消费；它不是 Git 或外部动作授权。

## Delivery 边界

内容 Gate 和 Delivery Gate 分开判定：

- 用户当前明确授权或工作流开始时已明确采用的项目策略要求 Git：按策略调用 `dd-git-workflow`；
- 用户明确禁止 Git：记录 `not-authorized`，不再询问，继续同一 worktree 的文档依赖；
- 未要求 Git：记录 `not-required`；
- 下游必须跨 worktree 或远程消费而 Delivery 尚未满足：只在该边界 `BLOCKED`，不撤销内容批准。

执行获准 Git 动作前检查：

- 只 stage 本 Stage；
- `git diff --cached --check`；
- 不含秘密/无关脏文件；
- 不使用 `--no-verify`；
- 公共文件遵循 `PublicFile`；
- 所需 Commit 可从 `git log` 找到。

默认不 squash。若用户另行要求整理历史，交给 Git Delivery 流程重新确定安全边界，不能包含父工作流或他人提交。

## 恢复与补救

| 证据 | 恢复动作 |
|---|---|
| 文档已写入，自检未完成 | 补做 A/B/C 自检 |
| 自检结论已保存，用户未确认 | 展示现有结论后重新 ASK |
| 用户确认已持久化，Git 未要求或被禁止 | 保留内容批准；记 `not-required`／`not-authorized`，继续同一 worktree 下游 |
| 已明确要求 Commit，但证据缺失 | 停在 Delivery 边界，只补获准的当前 Stage 动作 |
| 下游基于未确认上游 | 标记 stale，回到上游 Gate |
| 单个方向缺失 | 只补该方向；若基线变化则三个都重跑 |
| 多个 Stage 被错误合并提交 | 记录违规，不用破坏性 reset；从当前可追溯基线继续并保持后续边界 |

补救优先保留已验证证据，但不得复用基于错误前提的文本。是否失效由上游语义是否变化决定，不按“文件存在”猜测。

## Cleanup

删除本技能创建的：

- `.step0-rules-summary.md`
- `.step1-requirements-summary.md` 或 `.step1-requirements-confirmed.md`

不删除父 Feature workflow 的 seed/state。cleanup 后更新内容指纹和状态；仅当已明确交付策略要求时提交 cleanup。
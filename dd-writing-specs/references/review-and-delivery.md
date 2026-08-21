# Review and Delivery

## 目录

- [自检方向](#自检方向)
- [文档特定检查](#文档特定检查)
- [确认](#确认)
- [提交边界](#提交边界)
- [恢复与补救](#恢复与补救)
- [Cleanup](#cleanup)

## 自检方向

写作时同步覆盖 A/B/C 三个方向：

| 方向 | 通用问题 |
|---|---|
| A | 章节/占位符/内部一致性/项目规则/P0 分层 |
| B | Scope/YAGNI/职责/耦合/可扩展与可测试 |
| C | FR/AC/证据映射/UI 可观测性/遗漏测试 |

三个方向都必须检查，禁止压成一个模糊的"整体看起来没问题"。发现问题立即修复，只把会阻塞下游设计、实现或验证的问题列为必须修复；措辞偏好列建议。

## 文档特定检查

Requirements：

- A：12 章/项目规则、P0 代码符号搜索；
- B：可设计性、范围、YAGNI；
- C：每个 FR 有 AC，AC 可观察。

Design：

- A：与 Requirements、docs.md、Design P0；
- B：模块职责、耦合、扩展、测试；
- C：状态/数据流、每个 FR 有模块映射。

Visual：

- A：与 Design 一致、状态完整；
- B：交互、错误和边界可操作；
- C：UI AC 与可见证据映射。

Test Matrix：

- A：AC 覆盖和编号；
- B：测试层级、策略和证据；
- C：UI 矩阵、已有测试对照、缺口诚实。

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

## 提交边界

每个可保存 Stage 独立提交：

- rules summary；
- grill/seed check；
- Requirements（自检后确认提交）；
- Design + confirm；
- Visual + confirm；
- Test Matrix + confirm；
- 临时笔记 cleanup。

提交前检查：

- 只 stage 本 Stage；
- `git diff --cached --check`；
- 不含秘密/无关脏文件；
- 不使用 `--no-verify`；
- 公共文件遵循 `PublicFile`；
- Commit 可从 `git log` 找到。

默认不 squash。若用户另行要求整理历史，交给 Git Delivery 流程重新确定安全边界，不能包含父工作流或他人提交。

## 恢复与补救

| 证据 | 恢复动作 |
|---|---|
| 文档已写入，自检未完成 | 补做 A/B/C 自检 |
| 自检结论已保存，用户未确认 | 展示现有结论后重新 ASK |
| 用户确认已持久化，Commit 缺失 | 只补当前 Stage Commit |
| 下游基于未确认上游 | 标记 stale，回到上游 Gate |
| 单个方向缺失 | 只补该方向；若基线变化则三个都重跑 |
| 多个 Stage 被错误合并提交 | 记录违规，不用破坏性 reset；从当前可追溯基线继续并保持后续边界 |

补救优先保留已验证证据，但不得复用基于错误前提的文本。是否失效由上游语义是否变化决定，不按“文件存在”猜测。

## Cleanup

删除本技能创建的：

- `.step0-rules-summary.md`
- `.step1-requirements-summary.md` 或 `.step1-requirements-confirmed.md`

不删除父 Feature workflow 的 seed/state。cleanup 作为独立 Commit，随后写最终状态/Receipt。

---
name: dd-bug-fast-track
description: 当用户要尽快把 Bug 修好能马上用、不想先走完整根因调查和多轮确认时使用；先复述症状与期望对齐一次，之后不再询问、不再复核，直接最小修复到症状消失，再回头补复现测试、根因证据与回归验证。触发词：快速修 bug、速通修 bug、先修好再说、先能用再说、精简版 bug 流程、fast track、hotfix。
---

# Bug 修复速通

## 目标

让用户在最短路径内拿到症状已消失、可以立即使用的修复：一次症状复述对齐后，中途不再询问、不再复核，直接做最小修复；随后在同一环境下补齐复现测试、根因证据、回归 CI 与文档。

本 Skill 只改变顺序与询问密度，不改变验收标准。症状消失不等于根因已证明，补齐阶段逐条关闭欠账才算完成。

## 不适用

- 用户只要求诊断、未授权修复 → 停在诊断结论，用 `dd-bug-fix-workflow`；
- 用户要的是完整证据驱动流程（稳定复现 → 单变量假设 → 根因证明 → 回归 CI）→ `dd-bug-fix-workflow`；
- 新功能或行为扩展 → `dd-feature-fast-track` 或 `dd-feature-development-workflow`；
- 症状无法用一句话说清"什么操作、看到什么、期望什么"——复述会反复失败，直接转 `dd-bug-fix-workflow` 的 Intake；
- 数据损坏、安全事件或线上事故取证类问题：需要先保全证据，不走速通。

## 运行时

开始或恢复时调用 `dd-workflow-runtime`：

```yaml
workflow_type: bug-fast-track
host: auto
invocation_mode: standalone
requested_entry: user-request
state_file: $(git rev-parse --git-dir)/bug-fast-track-state.json
stage_graph: bug-fast-track-stage-graph
required_exit_stages:
  - intake
  - fast-fix
  - smoke
  - backfill
  - closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。

速通模式的通用语义（泳道划分、可省／不可省清单、欠账台账 schema、补齐顺序、恢复、红线）唯一属主是 [fast-track-contract](../../dd-workflow-runtime/references/fast-track-contract.md)；本 Skill 只定义 Bug 领域的差异。

## 工作流怎么运行

1. **复述症状并取得确认**——唯一一次询问：现在看到什么、期望是什么、这次修到哪个范围；
2. **按推荐项直接做最小修复**——先新建隔离 fix worktree（强制，不询问；例外只有恢复复用已有 fix worktree 与用户明确要求在当前工作区），快速定位后改最小一处，中途不打断、不复核、不派审查，自主判断记入 `decisions`；
3. **冒烟自证并交付可用产物**——真实跑一次确认症状消失，UI Bug 用真实路径证据，告诉用户怎么立刻验证；
4. **进入补齐**——补复现测试与红绿对照、补根因证据、补回归 CI、补文档，逐条关闭欠账并附证据；
5. **收尾或交接**——欠账全清则写 Completion Receipt 并 Host Close；根因无法证明或命中升级触发器则交接 `dd-bug-fix-workflow`。

## 核心不变量

1. 全程只询问一次（症状复述对齐），其余按推荐执行并记录；
2. 首次建立执行环境必须新建隔离 fix worktree，且在修改项目产物之前完成；例外只有恢复任务复用已提供 worktree（仅验证不重建）和用户明确要求在当前工作区（须记 `reason`）；
3. 速通阶段不得宣称根因已证明，只能记"疑似根因 + 待补证据"；
4. 冒烟必须真实跑通，用户可见 Bug 必须真实路径证据；
5. 补齐阶段的复现测试必须在回退实现上验证红、在修复实现上验证绿；
6. 症状消失 ≠ 根因已证明 ≠ 验收通过；
7. 内容完成不等于 Git 或外部动作授权；
8. 根因无法证明时交接，不关闭根因欠账。

## Stage 路由

固定顺序：

```text
intake → fast-fix → smoke → backfill → closure
```

| Stage | 实际要做什么 | 完成标志 | 详细规则 |
|---|---|---|---|
| Intake | 复述症状、期望行为与修复范围并取得确认；确定并持久化工作环境——新建隔离 fix worktree，且在修改任何项目产物之前完成（仅恢复任务复用已有 fix worktree、或用户明确要求在当前工作区时才例外，后者须记 `reason`）；并在本 Stage Gate 前完成一次 tracking 绑定尝试 | 症状复述已获用户确认，隔离 fix worktree 已新建或已复用并验证且已持久化，tracking 绑定结果已按 owner 合同落盘（绑定失败不阻塞本 Stage） | [fast-track.md](references/fast-track.md) |
| Fast Fix | 快速定位后做最小修复，不改无关行为，不宣称根因；自主判断记入 `decisions` | 修改完成，构建可过，`decisions` 已记录 | [fast-track.md](references/fast-track.md) |
| Smoke | 真实运行确认症状消失；用户可见 Bug 取真实路径证据；交付可用产物与验证步骤 | 症状已消失且有真实证据，欠账台账已写入并持久化 | [fast-track.md](references/fast-track.md) |
| Backfill | 补复现测试与红绿对照 → 补根因证据 → 补回归 CI → 补文档，逐条关闭欠账并附证据 | 所有 `open` 欠账为 `closed` 或经用户确认 `waived`，验证绑定同一最终 SHA | [backfill.md](references/backfill.md) |
| Closure | 写 Completion Receipt 或交接正式流程，按宿主合同收尾 | Receipt 已写或交接已记录，`status=completed` | [backfill.md](references/backfill.md) |

- 测试位置与 CI：[test-location](../../dd-workflow-runtime/references/test-location.md) 与 [ci](../../dd-workflow-runtime/references/ci.md)；
- UI 证据新鲜度：[ui-evidence](../../dd-workflow-runtime/references/ui-evidence.md)；
- 外部任务绑定与投影（Intake Gate 前一次绑定尝试，不阻塞）：[task-tracking](../../dd-workflow-runtime/references/task-tracking.md)；
- 诊断、交付与清理的正式规则（交接时用）：[diagnosis-and-verification](../dd-bug-fix-workflow/references/diagnosis-and-verification.md) 与 [delivery-and-closure](../dd-bug-fix-workflow/references/delivery-and-closure.md)。

## 通用质量 Gate

- 修复范围不超出复述确认的边界，速通不夹带无关重构；
- 用户可见 Bug 不能只用内部状态、mock 或日志证明；
- 不得为了绿灯修改既有测试的预期；改预期必须有复述确认或用户明确表态；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- Git 操作遵循 `dd-git-workflow`，不在 fix 分支夹带无关公共文件修改。

## 红线

### 询问纪律

- 未复述症状就修改项目产物；
- 复述未获确认（含 null、取消）就往下走；
- 速通阶段除 fast-track-contract §3.2 四种例外外再次询问或插入复核；
- 把"用户催得急"推断为免检或免补。

### 工作环境纪律

- 未新建隔离 fix worktree 就修改项目产物（恢复任务复用已提供 fix worktree、用户明确要求在当前工作区的例外除外）；
- 用当前工作区却不把原因写入 `reason`；
- 中途切换 worktree，或在隔离 fix worktree 之外修改交付范围内文件。

### 根因纪律

- 速通阶段宣称"根因已查明/已证明"；
- 一次改多个变量还声称因果成立；
- 无红绿对照就关闭复现测试欠账；
- 根因无法证明仍关闭根因欠账（应交接正式流程）。

### 欠账与交付

- 未做 tracking 绑定尝试、也未按 owner 合同记录结果就通过 Intake Gate；
- 省掉的产物不登记欠账；
- 无 `evidence` 就把欠账标 `closed`，或在速通阶段 waive；
- 用"症状没了"替代正式流程的验收结论；
- 把速通产出解释为 commit、push、merge 或发布授权；
- 状态未持久化就跨 Stage；
- Trae 完成后直接结束会话。

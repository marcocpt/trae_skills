---
name: dd-feature-fast-track
description: 当用户要尽快拿到能跑起来的新功能、不想先走规格套件和多轮确认时使用；先复述需求对齐一次，之后不再询问、不再复核，直接实现到可用，再回头补齐规格、测试与验证。触发词：快速实现、速通、先跑起来、先能用再说、精简版新特性流程、fast track、lite 流程。
---

# 新特性速通

## 目标

让用户在最短路径内拿到可以立即使用的实现：一次需求复述对齐后，中途不再询问、不再复核，直接实现到可运行；随后在同一环境下补齐正式流程的产物、测试与验证。

本 Skill 只改变顺序与询问密度，不改变验收标准。速通通过不等于验收通过，补齐阶段逐条关闭欠账才算完成。

## 不适用

- 用户要的是完整流程（规格套件先行、多 Phase、独立强审）→ `dd-feature-development-workflow`；
- Bug 修复 → `dd-bug-fast-track` 或 `dd-bug-fix-workflow`；
- 项目 Bootstrap：→ `dd-project-bootstrap-workflow`；
- 纯文档微调、只读审查；
- 需求无法在一句话内说清范围边界与验收——复述会反复失败，直接转 `dd-feature-development-workflow` 的 Intake。

## 运行时

开始或恢复时调用 `dd-workflow-runtime`：

```yaml
workflow_type: feature-fast-track
host: auto
invocation_mode: standalone
requested_entry: user-request
state_file: $(git rev-parse --git-dir)/feature-fast-track-state.json
stage_graph: feature-fast-track-stage-graph
required_exit_stages:
  - intake
  - fast-implementation
  - smoke
  - backfill
  - closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。

速通模式的通用语义（泳道划分、可省／不可省清单、欠账台账 schema、补齐顺序、恢复、红线）唯一属主是 [fast-track-contract](../../dd-workflow-runtime/references/fast-track-contract.md)；本 Skill 只定义新特性领域的差异。

## 工作流怎么运行

1. **复述需求并取得确认**——唯一一次询问，说清要解决什么问题、范围边界、怎样算能用；复述未确认就重问，不得默认通过；
2. **按推荐项直接落地**——先新建隔离 worktree（强制，不询问；例外只有恢复复用已有 worktree 与用户明确要求在当前工作区），按推荐方案一口气实现完，中途不打断、不复核、不派审查，所有自主选择记入 `decisions`；
3. **冒烟自证并交付可用产物**——真实构建／启动跑通主路径，UI 变化用真实路径证据，告诉用户怎么立刻用起来；
4. **进入补齐**——补测试与确定性验证、补规格、补 CI 与审查、补文档，逐条关闭欠账并附证据；
5. **收尾或交接**——欠账全清则写 Completion Receipt 并 Host Close；命中正式流程升级触发器则交接 `dd-feature-development-workflow` 收尾，不在速通里降级。

## 核心不变量

1. 全程只询问一次（需求复述对齐），其余按推荐执行并记录；
2. 首次建立执行环境必须新建隔离 worktree，且在修改项目产物之前完成；例外只有恢复任务复用已提供 worktree（仅验证不重建）和用户明确要求在当前工作区（须记 `reason`）；
3. 速通阶段省掉的每一项都进欠账台账；
4. 冒烟必须真实跑通，UI 必须真实路径证据；
5. 补齐以已确认需求为基准，不以实现现状为基准；
6. 速通通过 ≠ 验收通过；
7. 内容完成不等于 Git 或外部动作授权；
8. 命中正式流程升级触发器时交接，不降级收尾。

## Stage 路由

固定顺序：

```text
intake → fast-implementation → smoke → backfill → closure
```

| Stage | 实际要做什么 | 完成标志 | 详细规则 |
|---|---|---|---|
| Intake | 用通俗语言复述需求（问题、范围边界、验收口径）并取得确认；同时确定并持久化工作环境——新建隔离 worktree，且在修改任何项目产物之前完成（仅恢复任务复用已有 worktree、或用户明确要求在当前工作区时才例外，后者须记 `reason`）；并在本 Stage Gate 前完成一次 tracking 绑定尝试 | 需求复述已获用户确认，隔离 worktree 已新建或已复用并验证且已持久化，tracking 绑定结果已按 owner 合同落盘（绑定失败不阻塞本 Stage） | [fast-track.md](references/fast-track.md) |
| Fast Implementation | 按推荐方案一次实现完，不做阶段复核与独立审查，自主选择记入 `decisions`；只在命中询问例外时才停 | 实现完成，构建可过，`decisions` 已记录 | [fast-track.md](references/fast-track.md) |
| Smoke | 真实构建／启动并跑通主路径；UI 变化取真实路径证据；把「怎么立刻用起来」交给用户 | 主路径真实跑通，UI 证据有效，欠账台账已写入并持久化 | [fast-track.md](references/fast-track.md) |
| Backfill | 补测试与确定性验证 → 补规格 → 补 CI 与审查 → 补文档，逐条关闭欠账并附证据 | 所有 `open` 欠账为 `closed` 或经用户确认 `waived`，验证绑定同一最终 SHA | [backfill.md](references/backfill.md) |
| Closure | 写 Completion Receipt 或交接正式流程，按宿主合同收尾 | Receipt 已写或交接已记录，`status=completed` | [backfill.md](references/backfill.md) |

- 审查等级与风险触发器语义：[review-gate](../../dd-workflow-runtime/references/review-gate.md)；
- 测试位置与 CI：[test-location](../../dd-workflow-runtime/references/test-location.md) 与 [ci](../../dd-workflow-runtime/references/ci.md)；
- UI 证据新鲜度：[ui-evidence](../../dd-workflow-runtime/references/ui-evidence.md)；
- 外部任务绑定与投影（Intake Gate 前一次绑定尝试，不阻塞）：[task-tracking](../../dd-workflow-runtime/references/task-tracking.md)；
- 交接正式流程时的 Handoff 字段：[state-and-handoff](../dd-feature-development-workflow/references/state-and-handoff.md)。

## 通用质量 Gate

- 实现遵循当前 worktree 的项目规则；
- UI 验收不能只由内部状态、mock、日志或组件渲染证明；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件。

## 红线

### 询问纪律

- 未复述需求就修改项目产物；
- 复述未获确认（含 null、取消）就往下走；
- 速通阶段除 fast-track-contract §3.2 四种例外外再次询问或插入复核；
- 用"用户说越快越好"推断出免检或免补。

### 工作环境纪律

- 未新建隔离 worktree 就修改项目产物（恢复任务复用已提供 worktree、用户明确要求在当前工作区的例外除外）；
- 用当前工作区却不把原因写入 `reason`；
- 中途切换 worktree，或在隔离 worktree 之外修改交付范围内文件。

### 欠账纪律

- 未做 tracking 绑定尝试、也未按 owner 合同记录结果就通过 Intake Gate；
- 省掉的产物不登记欠账；
- 无 `evidence` 就把欠账标 `closed`，或在速通阶段 waive；
- 欠账只存在于会话上下文或 TodoWrite。

### 补齐纪律

- 补齐阶段照抄实现现状当规格，或用实现反向改写已确认需求；
- 跳过测试与确定性验证直接跑 CI；
- 命中升级触发器仍在速通内降级收尾。

### 交付与会话

- 把速通产出解释为 commit、push、merge 或发布授权；
- 用"已经能跑起来"替代正式流程的验收结论；
- 状态未持久化就跨 Stage；
- Trae 完成后直接结束会话。

---
name: dd-feature-development-workflow
description: 当实现需要规格套件、分阶段计划、TDD、CI 或用户可见 UI 证据的新功能、大规模重构或 API 迁移时使用；也用于接收 project-bootstrap Handoff，或恢复长期运行的 Feature 工作流。触发词：新特性流程、feature development workflow、规格文档套件先行、分阶段计划、Feature Handoff。
---

# 新特性实现工作流

## 目标

把已确认的 Feature 从需求输入推进到已验证、可恢复的完成状态。主文件拥有整体执行叙事：目标、工作流概览、Stage 路由与跨 Stage 红线，第一次阅读即可理解一个 Feature 从需求到交付怎么走；每个 Stage 的详细规则由对应 reference 唯一拥有，进入具体 Stage 时再按路由表打开。

## 不适用

- Bug 修复：使用 `dd-bug-fix-workflow`；
- 项目级 Bootstrap：使用 `dd-project-bootstrap-workflow`；
- 简单文本或纯文档微调：直接使用对应工具或 writer；
- 只读审查。

## 工作流怎么运行

一个 Feature 从需求到交付的大致旅程：

1. 收集并确认需求，复用已有 Handoff 和已解决事实，不重复询问；
2. 固定工作环境并确认基线；
3. 调用 `dd-writing-specs` 生成并批准 Requirements、Design、Test Matrix，UI 功能按需包含 Visual；
4. 从已批准规格拆出 Phase 和可执行 Task；
5. 按 Phase → Task → TDD 实现，每个 Phase 必须通过 Local Gate；
6. 根据真实实现同步受影响文档；
7. 冻结最终候选 SHA——实现和文档完成后锁定、等待最终验证和交付的唯一版本；
8. 对同一个 SHA 做确定性验证、独立审查、完整规格缺口检查（从整套已批准规格反查遗漏、越界或未验证项）和完整 CI；
9. 确认阶段决定继续交付还是回退；继续交付时仅按既有动作级授权推进同一个已验证候选 SHA，缺少所需授权时停在对应动作边界并保留证据——授权检查发生在每个 Git／远端动作边界（包括冻结候选阶段的分支 push），不是只在最后一步；
10. 完成交付、清理、状态收尾和 Host Close。

其中规格、计划、实现、文档主要负责形成内容；候选阶段负责冻结与最终验证；只有 Delivery 推进目标分支，而任何 Stage 的 Git／远端动作都必须服从既有动作级授权。

## 运行时

开始或恢复时调用 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)：

```yaml
workflow_type: feature-development
host: auto
requested_entry: user-request-or-bootstrap-handoff
state_file: $(git rev-parse --git-dir)/feature-development-state.json
stage_graph: feature-stage-graph
required_exit_stages:
  - intake
  - environment
  - specification
  - planning
  - implementation
  - documentation
  - final-candidate
  - confirmation
  - delivery
  - closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。

## 核心不变量

1. 没有已批准规格，不修改生产代码；
2. 已解决事实继承，状态和仓库证据支持恢复，不重复询问；
3. 每个 AC 必须能追到 Task 和 Test/Evidence；
4. 每个 Phase 必须通过 Local Gate 才能继续；
5. 用户可见行为必须有用户可见证据；
6. 最终候选必须冻结，审查 / 完整规格缺口检查 / 完整 CI 绑定同一个 SHA；
7. 内容批准、测试 PASS、审查者 PASS 只证明 Workflow Gate，不自动产生 Git 或外部动作授权。

## Stage / Gate 图

五个对外 Gate 是内部十个可恢复 Stage 的聚合命名；内部仍按 Stage 推进。

```text
Source Gate:   intake → environment → specification
Plan Gate:     planning
Phase Gate:    implementation (× N Phase)
Candidate Gate: documentation → freeze candidate SHA
              → deterministic verification
              → one independent A/B/C review + full-spec gap
              → Full CI on exact SHA
Delivery Gate: confirmation → authorized same-SHA promote → delivery → closure
```

候选 Gate 只产出并验证可交付候选，不更新 develop/main；目标分支推进只发生在 Delivery Gate。

Gate 结果与 Delivery 状态分开持久化：Candidate 可以 `PASS`，而 Delivery 同时为 `not-required`、`not-authorized`、`pending` 或 `completed`。

固定 Stage 顺序：

```text
intake → environment → specification → planning → implementation
→ documentation → final-candidate → confirmation → delivery → closure
```

恢复任务从第一个未满足 Gate 的 Stage 继续；禁止重复已验证 Stage 或绕过缺失依赖。

## Stage 路由（每 Stage 一行）

| Stage | 实际要做什么 | 完成标志 | 详细规则 |
|---|---|---|---|
| Intake | 确认 Feature 的目标、范围、成功标准、失败路径、兼容性及可验证 AC，只补尚未解决的 blocker | 需求事实已确认并持久化 | [intake-and-environment.md](references/intake-and-environment.md) |
| Environment | 固定唯一 worktree，验证基线和并发状态 | 工作环境与状态一致，可安全进入规格阶段 | [intake-and-environment.md](references/intake-and-environment.md) |
| Specification | 调用 `dd-writing-specs` 生成并批准 Requirements、Design、Test Matrix；UI 功能按需生成 Visual | canonical spec 已批准，并有当前内容指纹和批准依据 | [specification.md](references/specification.md) |
| Planning | 从已批准规格生成 Phase 和可执行 Task 包，建立 AC → Task → Test/Evidence 映射 | 所有 Phase/Task 输入输出、写入范围、验证方式和停止条件都明确 | [planning-stage.md](references/planning-stage.md) |
| Implementation | 按当前 Task 的 `anchors`、全局约束、Out of Scope、失败路径及必要集成输入选择性读取规格（不完整重读）；按 Phase 执行 Task 并采用 TDD；每个 Phase 通过 Local Gate 并完成按风险路由的紧凑 Phase 复核（命中风险触发器时升级独立强审）；高风险 UI 按风险触发远程 Smoke CI；Local Gate 未通过不得进入下一 Phase | 全部 Phase 已验证，无未解释的当前 Phase 缺口 | [implementation.md](references/implementation.md) |
| Documentation | 根据最终已验证行为判断哪些长期文档需要更新、无需更新或已过期 | 文档与即将冻结的实现一致 | [documentation.md](references/documentation.md) |
| Final Candidate | 冻结候选 SHA；对同一个 SHA 做确定性验证、独立审查、完整规格缺口检查和 Full CI。候选 Gate 只产出并验证可交付候选，不推进目标分支 | review / gap / CI 均绑定同一 `candidate_sha` 并通过 | [candidate.md](references/candidate.md) |
| Confirmation | 确认继续交付还是回退，不修改候选内容 | 继续或回退的决策已记录并持久化；仅当决定继续时才进入 Delivery | [candidate.md](references/candidate.md) |
| Delivery | 仅在已有 action-specific authorization 的范围内推进同一个 `candidate_sha` | 要求且获授权的交付动作都有证据 | [delivery-and-closure.md](references/delivery-and-closure.md) |
| Closure | 验证最终状态、写 Completion Receipt、按规则清理并完成 Host Close | 成功路径的状态或 Completion Receipt 为 `completed`，所需清理已验证并按宿主合同收尾；`paused` 不是完成 | [delivery-and-closure.md](references/delivery-and-closure.md) |

- Bootstrap Handoff、Feature state、legacy `current_step` mapping 与恢复：[state-and-handoff.md](references/state-and-handoff.md)；
- Planning 模板（source_manifest / 任务结构）：[planning.md](references/planning.md)；
- 来源／执行包／验证证据包／生命周期共享合同：[artifact-contract](../dd-workflow-runtime/references/artifact-contract.md) 是路由器，详细合同在其三个分文件 `artifact-source-and-packet.md`／`artifact-verification.md`／`artifact-lifecycle.md`；
- A/B/C 审查与风险升级：[review-gate](../dd-workflow-runtime/references/review-gate.md)；
- 测试位置与 CI：[test-location](../dd-workflow-runtime/references/test-location.md) 和 [ci](../dd-workflow-runtime/references/ci.md)。

## 通用质量 Gate

- 规格和实现遵循当前 worktree 中的项目规则；
- UI AC 不能只由内部状态、mock、日志、layer count 或组件渲染证明；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件。

## 红线

### 规格与证据

- 没有已批准规格或有效 Bootstrap 输入就修改生产代码；
- 用摘要替代批准原文，或在来源指纹／批准依据失效后继续执行旧包；
- 把验证计划、测试存在／覆盖、本次运行和证据有效性合并成一个“已通过”；

### 授权边界

- 把内容批准解释成 Commit／Push／外部动作授权；

### 状态与恢复

- 重问 Handoff 或状态中已解决事实；
- 跨 worktree 引用未提交状态；
- 状态未持久化就跨 Stage；
- merge、push 或 cleanup 成功前删除唯一状态；

### 阶段纪律

- 未通过 Phase Local Gate 就进入下一 Phase；
- Phase ≥ 3 时只用一个总计划文件包含所有 Phase，或使用 planning reference 不传 `split_mode` 与 `phase_list`；
- 完整 CI 没有验证最终候选 SHA 就推进 develop；
- 候选过期或内容变化后仍推进，或 Documentation 在候选冻结后才做；

### UI 证据与会话收尾

- 用内部状态宣称 UI 已验证；
- Trae 完成后直接结束会话。

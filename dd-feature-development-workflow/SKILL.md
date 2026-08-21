---
name: dd-feature-development-workflow
description: 当实现需要规格套件、分阶段计划、TDD、CI 或用户可见 UI 证据的新功能、大规模重构或 API 迁移时使用；也用于接收 project-bootstrap Handoff，或恢复长期运行的 Feature 工作流。触发词：新特性流程、feature development workflow、规格文档套件先行、分阶段计划、Feature Handoff。
---

# 新特性实现工作流

## 目标

把已确认的 Feature 从需求输入推进到已验证、已交付、可恢复的完成状态。主文件只负责编排、状态、Gate 和路由；规格、实现、CI 与清理细节按当前 Stage 读取 references。

## 不适用

- Bug 修复：使用 `dd-bug-fix-workflow`；
- 项目级 Bootstrap：使用 `dd-project-bootstrap-workflow`；
- 简单文本或纯文档微调：直接使用对应工具或 writer；
- 只读审查。

## 运行时

开始或恢复时调用 [dd-shared-workflow-runtime](../dd-shared-workflow-runtime/SKILL.md)：

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
  - final-candidate
  - confirmation
  - documentation
  - delivery
  - closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。现有 `current_step`/`current_phase` 作为兼容字段保留，但必须与 `current_stage` 一致。

## 核心原则

1. No approved specification, no production code；
2. Resolved Bootstrap facts are inherited；
3. Every Phase ends with a local quality Gate；
4. High-risk UI changes get remote Smoke CI；
5. The exact merge candidate entering develop gets full CI；
6. User-visible behavior requires user-visible evidence；
7. Persist before every Stage transition；
8. Trae completion requires a final ASK。

## Stage Graph

```text
Preflight
  ↓
Intake
  ↓
Environment
  ↓
Specification
  ↓
Planning
  ↓
Implementation
  ├─ Phase TDD
  ├─ Local Gate
  └─ Risk-based UI Smoke
  ↓
Final Candidate + Full CI + Promote
  ↓
Confirmation
  ↓
Documentation
  ↓
Delivery
  ↓
Closure
```

新任务按依赖推进；恢复任务从第一个未满足 Gate 的 Stage 继续。禁止重复已验证的 Stage，也禁止绕过缺失依赖。

## Stage Contracts

| Stage | Requires | Produces | Next | Recovery evidence |
|---|---|---|---|---|
| Intake | 用户请求或有效 Handoff | 已确认需求摘要 | Environment | 摘要、decisions |
| Environment | Intake Gate | 固定 worktree、初始 state | Specification | Git 路径、基线结果 |
| Specification | Intake、Environment | 规格套件与 review | Planning | 文档路径、提交 |
| Planning | Approved specification | 总计划与 Phase 计划 | Implementation | 计划文件、提交 |
| Implementation | Approved plan | Phase commits、测试与 UI 证据 | Final Candidate | commits、Phase Gate、Smoke runs |
| Final Candidate | 全部 Phase Gate、最新 develop | 候选 SHA、完整 CI、同 SHA 推进 | Confirmation | candidate branch、run、目标分支 |
| Confirmation | 最终实现和验证证据 | 用户继续或回退决策 | Documentation / rollback | decision、rollback state |
| Documentation | 已验证交付行为 | 同步文档和影响结论 | Delivery | diff、文档版本、提交 |
| Delivery | Documentation Gate | lint/push/CI/同步证据 | Closure | SHA、CI run、远端状态 |
| Closure | 所有必需 Gate | completed Receipt 或 paused state | Host Close / resume | Receipt、清理结果、状态 |

## Bootstrap Handoff

Preflight 检查调用参数或 Git dir 中的 `project-bootstrap-state.json`。只消费 `status=handoff-ready` 且满足以下条件的 Handoff：

1. 支持的 `handoff_version`；
2. `source_workflow`、`source_state_path`、`worktree_path`、Goal、Scope、Mode、Selected Feature/Phase、Required Reading、Constraints 和 Verification 完整；
3. `blocking_questions` 为空，必需路径存在；
4. Handoff worktree 与当前工作树一致；
5. Greenfield 有非空 `requirements_seed`；
6. Brownfield 有 Baseline 与 `phase_contract_status=approved` 的 Phase Contract。

接收后继承已解决事实、工作环境和阅读清单。Greenfield 复用 Requirements Seed；Brownfield 复用 approved Phase Contract，禁止把 `KNOWN_DEFECT` 自动升级为 AC。只询问 Feature 特有 blocker。

Feature state 原子写入消费字段成功后，才把 Bootstrap state 改为 `completed`：

```yaml
bootstrap_handoff_consumed: true
bootstrap_state_path: /absolute/path/project-bootstrap-state.json
requirements_seed_source: bootstrap-requirements-seed
phase_contract_path: null
```

不完整 Handoff 返回 Bootstrap blocker，不猜测、不并行维护 `dd-writing-specs` 直达出口。

## Feature State

除运行时通用字段外记录：

```yaml
feature_name: ""
feature_number: F0
requirements_path: ""
design_path: ""
visual_path: null
test_case_path: ""
review_paths: []
plan_dir: ""
phase_plan_paths: []
integration_plan_path: null
current_phase: null
total_phases: 0
completed_phases: []
smoke_ci_phases: []
commits: {}
final_candidate_branch: null
final_candidate_sha: null
final_ci_run: null
final_ci_passed: false
bootstrap_handoff_consumed: false
bootstrap_state_path: null
phase_contract_path: null
```

旧状态中的 `current_step` 映射：

```text
0 → intake
1 → environment
2 → specification
3 → planning
4 / 4.x → implementation
5 / 5.x → final-candidate
6 → confirmation
7 → documentation
8 → delivery
9 / 9.x → closure
```

状态字段与产物、分支或 CI 证据冲突时，按运行时恢复合同修正后继续。状态缺失时至少检查工作分支提交、规格/计划文件、Phase 证据、候选分支和 CI 结果；禁止默认回到 Intake。

## Stage 路由

### Intake

读取 [specification-and-planning.md](references/specification-and-planning.md) 的 Intake。

收敛目标、成功标准、IN/OUT、流程、接口、兼容性、AC、Phase、UI 证据和文档位置。有效 Bootstrap Handoff 已回答的内容不得重问。Gate：需求摘要已确认并按项目提交策略持久化。

### Environment

读取 [specification-and-planning.md](references/specification-and-planning.md) 的 Environment。

有效 Handoff 必须复用其 worktree；否则首次写文件前选择隔离 worktree 或当前 worktree。Gate：路径固定、无并发工作流、工作区边界明确、基线证据有效、Feature state 已写入。

### Specification

读取 [specification-and-planning.md](references/specification-and-planning.md) 的 Specification。

调用 `dd-writing-specs` 完成 Requirements、Design、Visual（如适用）和 Test Cases。Gate：产物与自检有效、用户确认、路径写入状态、规格提交策略满足。

### Planning

读取 [specification-and-planning.md](references/specification-and-planning.md) 的 Planning。

按 Phase 数量强制拆分档位（`<HARD-GATE>`），调用 `writing-plans` 时显式传 `split_mode` 与 `phase_list`，禁止让 `writing-plans` 自行决定拆分。Gate：无占位符、AC 映射完整、验证与提交边界明确、`phase_plan_paths` 数组与 `split_mode` 一致、计划已按项目规则交付。

### Implementation

读取 [implementation-and-verification.md](references/implementation-and-verification.md) 的 Phase Loop、TDD、Local Gate 和 UI Smoke。

按 Phase 顺序执行；每个 Phase 必须完成 TDD、用户可见证据、本地 Gate 和风险判断。Gate：`completed_phases` 覆盖全部 Phase，状态和提交证据一致。

### Final Candidate

读取 [implementation-and-verification.md](references/implementation-and-verification.md) 的 Final Candidate。

基于最新 develop 创建准确候选提交，对该 SHA 执行完整远程 CI，通过后才推进同一提交。Gate：`final_candidate_sha` 可验证、`final_ci_passed=true`、目标分支包含同一 SHA。

### Confirmation

向用户展示实现、证据、CI 和已知边界，ASK 继续文档同步或回退到 Intake/Specification/Planning/Implementation/Final Candidate。回退必须更新状态和 `rollback_from`。

### Documentation

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Documentation。

按调用关系、数据流、共享模型和用户流程检查 Requirements、Design、Visual、Test Cases 与代码测试。Gate：文档与已交付行为一致，版本和证据已更新或有明确无需更新结论。

### Delivery

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Delivery。

按项目规则完成 lint、验证、commit、push、CI 和必要同步。Gate：所有必需 Delivery 动作有准确证据；失败项已解决或由用户明确处置。

### Closure

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Closure。

清理前验证 Phase、候选 SHA、完整 CI、目标分支和工作区状态。外部动作前持久化 `in_progress`。活动状态会随 worktree 删除时，先写 Completion Receipt。

选择保留未完成环境时设置 `paused`，不触发最终完成 ASK。真正完成后设置 `status=completed`，再按共享运行时执行 Host Close：Trae 必须 ASK `结束本次任务` / `还有其他任务`；Codex 正常交付。

## 通用质量 Gate

- 规格和实现遵循当前 worktree 中的项目规则；
- 每个 AC 映射到计划、测试或明确证据；
- UI AC 不能只由内部状态、mock、日志、layer count 或组件渲染证明；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- 测试位置与证书规则遵循 `test-location-strategy` 和 `dd-shared-ci`；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件。

## 红线

- 没有已批准规格或有效 Bootstrap 输入就修改生产代码；
- 重问 Handoff 或状态中已解决事实；
- 跨 worktree 引用未提交状态；
- 未通过 Phase Local Gate 就进入下一 Phase；
- Phase ≥ 3 时只用一个总计划文件包含所有 Phase，或调用 `writing-plans` 不传 `split_mode` 与 `phase_list`；
- 用内部状态宣称 UI 已验证；
- 完整 CI 没有验证最终候选 SHA 就推进 develop；
- 候选过期后仍推进；
- 状态未持久化就跨 Stage；
- merge、push 或 cleanup 成功前删除唯一状态；
- Trae 完成后直接结束会话。

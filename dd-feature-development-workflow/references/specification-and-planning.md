# Feature Specification and Planning

只在 Intake、Environment、Specification 或 Planning Stage 读取。

## 目录

- [Intake](#1-intake)
- [Environment](#2-environment)
- [Specification](#3-specification)
- [Planning](#4-planning)

## 1. Intake

### 输入复用

先消费有效 Bootstrap Handoff、状态、已批准文档和用户当前请求。只对仍缺失的 Feature blocker 进行 `grill-me`；不要把技术设计混入需求质询。

至少收敛：

1. 用户问题和业务目标；
2. 可观察成功标准；
3. IN / OUT；
4. 入口、主路径、失败路径、退出条件；
5. 数据、接口和持久化影响；
6. 兼容与迁移；
7. 可测试 AC 及验证方式；
8. Phase 与各阶段可交付结果；
9. UI 的真实交互与证据；
10. 功能编号、优先级和文档路径。

项目文档规则优先；无规则时使用 `docs/superpowers/specs/` 与 `docs/superpowers/plans/`。

### 摘要

需要与 `dd-writing-specs` 复用输入时写 `.feature-step0-requirements-summary.md`。只写已确认需求事实，不写技术方案。路径、名称和交付策略必须与下游调用合同一致。

Gate：

- 10 项信息已解决或明确标记不适用；
- blocker 为零；
- 用户确认需求摘要；
- 摘要已按项目提交策略持久化；
- 状态更新为 `current_stage=environment`。

## 2. Environment

有效 Bootstrap Handoff 必须复用 `worktree_path`，只验证路径、状态和基线，不重复询问。

无 Handoff 时，在首次写入前使用宿主可用的 ASK：

- 新建隔离 worktree；
- 使用当前 worktree。

选定后：

- 只参考该 worktree 中的规则、文档、代码和已提交证据；
- 禁止中途切换；
- 检查其他 active/paused/handoff-ready 工作流；
- 记录 `main_root`、`worktree_dir`、`base_branch` 和工作分支；
- 验证工作区状态与基线；
- 基线失败时说明现有失败与本 Feature 风险，再 ASK 排查或停止。

创建 worktree、分支命名和初始化遵循 `dd-git-worktree`、`dd-git-branch` 和项目脚本，不在本文件复制语言特定安装命令。

Gate：

- 当前路径与状态一致；
- 无并发冲突；
- 基线证据有效；
- Feature state 原子写入；
- Bootstrap 消费字段与上游完成状态写入成功；
- `current_stage=specification`。

## 3. Specification

调用 [dd-writing-specs](../../dd-writing-specs/SKILL.md)，传递：

```yaml
worktree_path: /absolute/path
feature_number: F0
priority: P0
document_dir: /absolute/or/repo-relative/path
requirements_summary_path: null
bootstrap_requirements_seed: []
phase_contract_path: null
resolved_decisions: []
review_level: standard
```

子 Skill 必须消费上游事实，不重复 grill。没有子 Agent 能力时在主线程执行相同的 Requirements → Design → Visual（如适用）→ Test Cases 与审查顺序。

产物：

- Requirements；
- Design；
- Visual Prototype（UI 相关时）；
- Test Case Matrix；
- Review records。

检查：

- Requirements 不含实现符号；
- Design 不复制 Requirements，职责与数据流明确；
- Visual 与 UI AC 对齐；
- Test Cases 覆盖 AC、失败路径、兼容性和证据；
- 用户确认整套规格；
- 所有路径存在且交付策略满足。

Gate 通过后写路径、review 结论、规格提交 SHA，并更新 `current_stage=planning`。

## 4. Planning

读取已批准的全部规格与 review，先识别 Phase 数量与依赖，再调用 `writing-plans`。

### 拆分档位（按 Phase 数量强制）

<HARD-GATE>
拆分档位由 Phase 数量强制决定，不得为省 token 或省轮次降档：

- Phase ≤ 2 且任务少（简单）：1 个总计划文件即可；
- Phase ∈ [3, 5]（中等）：每 Phase 1 个独立子计划文件；
- Phase ≥ 6 或跨子系统（复杂）：每 Phase 1 个独立子计划文件 + 1 个跨 Phase 集成计划文件。

「中等」与「复杂」档必须产出**独立 `.md` 文件**，禁止用同一文件内的 `## Phase N` 二级标题分区代替。判定依据是 Requirements 中已确认的 Phase 列表长度，不是主观估计「任务多少」。每个 Phase 子计划必须独立可执行、独立可回滚、独立 Local Gate。

Trae 宿主下不得以「总计划里分了 Phase 章节效果一样」「下游按 Phase 顺序读即可」为由降档；这些是合理化借口，参见 [baseline-4-planning-phase-split.md](../tests/baseline-4-planning-phase-split.md)。
</HARD-GATE>

### 调用 writing-plans 的合同

调用 [writing-plans](../../writing-plans/SKILL.md) 时必须显式传：

```yaml
invocation_mode: helper
worktree_path: /absolute/path
feature_number: F0
plan_dir: /absolute/or/repo-relative/path
requirements_path: /absolute/path
design_path: /absolute/path
test_case_path: /absolute/path
split_mode: simple | per-phase | per-phase-with-integration
phase_list:
  - phase_id: 1
    name: ""
    goal: ""
    in: []              # 上游 Phase 已固化的产物/接口
    out: []             # 本 Phase 必须产出的可验证产物
    dependencies: []    # 依赖哪些 Phase
    ac_keys: []         # Requirements 中 AC 编号
  - phase_id: 2
    ...
```

`split_mode` 由上方拆分档位决定：

- `simple`：`Phase ≤ 2`，`writing-plans` 产出 1 个总计划；
- `per-phase`：`Phase ∈ [3, 5]`，`writing-plans` 按 `phase_list` 逐 Phase 产出独立文件，命名 `plan-phase-<NN>-<slug>.md`；
- `per-phase-with-integration`：`Phase ≥ 6` 或跨子系统，在 `per-phase` 基础上额外产出 `plan-integration-cross-phase.md`。

禁止不传 `phase_list` 与 `split_mode`，让 `writing-plans` 自行决定拆分。`writing-plans` 的「独立子系统」拆分逻辑与本 Phase 拆分概念不对应，必须由本工作流显式驱动。

### 计划至少包含

- Goal、Architecture、Tech Stack；
- 精确文件和职责；
- Phase 目标、IN/OUT、依赖；
- 2–5 分钟任务；
- TDD 红/绿/重构；
- 精确验证命令和预期；
- UI 真实入口、操作、断言和证据；
- 提交边界和回滚；
- AC → Task → Test/Evidence 映射。

禁止 `TODO`、`待定`、笼统错误处理、未定义符号和“类似任务 N”。

### 复核与交付

复核方向：

1. 覆盖与范围；
2. 一致与正确；
3. 可验证与可观测。

必须修复项自动修复并复核；重大产品/架构变化才 ASK。计划达到项目交付要求后写入状态：

```yaml
plan_dir: /absolute/path
total_phases: <N>
phase_plan_paths:
  - phase_id: 1
    path: plan-phase-01-<slug>.md
  - phase_id: 2
    path: plan-phase-02-<slug>.md
integration_plan_path: plan-integration-cross-phase.md   # 仅复杂档
plan_commit_sha: <sha>
current_stage: implementation
current_phase: 0
```

### 红线

- Phase ≥ 3 时只用一个总计划文件包含所有 Phase；
- 调用 `writing-plans` 不传 `phase_list` 与 `split_mode`，让它自行决定拆分；
- 用同一文件内 `## Phase N` 二级标题代替独立文件；
- 复杂档缺失跨 Phase 集成计划；
- 状态文件未写 `phase_plan_paths` 数组就推进到 implementation。

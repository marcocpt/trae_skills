# Feature Planning Stage

只在 Planning Stage 读取。本文件只拥有 Phase 档位、`phase_list` 和对 [planning.md](planning.md) 的调用合同；计划内容生成语义由 planning.md 拥有。

从磁盘完整重读已批准的全部原始规格与 review，核对每份来源的版本、内容指纹和批准依据；摘要只用于定位，不能代替原文。然后识别 Phase 数量与依赖，再使用 planning reference。

## 拆分档位（按 Phase 数量强制）

<HARD-GATE>
拆分档位由 Phase 数量强制决定，不得为省 token 或省轮次降档：

- Phase ≤ 2 且任务少（简单）：1 个总计划文件即可；
- Phase ∈ [3, 5]（中等）：每 Phase 1 个独立子计划文件；
- Phase ≥ 6 或跨子系统（复杂）：每 Phase 1 个独立子计划文件 + 1 个跨 Phase 集成计划文件。

「中等」与「复杂」档必须产出**独立 `.md` 文件**，禁止用同一文件内的 `## Phase N` 二级标题分区代替。判定依据是 Requirements 中已确认的 Phase 列表长度，不是主观估计「任务多少」。每个 Phase 子计划必须独立可执行、独立可回滚、独立 Local Gate。

Trae 宿主下不得以「总计划里分了 Phase 章节效果一样」「下游按 Phase 顺序读即可」为由降档；这些是合理化借口，参见 [baseline-4-planning-phase-split.md](../tests/baseline-4-planning-phase-split.md)。
</HARD-GATE>

## Planning reference 调用合同

调用 [planning.md](planning.md) 时必须显式传：

```yaml
invocation_mode: helper
worktree_path: /absolute/path
feature_number: F0
plan_dir: /absolute/or/repo-relative/path
requirements_path: /absolute/path
design_path: /absolute/path
test_case_path: /absolute/path
delivery_policy: <inherited>
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

- `simple`：`Phase ≤ 2`，`planning reference` 产出 1 个总计划；
- `per-phase`：`Phase ∈ [3, 5]`，`planning reference` 按 `phase_list` 逐 Phase 产出独立文件，命名 `plan-phase-<NN>-<slug>.md`；
- `per-phase-with-integration`：`Phase ≥ 6` 或跨子系统，在 `per-phase` 基础上额外产出 `plan-integration-cross-phase.md`。

禁止不传 `phase_list` 与 `split_mode`，让 `planning reference` 自行决定拆分。`planning reference` 的「独立子系统」拆分逻辑与本 Phase 拆分概念不对应，必须由本工作流显式驱动。

## 计划至少包含

- Goal、Architecture、Tech Stack；
- 精确文件和职责；
- Phase 目标、IN/OUT、依赖；
- TDD 红/绿/重构；
- 精确验证命令和预期；
- UI 真实入口、操作、断言和证据；
- 提交边界和回滚；
- AC → Task → Test/Evidence 映射。

每个可执行 Task 必须按 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) 实例化弱模型执行包：Phase plan 头部定义唯一 `source_manifest`，Task 用 `sources: [{ref, anchors}]`。缺任一来源指纹、批准依据、输入／输出、写入范围、精确验证、停止条件或 Delivery 授权时保持 `BLOCKED`，不得进入 Implementation。

规格已冻结的事实引用不复制：

- 计划引用 Test ID / population ID / policy 版本，不手工复制完整 item registry、seed manifest 或追溯矩阵；
- 弱模型执行包可内联当前任务需要的冻结事实一次，但必须由 `sources` 逐项追溯；中间层总计划不得再复制一份。

禁止 `TODO`、`待定`、笼统错误处理、未定义符号和“类似任务 N”。

## 复核与交付

复核方向（A/B/C）：覆盖与范围、一致与正确、可验证与可观测。必须修复项自动修复并复核；重大产品/架构变化才 ASK。计划达到项目交付要求后写入状态：

```yaml
plan_dir: /absolute/path
total_phases: <N>
phase_plan_paths:
  - phase_id: 1
    path: plan-phase-01-<slug>.md
    source_manifest_digest: <sha256>
  - phase_id: 2
    path: plan-phase-02-<slug>.md
integration_plan_path: plan-integration-cross-phase.md   # 仅复杂档
plan_delivery_evidence: <commit-sha-or-not-required-or-not-authorized>
current_stage: implementation
current_phase: 0
```

## 红线

- Phase ≥ 3 时只用一个总计划文件包含所有 Phase；
- 使用 planning reference 不传 `phase_list` 与 `split_mode`，让它自行决定拆分；
- 用同一文件内 `## Phase N` 二级标题代替独立文件；
- 复杂档缺失跨 Phase 集成计划；
- 执行包缺来源内容指纹／批准依据、写入 allowlist、验证预期、停止条件或 Delivery 授权；
- 来源变化后直接手改执行包并继续，而非标记 stale、重新派生和复核；
- 状态文件未写 `phase_plan_paths` 数组就推进到 implementation。

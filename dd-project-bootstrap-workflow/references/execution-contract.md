# Bootstrap Execution Contract

按需读取本文件。首次触发读取 Preflight、State 和 Node Contract；进入 Handoff 时再读取 Handoff 与 Host Close。

## 1. Preflight

任何 requested entry 都先执行轻量 Preflight：

1. 读取当前 Git/worktree 状态和适用的 `AGENTS.md`/项目规则；
2. 检测宿主：Trae、Codex 或 other；
3. 检测宿主能力：结构化询问、子 Agent、Git 写入；
4. 恢复 `project-bootstrap-state.json`；不存在时从仓库事实重建；
5. 记录 `requested_entry`，但不把它当作无条件跳步的 `start_step`；
6. 识别项目模式，具体规则见 `brownfield-policy.md`；
7. 将已有产物标记为 `missing`、`partial`、`valid`、`stale` 或 `conflicting`；
8. 生成 `blocking_gaps` 和 `deferred_gaps`；
9. 只询问无法从仓库或状态确定的 blocker；
10. 首次修改文件前确定并持久化工作环境。

最小产物扫描：

```text
docs.md
docs/planning/路线图.md
docs/planning/功能列表.md
docs/planning/技术调研.md
docs/architecture/全局架构契约.md
docs/standards/CODING_STANDARDS.md
AGENTS.md
Brownfield Baseline artifacts
Phase Contract
```

不要为 Preflight 预加载整个 `docs/`。

## 2. State

状态遵循 [dd-workflow-runtime/state](../../dd-workflow-runtime/references/state.md)，使用：

```text
WORKFLOW_TYPE=project-bootstrap
file=$(git rev-parse --git-dir)/project-bootstrap-state.json
progress=current_node
```

Bootstrap 字段：

```yaml
schema_version: 1
workflow_type: project-bootstrap
status: active
project_mode: brownfield
host: trae
requested_entry: roadmap
current_node: brownfield-baseline
completed_nodes:
  - preflight
  - docs-governance
artifacts: {}
decisions: []
blocking_gaps:
  - brownfield-baseline
deferred_gaps: []
handoff: {}
```

每个 Node Gate 通过后立即更新状态。恢复时验证路径、产物、规则和当前节点；不能盲信 JSON。

## 3. Gap Scan

Gap 分类：

- `blocking`：requested entry 或 Exit Gate 的必需依赖；
- `deferred`：不影响 requested entry/Exit Gate，且已有明确负责人或触发条件；
- `conflict`：两个当前来源对同一事实给出不同结论，始终 blocking。

执行顺序由依赖决定，而非固定数字步骤。用户请求从 Roadmap 开始时，如果 Brownfield Baseline 缺失，先补 Baseline。

## 4. Node Contract

每个节点声明：

```yaml
requires: []
produces: []
gate: []
next: []
```

通用 Workflow Gate：

1. artifact exists；
2. artifact validated；
3. blocking decisions resolved；
4. state persisted；
5. blocking issues 为零。

Node Gate 不要求“最新 commit 必须是当前 artifact”。Git commit、push 和 PR 属于 Delivery Gate。

## 5. Dependency Graph

```text
Preflight
  ↓
Docs Governance
  ├─ Brownfield Baseline（Brownfield）
  └─ Research / Technical Validation（风险触发）
             ↓
           Roadmap
             ↓
    Architecture Contract
             ↓
      Coding Standards
             ↓
       AI Conventions
             ↓
 Phase Contract（Brownfield）
             ↓
           Handoff
```

节点合同：

### docs-governance

- requires：Preflight；
- produces：根目录 `docs.md` 或现有治理验证结果；
- gate：SSOT、目录、同步和阅读策略明确；
- next：Baseline / Research / Roadmap。

### brownfield-baseline

- requires：Brownfield mode、docs governance；
- produces：能力、使用关系、处置、Characterization 清单；
- gate：无未解释遗漏，REVIEW 明确记录；
- next：Research / Roadmap / Architecture。

### research

- requires：未验证高风险假设；
- produces：技术调研和候选 ADR；
- gate：每个关键结论有证据、风险和限制；
- next：Roadmap / Architecture。

### roadmap

- requires：docs governance、Baseline（Brownfield）、必要 Research；
- produces：Roadmap、功能列表；
- gate：Goal/IN/OUT/Exit Gate、依赖和首个 Feature 明确；
- next：Architecture。

### architecture-contract

- requires：Roadmap、Baseline（Brownfield）；
- produces：Architecture Contract、ADR Index；
- gate：依赖方向、不变量、禁止方向、双 Public Surface 和状态明确；
- next：Coding Standards。

### coding-standards

- requires：Architecture、语言和工具链事实；
- produces：Coding Standards、commit 规则、语言/测试规则；
- gate：验证命令和 Greenfield/Brownfield 质量策略可执行；
- next：AI Conventions。

### ai-conventions

- requires：Architecture、Coding Standards、host；
- produces：`AGENTS.md`、按需 nested `AGENTS.md` 和宿主薄适配器；
- gate：入口短、引用有效、上下文策略和会话规则明确；
- next：Phase Contract / Handoff。

### phase-contract

- requires：Roadmap、Architecture、Baseline（Brownfield）；
- produces：`{X}_01_阶段需求与验收.md`；
- gate：处置分类正确、AC 可验证、REVIEW 为零；
- next：Handoff。

### handoff

- requires：模式所需全部节点；
- produces：结构化 Handoff；
- gate：目标、路径、约束、验证和下游明确；
- next：`dd-feature-development-workflow`。

## 6. Child Invocation

父工作流传递：

```yaml
project_mode: greenfield
host: codex
worktree_path: /absolute/path
resolved_decisions: []
artifact_paths: {}
blocking_questions: []
delivery_policy: project-rules
```

子 skill：

- 必须消费上游事实；
- 不得重新询问已解决事实；
- 只询问缺失 blocker 或产物特有的新决策；
- 发现上游冲突时返回 blocker；
- 独立触发时才执行自己的最小 Preflight。

## 7. 审查规则

审查遵循 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md)：主 Agent 按 A/B/C 三方向自检；命中高风险附加检查触发器时追加对应检查。检查语义不因执行方式简化而减少。

## 8. Delivery Gate

Delivery policy 来源顺序：

1. 用户当前明确要求；
2. 项目 `AGENTS.md` 和 Git 规则；
3. `dd-git-workflow`；
4. 安全默认。

Delivery 可包含 status、lint、test、commit、push、PR。Delivery 失败如实记录并处理，但不伪造 Node artifact 未完成。

## 9. Handoff

Greenfield/Brownfield 统一交给 `dd-feature-development-workflow`。

Payload：

```yaml
handoff_version: 1
source_workflow: project-bootstrap
source_state_path: /absolute/path/project-bootstrap-state.json
worktree_path: /absolute/path
goal: ""
scope: []
project_mode: greenfield
selected_feature_or_phase: F0
required_reading: []
relevant_files: []
constraints: []
requirements_seed: []
acceptance_criteria: []
verification: []
out_of_scope: []
resolved_decisions: []
open_non_blocking_items: []
blocking_questions: []
baseline_path: null
phase_contract_path: null
phase_contract_status: null
delivery_policy: project-rules
```

Greenfield 必须携带非空 Requirements Seed，`phase_contract_path=null`。Brownfield 必须携带 Baseline 与 approved Phase Contract，`phase_contract_status=approved`；已知缺陷不得自动进入 `acceptance_criteria`。

Handoff 写入 Bootstrap state 并设 `status=handoff-ready`。`dd-feature-development-workflow` 验证 payload、路径和工作树，先写入自己的 Bootstrap 消费字段，再把 Bootstrap state 改为 `completed`。

下游状态必须记录：

```yaml
bootstrap_handoff_consumed: true
bootstrap_state_path: /absolute/path/project-bootstrap-state.json
requirements_seed_source: bootstrap-requirements-seed
phase_contract_path: null
```

不得同时向 Greenfield 暴露 `dd-writing-specs` 直达出口；Feature workflow 是唯一消费者，由其内部按需调用规格 writer。

## 10. Host Close

询问遵循 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md)。

Trae：

1. Exit Gate 与 Handoff 完成后禁止直接结束；
2. ASK `结束本次任务` / `还有其他任务`；
3. “还有其他任务”继续接收；
4. ASK 前先持久化 completed，必要时写 Completion Receipt；
5. “结束本次任务”后输出最终摘要。

Codex：

- 正常交付已完成结果；
- 只有用户或项目规则要求时才追加结束确认。

# Feature State and Handoff

只在 Preflight、Bootstrap Handoff 消费或状态恢复时读取。本文件只保留 Feature 增量，不复制 `dd-workflow-runtime` 的通用 state 字段。

## 1. Bootstrap Handoff

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

## 2. Feature State

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
specification_approvals: []
execution_packet_paths: []
verification_evidence: []
current_phase: null
total_phases: 0
completed_phases: []
smoke_ci_phases: []
commits: {}
final_candidate_branch: null
final_candidate_sha: null
final_ci_run: null
final_ci_passed: false
candidate_review: null
full_spec_gap: null
candidate_ready: false
bootstrap_handoff_consumed: false
bootstrap_state_path: null
phase_contract_path: null
```

## 3. legacy `current_step` mapping

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

现有 `current_step`/`current_phase` 作为兼容字段保留，但必须与 `current_stage` 一致。

## 4. 恢复（evidence-first）

状态字段与产物、分支或 CI 证据冲突时，按运行时恢复合同修正后继续。状态缺失时至少检查工作分支提交、规格/计划文件、Phase 证据、候选分支和 CI 结果；禁止默认回到 Intake。

证据优先于状态字段：`current_stage` 与真实 diff／提交／CI 冲突时，以可复核证据为准，并把修正写入状态。

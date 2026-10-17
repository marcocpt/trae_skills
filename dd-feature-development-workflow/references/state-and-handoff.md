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
change_tier: full             # small | full，默认 full；判定与升级见 small-change-track.md
tier_rationale: null          # change_tier=small 时必填，逐条对应准入条件
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
tracer: null   # {decision, reason, target_ac, result, evidence_ref, limitations}，schema 唯一属主见 tracer-contract.md
commits: {}
final_candidate_branch: null
candidate_sha: null
candidate_review: null          # {level, execution, sha, review_ref}
full_spec_gap: null             # {sha, gap_table_ref}
full_ci_run: null               # {run_id, url, head_sha, conclusion} 终态均落盘，null=未有终态
bootstrap_handoff_consumed: false
bootstrap_state_path: null
phase_contract_path: null
```

提交且项目要求CI时的候选字段不变量：`candidate_review.sha == full_spec_gap.sha == full_ci_run.head_sha == candidate_sha`；且 `full_ci_run.conclusion` 终态均落盘，`PASS` 仅当 `conclusion==success && head_sha==candidate_sha`，`null` 表示未有终态；适用的必需项缺失或不一致即 `stale`，恢复/Closure 据此判定，不猜测。候选是否就绪只由上述源字段推导判定，不另存派生布尔。

未提交验证时 `candidate_sha` 为空：被验证版本由 `verification_evidence.result.bindings.implementation_digest` 绑定真实工作树内容（含相关 dirty／未跟踪输入），**不得用内容摘要冒充 `candidate_sha`**；有 dirty 时不能只绑定 HEAD。

**旧候选字段兼容**：旧状态缺 `candidate_review`／`full_spec_gap`／`full_ci_run`，或仍含旧候选字段、旧批准镜像时，原样保留并兼容读取为线索，不删除、不改写、不销毁唯一记录；缺失一律按"未验证"读取（不得当作已通过），不因缺新字段重启或回退已通过的 Gate。

`change_tier=small` 缺 `tier_rationale` 即 `BLOCKED`；原档位准入、风险升级和恢复规则继续由 [small-change-track.md](small-change-track.md) 拥有。候选审查保留既有约束：由review-gate按实际风险决定，普通任务low自检，命中风险升级standard/high；不因change_tier或文件数自动升级。

**旧批准记录兼容**：旧状态若含 `specification_approvals`（历史逐份批准镜像），兼容读取为批准证据线索并原样保留，不删除、不改写、不为去镜像而销毁唯一批准记录；当前批准依据以 [artifact-source-and-packet](../../dd-workflow-runtime/references/artifact-source-and-packet.md) 的 `approval` 记录与 Planning `source_manifest` 为准（属主唯一），恢复时引用既有批准属主，不反复手工同步。不新增 `mini_spec_path` 作为状态要求；从既有任务入口、规格路径与批准记录恢复，不因旧状态缺新字段重启。

### 2.1 in-progress 镜像

merge、push、cleanup 等不可瞬时动作使用运行时的 `in_progress: {operation, target, source, started_at}`（见 runtime-contract §4），不另设布尔兼容字段。merge/cleanup 两条恢复分支：

- `in_progress.operation=merge`：核对目标分支是否已含 `candidate_sha`；已含则清除 `in_progress` 并进入 Closure；未含则询问是否继续合并；
- `in_progress.operation=cleanup`：核对清理目标是否存在；存在则先完成剩余清理动作，再清除 `in_progress` 并写 Receipt。

## 3. legacy `current_step` mapping

`current_step`/`current_phase` 只作兼容 label，**不得用于排序或推进**；恢复顺序唯一读取 `current_stage` + Stage graph。冻结映射与新 Stage 顺序一致：

```text
0 → intake
1 → environment
2 → specification
3 → planning
4 / 4.x → implementation
5 / 5.x → documentation
6 / 6.x → final-candidate
7 → confirmation
8 → delivery
9 / 9.x → closure
```

现有 `current_step`/`current_phase` 作为兼容字段保留，但必须与 `current_stage` 一致。

## 4. 恢复（evidence-first）

跨 app/会话恢复时先读持久任务入口定位目标、边界、代码位置/worktree、关键决定、验证证据、下一步和授权（入口建立与路径规则见 [SKILL.md](../SKILL.md) 看板与接手入口节）：入口 + 仓库证据即可离线恢复，不依赖聊天记忆，也不要求必须联网。

状态字段与产物、分支或 CI 证据冲突时，按运行时恢复合同修正后继续。状态缺失时至少检查工作分支提交、规格/计划文件、Phase 证据、候选分支和 CI 结果；禁止默认回到 Intake。

恢复与继续前先判影响：与当前版本身份／范围／环境失配的证据失效并重做，未受影响且仍有效的结果直接复用，不无条件全量重跑；**仅 HEAD 相同但 dirty／未跟踪输入已变化时必须重验**，不能让 HEAD 相同掩盖 dirty 变化；远端 base 前进本身不使未受影响的本地验证失效，base 变化影响合并产物时重验合并结果。

恢复写入前必须核实当前代码、dirty diff、实际验证运行与批准范围：旧文档、旧测试报告与旧补丁仅为线索，**证据绑定输入/版本与当前状态不一致时，不得照旧补丁直接覆盖当前文件**，按 §4 证据修正后继续。

证据优先于状态字段：`current_stage` 与真实 diff／提交／CI 冲突时，以可复核证据为准，并把修正写入状态。

`change_tier` 缺失或为空时，按已产出产物推导档位并写回（见 [small-change-track.md](small-change-track.md) §8），不默认抬回完整流程重跑，也不回退已通过的 Gate。

Tracer 恢复三态判定见 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §8：`decision=required` 且 `result` 非 `passed` 时从 Phase 0（`current_stage=implementation`, `current_phase=0`）恢复，不得进 Phase 1；`skipped` 缺 `reason` 时 `BLOCKED`。tracer 落在 `4/4.x → implementation` 内，不新增 Stage，`current_step` 映射不变。

未提交验证与CI不适用路径按candidate.md处理：SHA字段不承载工作树指纹；使用现有implementation_digest绑定证据。项目不要求CI时full_ci_run=null加not-required依据合法，不能套用提交级CI不变量误判；项目必需CI的缺失仍不可放行。

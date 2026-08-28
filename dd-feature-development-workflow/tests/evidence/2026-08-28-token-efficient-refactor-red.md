# 红测证据：2026-08-28 dd-feature-development-workflow token-efficient refactor

> 本文件记录**实际运行**的红测输出。禁止预填或伪造；任何新增条目必须来自真实命令执行。

## 环境

- 日期：2026-08-28
- branch：`develop`
- HEAD：`bb2ba2619364efc478b4f3af8043a6d116d1a570`
- 工具：`python3` (`/opt/homebrew/bin/python3`)，`unittest` 标准库
- 注：`rg` 未安装，仓库内扫描以 `grep -R` 等价替代（语义一致）。

## 1. 确定性合同红测（Task 1 Step 4）

命令：

```bash
python3 -m unittest \
  dd-feature-development-workflow/tests/test_feature_workflow_contracts.py \
  dd-workflow-runtime/tests/test_ci_contracts.py -v
```

实际结果：`Ran 17 tests ... FAILED (failures=15)`

失败测试（逐一）：

| 测试 | 断言 | AC |
|---|---|---|
| test_stage_order_documentation_before_candidate | SKILL 中 documentation 未在 final-candidate 之前 | AC-07 |
| test_candidate_does_not_promote_target | 无 candidate_ready；candidate 仍 promote | AC-08 |
| test_delivery_promotes_exact_candidate_sha | delivery_authorization 未独立保留 | AC-09 |
| test_phase_reads_anchors_not_full_specs | 仍要求"完整读取该包引用的批准原始规格" | AC-05 |
| test_candidate_requires_frozen_standard_review_and_full_gap | 无 review_level / full_spec_gap | AC-08 |
| test_compact_verification_keeps_coverage_run_bindings_validity | artifact-contract 缺 compact coverage/runs/bindings/validity | AC-04 |
| test_main_skill_routes_every_reference_directly | SKILL 未直连 state-and-handoff 等新 reference | AC-01/02 |
| test_retired_references_have_no_active_links | SKILL 仍路由 specification-and-planning 等 | AC-13 |
| test_ci_md_no_legacy_steps | ci.md 含 1.2.5/4.5b/5.5/8.2.1 | AC-10 |
| test_test_location_md_no_legacy_steps | test-location.md 含 1.2.5 | AC-10 |
| test_ci_md_no_legacy_names | ci.md 含 Macim/macos-ci.yml | AC-10 |
| test_test_location_md_no_legacy_names | test-location.md 含 macos-xcuitest.yml | AC-10 |
| test_ci_md_external_git_requires_authorization | ci.md 无 delivery_authorization 绑定 | AC-10 |
| test_ci_xcode_exists_and_generic | ci-xcode.md 不存在 | AC-10 |
| test_refactor_skill_no_unconditional_push | refactor 仍"每个 Commit 后 push" | AC-10 |

部分已通过：`test_ci_md_evidence_binds_exact_sha`、`test_ci_md_local_diagnosis_cannot_close_remote_gate`（现有 ci.md 已含 SHA 绑定与本地诊断限制文本）。

结论：红测失败覆盖 AC-01/02/04/05/07/08/09/10/13，满足计划"失败至少覆盖 AC-03/04/05/07/08/09/10"。

## 2. 弱模型红测（Task 1 Step 5）

状态：`BLOCKED_EVAL_UNAVAILABLE`

原因：当前执行环境只暴露 `code-explorer` 子代理，无法取得全新的弱模型（`luna-worker`）实例对四个 scenario 逐字评测。按计划约束，不得编造模型输出或先改 Skill，故标记 `BLOCKED_EVAL_UNAVAILABLE`，不伪造红测输出。

四个 scenario 的预期正确行为已由下列文件冻结（作为行为合同的机械断言，供任务 7 绿测复用）：

- `tests/baseline-7-candidate-before-delivery.md`
- `tests/baseline-8-phase-anchor-loading.md`
- `tests/baseline-9-compact-verification.md`
- `tests/baseline-10-frozen-candidate-review.md`

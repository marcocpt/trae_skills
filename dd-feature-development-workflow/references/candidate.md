# Feature Final Candidate

只在 Final Candidate Stage 读取。候选冻结、独立 review/full gap、Full CI 与 invalidation。Candidate Gate 只产生可交付候选，不推进目标分支（AC-08）。

档位差异：`change_tier=small` 时审查等级与缺口检查按 §4 降级，SHA 绑定与完整 CI 不变；档位语义唯一属主是 [small-change-track.md](small-change-track.md)，本文件只引用。

## 1. 前置

所有 Phase Gate 通过，且 Documentation 已同步（候选冻结前完成，AC-07）。Tracer 决策已闭环（见 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §9）：`required` → `tracer.result=passed`；`skipped` → `reason` 存在；未闭环不得冻结候选。档位已判定：`change_tier` 存在，`small` 档需有 `tier_rationale` 且未命中升级触发器（见 [small-change-track.md](small-change-track.md) §3/§4）。

## 2. 冻结候选 SHA

1. 确认工作分支状态可解释且所有 Phase compact verification 完整、有效；
2. 确认 Commit／merge／push 的 Delivery 授权；缺失时保留已通过的 Workflow Gate 并停在该 Delivery 边界；
3. 获取最新 develop；
4. 基于最新 develop 创建 `ci/<F编号>-final-candidate`；
5. merge-only 合入 Feature 分支；
6. 记录冻结 `candidate_sha`；
7. push 候选分支（如授权）。

## 3. 冻结后确定性验证

对冻结 `candidate_sha` 先做确定性验证（lint/build/typecheck/全部测试/映射检查），并核对其 verification bindings 与 candidate SHA 一致（AC-04/AC-09）。

## 4. 独立 A/B/C 审查 + full-spec gap

### 4.1 `full` 档

以 `review_level=standard`、`review_execution=auto` 审查同一冻结 SHA（AC-08）。Reviewer 输入为 canonical spec、frozen diff、Phase verification refs；输出 A/B/C findings 和 full-spec gap table——必须覆盖所有适用的 normative stable IDs/anchors（含 FR/NFR/AC、Out of Scope、global/cross-cutting invariants、Constraints、failure/degradation paths、compatibility/migration、explicit negative requirements/Decision Freedom 禁止项），有 stable ID 时以 ID 标识、无则用稳定 section anchor，不复制正文；每项仍需记录 coverage/disposition 及对应 implementation/test/evidence ref。无安全独立路线且未获外部授权时 `BLOCKED`，不得 inline 降级为独立 PASS。

### 4.2 `small` 档

`change_tier=small` 且未命中 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 风险触发器时：

- `review_level=low`、`review_execution=auto`——由主 Agent 按 A/B/C 三方向自检并记录分方向结论，不派独立强审；A/B/C 语义与检查方向不因档位降级（属主 review-gate，本文件不重新定义）；
- `full_spec_gap` 缩为 **AC → 测试/证据逐项核对表**：逐项记录 AC、coverage、disposition 与对应 implementation/test/evidence ref，不要求覆盖全部 normative anchors 的 gap table；
- 命中任一风险触发器 → 按 review-gate 升级到 `standard` 或 `high`，并执行 §4.1 的完整 gap table；small 档不覆盖该升级；
- 冻结 `candidate_sha`、同 SHA 完整 CI 与 §6 invalidation 规则不变。

## 5. Full CI on exact SHA

对该 SHA 运行完整远程 CI。完整 CI 至少覆盖 lint、build、全部单元/集成测试、全部 UI 测试和项目要求的证据检查。

## 6. Invalidation

任何候选后内容变化（修复、文档同步新 commit 等）都会使 review、gap、CI 全部 stale，必须重新冻结并重做上述步骤（AC-08/AC-09）。不得把旧候选的 CI 结果复用于新 SHA。develop 在 CI 期间变化时废弃候选并重新生成、重新验证。

## 7. Gate 输出

```yaml
final_candidate_branch: ci/F0-final-candidate
candidate_sha: <sha>
candidate_review:
  level: standard            # change_tier=small 且未命中风险触发器时为 low
  execution: auto
  sha: <candidate_sha>
  review_ref: <review-ref>
full_spec_gap:
  sha: <candidate_sha>
  gap_table_ref: <gap-table-ref>   # small 档为 AC → 测试/证据逐项核对表
full_ci_run:
  run_id: <run-id>
  url: <run-url>
  head_sha: <candidate_sha>
  conclusion: success
current_stage: confirmation
```

`full_ci_run.head_sha` 必须等于 `candidate_sha` 且 `conclusion` 终态均落盘；`candidate_review.sha` 与 `full_spec_gap.sha` 也必须等于 `candidate_sha`；`PASS` 仅当 `conclusion==success && head_sha==candidate_sha`，`null` 表示未有终态，任一不等或结论非 success 即 `stale/BLOCKED`，不得推进。候选是否就绪只由上述字段推导判定，不输出派生布尔。

Candidate Gate 不更新 develop/main。Confirmation 只决定交付或回退；Delivery 只能推进同一 `candidate_sha`（AC-09）。

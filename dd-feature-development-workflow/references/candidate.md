# Feature Final Candidate

只在 Final Candidate Stage 读取。被验证版本绑定、对照验收条件的验证、按风险路由的审查、项目要求的 CI、失效与复用判定。Candidate Gate 只产生可交付候选，不推进目标分支（AC-08）。

档位差异：`change_tier` 只决定文档组织与缺口覆盖范围，**不再决定审查等级**——审查等级唯一由 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 风险触发器路由；档位语义唯一属主是 [small-change-track.md](small-change-track.md)，本文件只引用。

## 1. 前置

所有 Phase Gate 通过，且 Documentation 已同步（被验证版本绑定前完成，AC-07）。Tracer 决策已闭环（见 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §9）：`required` → `tracer.result=passed`；`skipped` → `reason` 存在；未闭环不得绑定被验证版本。档位已判定：`change_tier` 存在，`small` 档需有 `tier_rationale` 且未命中升级触发器（见 [small-change-track.md](small-change-track.md) §3/§4）。

## 2. 绑定被验证版本

1. 确认工作分支状态可解释，且所有 Phase compact verification 完整、有效；
2. **已提交且工作树干净** → 冻结 `candidate_sha`：它是后续验证、审查、缺口核对与 CI 的唯一版本身份；
3. **未提交，或存在相关 dirty／未跟踪输入** → **不为获得 SHA 强制提交**：用现有 [artifact-verification](../../dd-workflow-runtime/references/artifact-verification.md) 的 `verification_evidence.result.bindings.implementation_digest` 绑定真实工作树内容（必要时补充相关 dirty／未跟踪输入指纹）作为被验证版本；本次未提交验证的 `candidate_sha` 保持 `null`，旧提交身份仅作为历史线索原样保留；
   - **不得把内容摘要塞进 `candidate_sha` 冒充 Git 提交，也不新增平行 schema／账本**；
   - 有 dirty 时不能只绑定 HEAD。
4. **专用候选分支流水线不默认启用**：fetch 最新 develop → 建 `ci/<F编号>-final-candidate` → merge-only 合入 Feature 分支 → push 这条链路，只在项目规则或集成流程确需时、按已有动作级授权采用；未经授权停在动作边界，保留已通过的 Workflow Gate 与证据。
   **本地验证不以先获得 commit/push 授权为前提**；候选分支 push 只是授权动作之一，不是验证的前置条件。
5. Commit／merge／push 的 Delivery 授权缺失时，不因此判定验证无效：保留已通过的 Workflow Gate，停在该 Delivery 边界。

## 3. 对照验收条件完成验证

1. 对照已批准验收条件（与 `full_spec_gap` 同一来源）核对实现的**完整性、遗漏与越界**：每个 AC 追到 Task 与 Test/Evidence，越界改动单独列出；
2. 对被验证版本按项目规则与本次风险运行必要的确定性验证（如lint/build/typecheck、相关回归与映射检查；项目明确要求全量时执行全量），并核对其 verification bindings 与被验证版本一致（AC-04/AC-09）；
3. **仍有效的结果直接复用**：已执行且身份／范围／环境仍有效的测试与 CI 结果沿用，不重复运行；判定规则见 §6。

## 4. 审查与缺口核对（按 review-gate 风险路由）

A/B/C 审查语义唯一属主是 [review-gate](../../dd-workflow-runtime/references/review-gate.md)，本文件只规定何时升级与记录什么。

- **默认**：`review_level=low`、`review_execution=auto`，由主 Agent 按 A→B→C 三方向自检并分方向记录结论，不派独立强审。**不因 `change_tier=full` 或文件数量自动要求独立强审**，也不因这两者自动要求覆盖全部规范锚点的独立大表。
- **升级**：命中 review-gate 任一风险触发器 → 按该合同升级到 `standard`／`high` 并执行独立强审；高风险必须覆盖全局／跨层不变量、明确负向要求（Decision Freedom 禁止项、Out of Scope）与兼容性／迁移影响。
- **缺口核对（`full_spec_gap`）**：对照验收条件与被批准规格核对完整性、遗漏与越界，覆盖适用的 normative stable IDs/anchors（含 FR/NFR/AC、Out of Scope、global/cross-cutting invariants、Constraints、failure/degradation paths、compatibility/migration、explicit negative requirements/Decision Freedom 禁止项）；有 stable ID 时以 ID 标识，无则用稳定 section anchor，不复制正文；每项记录 coverage/disposition 及对应 implementation/test/evidence ref。
- **记录形式**：具体覆盖可紧凑记入既有验证证据或 AC → 测试/证据逐项核对表，不机械生成独立的覆盖大表；但每项覆盖事实必须可复核、可追到 ref。
- 无安全独立路线且未获外部授权时 `BLOCKED`，不得 inline 降级为独立 PASS。
- 提交路径：`candidate_review.sha` 与 `full_spec_gap.sha` 绑定真实 `candidate_sha`。未提交路径：本次SHA字段保持空（历史记录保留并标清适用范围），审查与缺口结论通过既有验证证据绑定同一 `implementation_digest`；不得把内容摘要写入任何SHA字段，也不能让几个空SHA相等冒充通过。

## 5. CI（是否必需、范围与执行位置由项目规则决定）

按 [test-location](../../dd-workflow-runtime/references/test-location.md) 与 [ci](../../dd-workflow-runtime/references/ci.md) 的项目规则判定，本文件不固定 CI 形式：

- **项目要求 CI**：严格绑定被交付版本；仍有效的同版本 CI 结果直接复用并记录 run ID／head_sha；未执行、未绑定或结论非 success 不得声称通过，也不得放行 merge。
- **项目要求但未经授权或无法执行**：记为明确缺口（`not-authorized`／`BLOCKED`）并保留证据，**不得**改成本地通过、不得自行豁免、不得留空冒充完成。
- **项目不要求 CI**：`full_ci_run` 保持 `null`，并在 Gate 结论记 `not-required` 与依据（如 `remote_ci_required=false` 或项目规则出处），不用本地结果冒充、不写占位结论。

## 6. 失效与复用（先判影响）

任意变更先判影响，再决定重做还是复用：

- 被验证版本身份、范围或环境失配 → 对应证据 `stale`，必须重做（AC-08/AC-09），不得把旧候选的 CI 结果复用于新版本；
- **仅 HEAD 相同但 dirty／未跟踪输入已变化** → 绑定失配，必须重验，不得继续复用旧证据；
- 未受影响且身份／范围／环境仍有效的结果 → 直接复用，不无条件全量重跑；
- 远端 base 前进本身不使未受影响的本地验证失效；**base 变化影响合并产物时重验合并结果**，develop 在 CI 期间变化且影响合并产物时重新生成并重新验证。

## 7. Gate 输出

以下示例仅适用于已有提交且项目要求CI的路径；未提交验证使用既有verification_evidence绑定，CI不要求时保留null并记录项目依据，不能套写success。

```yaml
final_candidate_branch: ci/F0-final-candidate   # 仅在按授权采用专用候选分支时非空，否则 null
candidate_sha: <sha>                            # 未提交验证时为空；此时被验证版本由 verification_evidence.result.bindings.implementation_digest 绑定
candidate_review:
  level: low                      # 默认 low；命中 review-gate 风险触发器时 standard|high
  execution: auto
  sha: <candidate_sha>
  review_ref: <review-ref>
full_spec_gap:
  sha: <candidate_sha>
  gap_table_ref: <gap-table-ref>  # 可紧凑记入验证证据或 AC → 测试/证据逐项核对表
full_ci_run:
  run_id: <run-id>
  url: <run-url>
  head_sha: <candidate_sha>
  conclusion: success             # 终态均落盘；null 表示未有终态；项目不要求 CI 时为 null 并记 not-required
current_stage: confirmation
```

验收先检查当前任务要求的全部验证与证据身份。提交路径的`candidate_review.sha`、`full_spec_gap.sha`绑定candidate_sha；仅当项目要求CI时，`full_ci_run.head_sha`也须绑定该真实SHA，`conclusion`终态均落盘，CI的`PASS`仅当`conclusion==success && head_sha==candidate_sha`。必需项缺失或失配不得放行。未提交路径用implementation_digest核对审查、测试与缺口证据，不要求制造提交或CI；不允许以空SHA相等代替核验。项目不要求CI时`full_ci_run=null`是合法未适用表示，附not-required及依据，不因此判stale/BLOCKED，也不写假success。候选是否就绪只由上述源字段推导判定，不输出派生布尔。

Candidate Gate 不更新 develop/main。Confirmation复用已有授权，仅处理仍未解决的动作决定；Delivery 只能推进同一被验证版本（AC-09）。

规格缺口检查覆盖全部当前有效约束，输入可以是已批准最小任务包与必要独立合同，不要求四件套。文档数量不决定是否允许进入 small；small 准入继续由 small-change-track 决定，审查强度由 review-gate 风险路由决定。

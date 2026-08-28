# 外部强审结果：2026-08-28 dd-feature-development-workflow token-efficient refactor

> 本文件记录**实际发起**的外部独立强审结果与后续本地核对/修复。禁止伪造；所有内容来自真实运行。

## 送审信息

- conversation_id：`chatgpt-review-skills-develop-0828-0920`
- 通道：已登录 ChatGPT 账号的 `codex exec --sandbox read-only`（read-only 强审后端）
- 审查范围：`bb2ba26..HEAD`（本重构全部改动，含 plan 输入与送审材料提交）
- 结果状态：`REQUEST_CHANGES`（14 findings：6 HIGH、7 MEDIUM、1 LOW）
- REVIEWED 文件覆盖：36（含 refactor/feature/runtime 三组）

## Findings（external，逐项）

| ID | Severity | 主题 | 分流 |
|---|---|---|---|
| F-001 | HIGH | state 字段 `final_candidate_sha/final_ci_run/final_ci_passed` 与 candidate 输出 `candidate_sha/full_ci_run` 不一致 | FINDING |
| F-002 | HIGH | delivery-and-closure.md 第 1 节重复 Documentation 正文（双重属主），Gate 误写 `current_stage=delivery` | FINDING |
| F-003 | HIGH | Closure 验证引用 `final_candidate_sha/final_ci_passed`，末端状态机断裂 | FINDING |
| F-004 | MEDIUM | ci.md 场景 2.4/3 "跳过继续"未限定必须有基线 CI 证据 | FINDING |
| F-005 | HIGH | implementation.md 未强制 Verification 未提交时记 not-required/not-authorized | FINDING |
| F-006 | MEDIUM | verification_evidence 用外部引用而非证据内容 | FINDING |
| F-007 | MEDIUM | TDD Red/Green 未绑定当前运行状态 | FINDING |
| F-008 | MEDIUM | SKILL Stage 图 `current_stage` 末端缺 delivery 语义 | FINDING |
| F-009 | MEDIUM | planning.md 复杂档 integration plan 与 `split_mode` 一致性不足 | FINDING |
| F-010 | MEDIUM | implementation.md 未声明单 Phase 多任务责任 | FINDING |
| F-011 | MEDIUM | state 恢复 evidence-first 缺 `merge_in_progress`/`cleanup_in_progress` | FINDING |
| F-012 | LOW | planning-stage 档位阈值 2/5/6 与基线 4 的「中等/复杂」措辞需对齐 | FINDING |
| F-013 | MEDIUM | ci.md `gh run list` 未列 workflow-name 的复用路径 | FINDING |
| F-014 | LOW | SKILL 红线未列「候选过期/内容变化仍推进」已覆盖（重复项） | FINDING |

## 本地核对结论

逐项对照相关文件后，全部 14 项引用属实（无 DISPUTED）。核心修复项：

1. **统一候选字段**：state 改用 `candidate_sha` + `full_ci_run`（对齐 candidate.md/delivery 的 exact-SHA 语义）——修 F-001/F-003/F-008/F-011；
2. **Documentation 单一属主**：delivery-and-closure.md 第 1 节删除正文，改为路由 `documentation.md`；Gate 改 `current_stage=final-candidate`——修 F-002；
3. **Verification Delivery 状态强制**：implementation.md 强制记录 verification 的 `not-required | not-authorized | pending`——修 F-005/F-006；
4. **TDD 运行绑定**：Red/Green 显式"当前代码失败/通过"——修 F-007；
5. **CI 跳过收敛**：场景 2.4/3 的跳过仅限有基线 CI 证据——修 F-004/F-013；
6. **planning 档位对齐**：阈值与基线 4 措辞统一、integration plan 与 split_mode 显式绑定——修 F-009/F-012；
7. **单 Phase 多任务**：implementation 声明责任——修 F-010；
8. **F-014**：SKILL 红线已覆盖，无需改动（标注已满足）。

## 处置与复查状态

- [x] 修复（含 F-001..F-013）
- [x] 第二轮送审（修复后）：返回 `REQUEST_CHANGES`（R-001..R-009：2 HIGH、7 MEDIUM）
- [x] R-001..R-009 本地核对：全部属实，已修复（commit `e57350f`）
- [x] 第三轮送审：通过 **chatgpt-review MCP 通道**（`chatgpt_send_file` 上传快照，conversation `chatgpt-review-skills-develop-0828-0920`）返回 **不 ACCEPTED**：R-001（state.md producer 仍写旧字段）、R-004（merge_in_progress 双重属主）、R-005（Integration Gate 引用未冻结 candidate_sha）、R-007（本地最终验证边界）+ 1 验证缺口
- [x] 第三轮 findings 本地核对：全部属实，已修复（见下）
- [x] 第四轮送审：MCP 通道返回 **不能 ACCEPTED**：R4-001（merge 后提前删 state）、R-007（CI trigger 降级矛盾）、R4-002（legacy mapping 顺序冲突）+ R-009（测试文件未入 bundle）。同时确认 R-001/R-002/R-003/R-004主体/R-005/R-008 已 CLOSED
- [x] 第四轮 findings 本地核对：全部属实，已修复（见下）
- [x] 第五轮送审：MCP 通道返回 **不能 ACCEPTED**：R5-001（场景 4 用户要求绕过）、R5-002（gh 不可用≠无远端 CI）、R-009（缺 4 项机械断言）。同时确认 R4-001/R4-002/R-007主体/R-009材料 已 CLOSED
- [x] 第五轮 findings 本地核对：全部属实，已修复（见下）
- [x] 第六轮送审：MCP 通道返回 **不能 ACCEPTED**：R5-002（ci.md 仍把 gh 不可用当 local-final 条件）、R-009（测试未跨文件断言 CI）。同时确认 R5-001、R4-001/002 已 CLOSED
- [x] 第六轮 findings 本地核对：全部属实，已修复（见下）
- [ ] 第七轮送审：修复后继续 MCP 送审，直到 ChatGPT 返回 `CLOSED`

## 第三轮 findings 与修复记录

| ID | Severity | 核对 | 修复 |
|---|---|---|---|
| R-001 | HIGH | 属实：state.md:149 仍写 `final_ci_passed` | 改为写 `full_ci_run={...}` + `full_ci_passed=true`，要求 `head_sha==candidate_sha` 才置 true |
| R-004 | MEDIUM | 属实：state.md:150/204 仍用 `merge_in_progress` 布尔+模板代码 | 统一 `in_progress: {operation,target,source,started_at}`；模板代码同步 |
| R-005 | HIGH | 属实：implementation §3.1 绑定 `integration_ci_run.head_sha == candidate_sha`（循环依赖） | 改为绑定 `integration_verification.bindings.implementation_digest`；candidate_sha 留 Final Candidate |
| R-007 | MEDIUM | 属实：test-location 封闭列表与 ci.md 风险豁免叠加 | test-location 增加"有必需远端 CI Gate 时本地最多 CONDITIONAL/BLOCKED，不得 PASS"边界 |
| 验证缺口 | VERIFY | 属实：无 state.md producer 断言 | 新增 TestStateProducerConsumerConsistent（3 个断言） |

## 第四轮 findings 与修复记录

| ID | Severity | 核对 | 修复 |
|---|---|---|---|
| R4-001 | HIGH | 属实：state.md 规定 merge 成功后即删 state，Feature Closure 失去事实源 | state.md 按 WORKFLOW_TYPE 分支：feature-development 保留 state 直到 Closure 完成（Receipt + cleanup 验证后）才删除 |
| R-007 | MEDIUM | 属实：ci.md/test-location 封闭列表允许"CI 触发失败+用户选本地→本地最终验证"，与红线矛盾 | CI 触发失败不进入 local-final-verification 封闭列表，一律 ASK 修复/重试/终止 |
| R4-002 | MEDIUM | 属实：legacy current_step 映射顺序与新 Stage 顺序冲突 | 冻结映射为新顺序（4=impl,5=doc,6=final-candidate,7=confirmation,8=delivery,9=closure），current_step 仅作 label 不用于排序 |
| R-009 | VERIFY | 属实：测试文件未入 bundle | 下一轮 bundle 含测试快照；新增 R4-001 回归断言 |

## 第五轮 findings 与修复记录

| ID | Severity | 核对 | 修复 |
|---|---|---|---|
| R5-001 | MEDIUM | 属实：ci.md 场景 4 仍允许"用户明确要求"绕过 CI 优先 | 场景 4 本地全量测试仅作补充诊断；有必需远端 CI Gate 时不得仅因用户要求降级 |
| R5-002 | MEDIUM | 属实：gh 不可用被等同于"无远端 CI 能力" | 拆为 remote_ci_required / ci_control_available 两概念；gh 不可用→BLOCKED/ASK，不归入无远端 CI |
| R-009 | MEDIUM | 属实：缺 4 项机械断言 | 新增 test_ci_trigger_failure_cannot_fall_back_to_local_final、test_user_request_cannot_bypass_required_remote_ci、test_workflow_selector_is_shared_by_all_scenarios、test_gh_unavailable_not_equal_remote_ci_absent、test_legacy_stage_mapping_matches_stage_graph |

## 第六轮 findings 与修复记录

| ID | Severity | 核对 | 修复 |
|---|---|---|---|
| R5-002 | MEDIUM | 属实：ci.md 本地诊断封闭列表仍含"gh 不可用且用户选择不修复"，与 test-location 的 remote_ci_required 模型冲突 | ci.md 改为仅 `remote_ci_required=false` 才 local-final；gh 不可用→BLOCKED/ASK；红线"CI 不可用"定义同步；test-location 删"两种情形"旧措辞 |
| R-009 | MEDIUM | 属实：test_gh_unavailable 只查 TEST_LOCATION 不查 CI | 扩为跨文件断言（CI+TEST_LOCATION），加"两种情形"负向断言 |

## 第二轮 findings 与修复记录

| ID | Severity | 核对 | 修复 |
|---|---|---|---|
| R-001 | HIGH | 属实：state.md 仍留 `final_ci_passed`；candidate 输出未结构化 | candidate.md/state.md/state-and-handoff 统一为 `{run_id,url,head_sha,conclusion}` + review/gap SHA binding |
| R-002 | HIGH | 属实：`verification.delivery` 违反 plan+result 唯一 schema | 改为 `phase_delivery`，authorization/execution 分离；Red/Green run 各自带 digest |
| R-003 | MEDIUM | 属实：final-candidate Gate 写在 delivery-and-closure | 移到 documentation.md；delivery-and-closure 删除 Documentation 节 |
| R-004 | MEDIUM | 属实：布尔 merge/cleanup 与 `in_progress` 双重属主 | 移除布尔字段，镜像 `in_progress: {operation,...}`，定义 merge/cleanup 恢复分支 |
| R-005 | MEDIUM | 属实：integration plan 无执行属主 | implementation 增加 §3.1 Post-Phase Integration Gate |
| R-006 | MEDIUM | 属实：baseline-4 自称"同一子系统不同层"又判跨子系统 | 冻结为"数据/服务/UI 三子系统"，5 文件验收成立 |
| R-007 | MEDIUM | 属实：ci.md 跳过与 test-location"不跳过失败验证"冲突 | 跳过=风险豁免，Gate 保持 `CONDITIONAL` 禁止据此声明 PASS |
| R-008 | MEDIUM | 属实：workflow-name 解析只在场景 1 | 提升为所有场景共同前置"工作流选择器"，单一属主 |
| R-009 | MEDIUM | 属实：测试断言偏弱/no-op | 强化 exact-SHA 结构化断言、cross-file producer/consumer、documentation Gate 属主断言、修复 no-op replace |

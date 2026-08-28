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
- [ ] 针对性复查：修复后再次送审，直到 ChatGPT 返回 `CLOSED`

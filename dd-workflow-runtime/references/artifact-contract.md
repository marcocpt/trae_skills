> 唯一属主：规范事实、派生视图、执行包和验证证据的通用语义只在本文件维护；调用方只补领域检查。

# Artifact Contract

仅在创建或消费这些产物时读取。

## 1. 事实与视图

- Requirements、Architecture／Design、测试策略各有唯一属主；事实用稳定 ID，其他产物只引用。
- 规范有效需同时可核对版本、实际内容指纹和 `approval`；文件存在不等于批准。指纹用 Git blob ID 或文件 SHA-256，分支、路径、日期、仓库 HEAD 均不能替代。
- 人审视图只含改什么、为什么、不改什么、主要风险、待裁决项和依据，不增加规范事实。
- 派生视图不得独立维护；来源变化后失效并重新派生，规范修改必须回到属主。

## 2. 弱模型执行包

每个任务单独派生：

| 字段 | 必需内容 |
|---|---|
| `task_id` | 稳定 ID、目标、依赖 |
| `sources` | 逐项路径、稳定 ID、版本、内容指纹、`approval` |
| `constraints` | 相关约束、失败路径、跨功能约束、授权边界 |
| `consumes` / `produces` | 精确输入、输出、下游接口 |
| `write_scope` | 可创建／修改／删除的文件；未列路径禁止写 |
| `steps` | 按依赖排序的可执行步骤，无 TODO／“类似任务” |
| `verification` | 精确命令／人工步骤、预期、通过条件、证据位置 |
| `stop_conditions` | `BLOCKED`／`STOP` 条件和下一安全动作 |
| `delivery_authorization` | Git／外部动作状态、范围和证据 |

- `approval={status, authority, decided_at, evidence_ref}`，只有与当前指纹绑定的 `approved` 有效。
- `delivery_authorization={status, actions, scope, authority, decided_at, evidence_ref}`；`status` 只取 `authorized | not-required | not-authorized | pending`。仅可执行 `authorized` 中明确列出的动作和范围；`pending`／缺字段在动作边界 `BLOCKED`。内容批准不授权动作。
- 组包方重读已批准原文；摘要只定位来源。只展开本任务所需冻结事实一次，使执行方无需拼接关键事实；禁止自行补齐缺失来源、权限、接口或通过条件。
- 执行前核对每个来源可定位、指纹与批准有效、依赖包与当前 worktree 一致。缺字段或不一致即 `stale`／`BLOCKED`：停止、回上游重读并重新派生，禁止手改旧包继续。

## 3. 生命周期与保留

### 3.1 七类生命周期（唯一定义）

| 类型 | 唯一职责 | 是否持续同步 | 关闭后处理 |
|---|---|---|---|
| `canonical` | 当前 Requirements、Design、Test Policy、Architecture | 是，仅按影响更新 | 保留并持续维护 |
| `active-change` | 当前 Phase 的增量范围、设计、验证与执行包 | 仅活动期间 | 提升长期事实后关闭 |
| `derived` | trace map、人审摘要、弱模型执行包 | 不独立维护 | 来源变化即 stale，重新派生 |
| `evidence` | 与来源、实现、环境绑定的运行结果 | 不回填合同 | 当前 Gate 仍依赖则保留；过期后可删 |
| `decision` | ADR 与不可从最终规则推导的裁决理由 | 不覆写历史 | 永久保留，使用 superseded |
| `working` | 临时摘要、审查过程、迁移清单 | 否 | 事实吸收后删除 |
| `closed-change` | 已完成且不再继续同步的 change package | 否，保持冻结 | 保留 closure README 和必要证据 |

- `canonical` 只维护当前事实；`active-change` 关闭后把长期事实合并到 `canonical`；`closed-change` 不再同步；子 change 的 `review` 状态不能自动重开或关闭 Phase。
- 详细版本叙事、临时摘要、复审过程和已失效执行包属于 `working`；Git 已追溯且事实已吸收时可删除。
- `derived` 失效即 `stale`，必须重新派生，规范修改必须回到属主。

### 3.2 Phase / Package / Gate 状态字段（唯一定义，下游不得重定义）

```yaml
phase_activity: not-started | active | complete
package_lifecycle: active-change | closure-pending | closed-change | retired
package_review: draft | proposed | approved | review-blocked
gates:
  - gate_id: stable gate identifier
    scope: phase or change package name
    result: OPEN | BLOCKED | CONDITIONAL_PASS | PASS | CLOSED
    as_of: YYYY-MM-DD
    evidence_ref: repository-relative path or commit
    decision_ref: decision ID or none
```

- `closed-change` 不是 Gate 结果，也不能由子计划状态反向覆盖 Phase；`phase_activity`、`package_lifecycle`、`package_review` 与 `gates[].result` 互相独立。
- 示例：P0 可为 `phase_activity=complete`、Gate `CONDITIONAL_PASS`、`P0_R1.package_lifecycle=active-change`；P3 可同时拥有 Implementation Gate `PASS`、Formal Exit Gate `CLOSED`，而旧 P3_04 仍为 `package_review=review-blocked`。只有对应 Gate 和 package 都满足关闭条件时，才可标记 `closed-change` 或 `retired`。
- 若 change 修改稳定 ID、AC 或其他 canonical 事实，必须新建或重审 Gate，不能只沿用旧状态。

### 3.3 同步影响矩阵

同步输出固定为 `updated | no-update | stale | not-applicable | retired`。变更只更新事实属主和真实受影响下游：

- 修复实现偏差且合同未变：Requirements / Design = `no-update`，回归测试和新证据 = `updated`；
- 修复暴露合同歧义或行为变化：先更新 Requirements，再重审 Design / Test Policy；
- 纯重构：Requirements = `no-update`；职责、依赖或数据流改变时 Design = `updated`；
- 增加等价测试样本：Test Policy / Verification Population = `updated`，Requirements = `no-update`；
- Acceptance Contract 改变：Requirements = `updated`，旧证据 = `stale`。

证据保留不能只按文件名判断。`retention` 记录（见 3.5）与 `ledger` 共同决定去留。

### 3.4 迁移台账（ledger）最小字段

`ledger.md` 每行对应一个稳定 ID 或外部引用，至少包含：

`source`、`target`、`E/M/G/C`、`disposition`、`verification_ref`、`approval`

- `E/M/G/C`：E 表达和结构变化；M 已有批准来源明确蕴含的等价迁移；G Design/代码/测试有规则但批准 Requirements/ADR 没有；C 批准来源互相冲突。
- 引用 disposition 明确为 `current | historical | retired`。
- 不写成长篇叙事；规范化映射保留原文状态字符串（如 `PROPOSED_FOR_HOST_APPROVAL` → `package_review=proposed`，`REVIEW-BLOCKED` → `review-blocked`），不得覆盖原始证据或据此自动批准。

### 3.5 保留清单（retention）最小字段

`retention.yaml` 中每项至少记录：

```yaml
role: reproducibility | closure | decision-support | diagnostic
retention: permanent | while-referenced | until-superseded | ephemeral
unique_evidence: true | false
replacement: repository-relative path or none
reason: one-line retention reason
source_version: commit or document version
content_hash: SHA-256
owner: role or person
deletion_authorization: evidence reference or none
```

- `unique_evidence=true` 禁止自动删除；人工删除仍需明确授权并留下记录。
- 任何删除都必须有替代物核验和明确授权；缺少 `replacement` 核验或 `deletion_authorization` 的 `unique_evidence` 不得进入删除清单。

## 4. 验证证据（与来源/实现/环境绑定，不回填合同）

| 字段 | 记录 | 不能推出 |
|---|---|---|
| `verification_plan` | 计划检查、oracle、预期 | 已覆盖或已通过 |
| `existing_coverage` | 指定来源版本的 AC／路径覆盖 | 本次运行通过 |
| `run_result` | 本次命令／步骤、环境、实现／构建指纹、时间、`PASS | FAIL | NOT_RUN` | 后续版本仍有效 |
| `evidence_validity` | 与当前来源、实现／构建、环境、AC 的匹配：`valid | stale | unreadable | unverified` | 未运行也可 PASS |

`existing_coverage` 只取 `COVERED`（完整）、`PARTIAL`（部分）、`MISSING`（缺失）、`DEFERRED`（已批准延后，含负责人／触发条件）、`UNVERIFIED`（无法核对，设 blocker）。测试存在或 `COVERED` 都不等于运行通过。只有必需 `run_result=PASS`、`evidence_validity=valid`、AC／失败路径无缺口且 blocker 为零，Gate 才能 `PASS`。

计划写规范；覆盖快照、运行结果、审查发现和进度写既有状态／证据记录，不回填冻结合同。

## 5. 最小化

- 按耦合和可独立验证性拆任务；不用固定字数、token 或分钟阈值裁内容。
- 删除重复背景和解释，不删除 AC、失败／回滚路径、通过条件、来源指纹或授权边界。
- 不要求新顶层 Skill、状态系统或生成器；复用现有计划、状态和证据产物。

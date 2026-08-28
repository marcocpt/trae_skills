> 拆分来源：`artifact-contract.md` §3。唯一属主：生命周期、同步影响、ledger 与 retention 只在此维护。

# Artifact Lifecycle

仅在判定文档同步、生命周期或保留时读取。来源/执行包与验证证据见对应分文件。

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
> 拆分来源：`artifact-contract.md` §3。唯一属主：生命周期、同步影响、ledger 与 retention 只在此维护。

# Artifact Lifecycle

仅在判定文档同步、生命周期、保留、任务结案或检索项目历史时读取。来源/执行包与验证证据见对应分文件。

## 3. 生命周期与保留

### 3.1 七类生命周期（唯一定义）

| 类型 | 唯一职责 | 是否持续同步 | 关闭后处理 |
|---|---|---|---|
| `canonical` | 当前长期合同：Requirements、Design、Test Policy、Architecture 或合并的最小长期合同 | 是，仅按影响更新 | 保留并持续维护 |
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
- 增加等价测试样本：样本登记或可执行测试证据 = `updated`；仅当策略或Population约定实际变化才更新对应属主，不强制双写；Requirements = `no-update`；
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

### 3.6 任务结案与项目记忆

项目记忆复用当前合同、代码与测试、持久任务入口和重要决策；不引入新的生命周期或状态 schema。当前合同维护仍有效的目标、约束和行为约定，代码与测试已充分表达的实现细节用引用，不逐次复制修改过程；已有合同与稳定 ID 继续有效，不能因采用最小任务包而丢弃批准语义。最小长期合同与分篇合同适用同一 [来源与批准合同](artifact-source-and-packet.md)；合并文件不改变规范有效性或既有批准边界，文件名和位置由项目约定。

完成本任务要求的 Gate 后，在既有持久任务入口内写结案记录；不另建历史总结、CHANGELOG、记忆数据库或第二套状态账本。入口选择仍由 [state.md](state.md#持久任务入口) 拥有。结案记录通常用数段或一张小表，保留：

- 任务标识、日期、症状或目标，以及本次实际完成的范围；
- 根因或关键决定及理由；被否决方案仅在影响未来判断时记录，没有发生或没有证据的内容明确记为未执行或未知；
- 受影响能力、代码与测试位置，以及实际验证结论与证据引用；
- 被验证版本：复用 [artifact-verification](artifact-verification.md) 的绑定；未提交时保留可持久定位的差异或快照，不得只写 HEAD 或只留下摘要指纹；不为历史追溯强制 commit；
- 剩余限制、未完成项的既有入口，以及授权与交付状态，区分代码完成、验证通过和已合并；
- 重要批准或不可从最终代码推导的长期取舍，引用原批准依据或既有 ADR；仅确有独立长期用途时新建决策记录。

已有 Completion Receipt 或项目闭合 README 可以直接承载上述内容；持久入口与 Receipt 分处两地时引用既有记录，不再次维护一份叙事。`child/helper` 只返回事实，由父工作流更新同一入口；只交还规格、暂停或仍有 blocker 时保持真实接手状态，不把阶段完成写成整个任务完成。

结案记录完成后冻结，不随未来代码追更；后续更正以有来源的更正记录或新任务指向原记录。压缩工作笔记前，核对唯一验证证据、批准依据和仍有效约束不得因压缩丢失；长期约定归现有属主，旧入口只留引用。删除仍按 §3.5，不因“仅供 AI 阅读”而自动清理旧文件、活动状态或唯一证据；仅存在工作树内的记录在环境清理前必须保全到项目内持久位置。差异或快照须覆盖相关未跟踪输入，优先复用已存在的可重建来源，不强制统一快照格式或新增账本；无法在已授权位置保全时停止清理，记录 blocker 与下一安全动作，不宣称清理完成。

### 3.7 按问题检索

纯查询不建立任务包或新状态。先用任务标识、能力名、代码符号或症状检索，再读取命中的相关段落；优先 `rg` 定位，必要时用 `git log -S` / `git log -G` 与 `git show` 回溯具体文件。不默认全文加载历史目录，也不把整份记忆文件加入每次上下文。

| 问题 | 优先来源与核对方式 |
|---|---|
| 当前怎样工作 | 当前已批准合同与适用活动增量，再核对当前代码、dirty 差异和相关测试；代码说明实现事实，不自动改写目标或批准约束 |
| 为什么这样改 | 相关任务结案记录与重要决策，再沿引用查看原始差异、批准与当时证据；不能从最终代码反推未记录的动机 |
| 做到哪里 | 既有任务入口和运行时状态，再核对实际差异与有效验证，按恢复合同修正过期状态 |
| 验证过什么 | 记录指向的原始运行结果及版本、环境绑定；区分记录中的历史结论与本次实际验证 |

结案记录只说明当时的状态，不能覆盖当前合同或证明当前版本通过。旧草案、历史计划和搜索摘要只作线索；来源冲突时保留目标与实现的区别并报告冲突，不静默挑选新语义。证据缺失、过期或版本不符时明确说明，不能补造历史验证或断言当时未记载的理由。回答附可定位的来源，对未实测内容说明依据。

确有检索需求时可生成任务或能力索引；索引属于 `derived`，必须引用原记录，来源变化后重建，不作为唯一事实来源。不要求先建立向量数据库、集中记忆文件或额外服务；历史存量只按本次问题定向检索，清理另按保留规则处理。

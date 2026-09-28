# Feature 小型改动快速通道（`change_tier`）

只在 Intake 档位判定、Specification、Planning 和 Final Candidate Stage 读取；Implementation、Documentation 只在需要确认本档差异时读取。

## 1. 定位

本文件唯一拥有 `change_tier` 语义：档位判定、可省项、不可省项、升级与恢复。

- **不新增 Stage、不改 Stage 顺序、不改 `required_exit_stages`**——small 档只压缩 Stage 内部产物，不改变工作流骨架；
- 审查等级语义唯一属主是 [review-gate](../../dd-workflow-runtime/references/review-gate.md)，风险分类词表唯一属主是 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §3，文档生命周期唯一属主是 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3.3，执行包来源字段唯一属主是 [artifact-source-and-packet](../../dd-workflow-runtime/references/artifact-source-and-packet.md)。本文件只引用，不复制其清单或 schema。

## 2. 档位

```yaml
change_tier: small | full
```

- `full`：现行完整流程（规格套件、Phase 拆分、独立强审、full-spec gap）；
- `small`：本文件定义的快速通道。

**默认 `full`。** 只有 §3 全部准入条件都能逐条证成时才可判 `small`；不能证成即 `full`。不得先按 `small` 开工、遇事再补材料。

## 3. small 准入（全部满足才可判定）

1. 单 Phase，且 Phase 目标能用一段话说清；
2. 改动落在既有模块内，不新增架构边界；
3. 不新增、不修改公共 API 签名；
4. 不改持久化格式，不改并发模型；
5. 无兼容性、迁移、安全或权限影响；
6. 不存在未验证的高风险架构假设——判定与 `tracer.decision=skipped` 同源（见 tracer-contract §3，本文件不重写其清单）；
7. 用户可见 UI 变化可用真实路径验证；无 UI 变化时本条不适用。

规模参考（仅作复核提示，不单独构成准入）：改动文件 ≤ 5 且有效 diff ≤ 200 行。超出时必须重新核对第 1～7 条是否真的成立，而不是直接判 `full` 或放行。

## 4. 升级触发器（命中任一立即转 `full`）

- 新增或更改公共 API 签名；
- 新增架构边界或跨模块依赖；
- 持久化格式或并发模型变化；
- 兼容性、迁移、安全或权限影响；
- 需要 ≥ 2 个 Phase，或实现中发现接口／架构／规格假设失效（合同漂移）；
- 关键用户路径 UI 变更无法用真实路径验证；
- 命中 review-gate 风险触发器（此时审查等级按 review-gate 升级，不受 small 档降级约束）。

升级处理：把 `change_tier` 改为 `full`，已产出材料按 `full` 补齐——mini-spec 升级为规格套件需重新走批准；**禁止"边走边升"**，即不允许继续按 small 收尾、事后再补材料。

## 5. small 档各 Stage 做什么

| Stage | small 档做法 | 与 `full` 的差异 |
|---|---|---|
| Intake | 复述确认（保留），同时判定档位并写 `tier_rationale` | 仅多一步档位判定 |
| Environment | 不变 | — |
| Specification | 只产出 **1 份 mini-spec**：可验证 AC 清单、IN／OUT、验证命令与预期、影响面（调用方、文档、测试）。记录路径与内容指纹，批准依据按 artifact-source-and-packet 的最小要求 | 不生成 Requirements／Design／Visual／Test Matrix 四件套 |
| Planning | 不做拆分档位判定与独立执行包派生；产出单 Phase 执行清单（Goal、改动文件、验证命令与预期、回滚点、AC → 测试映射）；`tracer.decision=skipped` + `reason` | 不产出 Phase 子计划文件与 `phase_plan_paths` |
| Implementation | 单 Phase，TDD 红绿必须实际运行并绑定 digest，Local Gate 全项不减 | 只少 Phase 循环 |
| Documentation | 不变，按影响判定 lifecycle 结论 | — |
| Final Candidate | **仍冻结 `candidate_sha` 并跑同 SHA 完整 CI**；`candidate_review.level=low`（review-gate 默认档，主 Agent A／B／C 自检，零独立强审）；`full_spec_gap` 缩为 **AC → 测试／证据逐项核对表**（逐项记 coverage、disposition 与 ref） | 不派独立强审，不做覆盖全部 normative anchors 的 gap table；SHA 绑定与完整 CI 不变 |
| Confirmation／Delivery／Closure | 不变 | — |

命中 review-gate 风险触发器时，`candidate_review.level` 按其规则升级到 `standard` 或 `high`，small 档不覆盖该升级。

## 6. small 档不可省清单（写死）

1. Intake 需求复述确认（防跑偏闸口）；
2. mini-spec 的用户确认——mini-spec 就是本档的"已批准规格"，没有它同样不得修改生产代码；
3. TDD 红绿**实际运行**并绑定 `implementation_digest`；
4. Local Gate 全项；
5. 用户可见 UI 的真实路径证据；
6. 冻结 `candidate_sha` 与同 SHA 完整 CI；
7. Documentation 按需同步与 lifecycle 结论；
8. 动作授权边界（内容批准不等于 Git 授权）；
9. Host Close。

## 7. 状态字段

```yaml
change_tier: small | full
tier_rationale: <small 时必填，逐条对应 §3 准入条件>
```

写入 Feature state（见 [state-and-handoff.md](state-and-handoff.md) §2）。判 `small` 却缺 `tier_rationale` → `BLOCKED`，补判定后才可推进；这条约束与 tracer `skipped` 必带 `reason` 同构。

## 8. 恢复

- `change_tier` 存在 → 直接沿用，不重新判定；
- 缺失或为空 → 按已产出产物推导：存在 mini-spec 且单 Phase → `small`；存在规格套件或 Phase 子计划 → `full`；写回状态并补 `tier_rationale`；
- 仍无法判断 → 按 `full` 补齐，**不回退已通过的 Gate，不默认从 Intake 重启**；
- 恢复后实际 diff 命中 §4 任一触发器 → 转 `full` 并按 §4 补齐。

## 9. 红线

- 把 small 当免检通道，省掉 §6 任一硬 Gate；
- 命中升级触发器仍按 small 收尾，或"边走边升"；
- 未写 `tier_rationale` 就判 `small`；
- 以"改动很小"为由跳过规格批准或用户确认；
- 在本文件复制 review-gate 的等级语义、tracer-contract 的风险清单或 runtime 的状态字段定义。

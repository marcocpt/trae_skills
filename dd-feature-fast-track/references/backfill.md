# 新特性补齐阶段（Backfill / Closure）

补齐顺序、基准与关闭规则见 [fast-track-contract](../../dd-workflow-runtime/references/fast-track-contract.md) §5；本文件只写新特性领域补什么、怎么补、什么时候交接。

## 1. 补测试与确定性验证（第一步，不可跳过）

1. 把复述确认的验收口径拆成可验证 AC 清单；AC 来源是**已确认需求**，逐条对照速通实现，不允许照抄实现现状；
2. 建立 AC → 测试/证据映射：已有测试直接复用，缺的补写；测试位置遵循 [test-location](../../dd-workflow-runtime/references/test-location.md)；
3. 红绿必须实际运行：新增测试先在回退实现上验证失败、在最终实现上验证通过；不能构造回退的，用已复现的最小对照实验代替并写明；
4. 确定性验证：同一份实现重复执行结论一致，把运行记录绑到当前实现指纹。

关闭欠账 `test` 与 `determinism`，`evidence` 填实际运行记录与指纹。

## 2. 补规格（第二步）

1. **规模判定**：对照 [small-change-track](../dd-feature-development-workflow/references/small-change-track.md) §3 的准入条件判断——满足则补 1 份 mini-spec（AC 清单、IN／OUT、验证命令与预期、影响面），不满足则补完整规格套件（Requirements、Design、Test Matrix，UI 功能含 Visual），走 `dd-writing-specs` 的写法；
2. **反向规格纪律**：规格描述"应该是什么"，不是"现在是什么"。实现与已确认需求冲突时改实现，并把冲突与处置记入 `decisions`；不得为了让规格和实现一致而改写已确认需求；
3. 记录规格路径与内容指纹，作为后续缺口检查的基准。

关闭欠账 `spec` 与 `plan`（`plan` 的 closing 证据是 AC → Task → 测试/证据映射）。

## 3. 补 CI 与审查（第三步）

1. 冻结最终候选 SHA——补齐完成后锁定，后续验证与交付都绑定这一个 SHA；
2. 在该 SHA 上跑完整 CI，遵循 [ci](../../dd-workflow-runtime/references/ci.md)；关闭欠账 `ci`，`evidence` 填运行记录与 `head_sha`；
3. 审查按 [review-gate](../../dd-workflow-runtime/references/review-gate.md)：默认主 Agent A／B／C 自检；命中风险触发器时升级独立强审，等级由 review-gate 决定，速通模式不覆盖该升级；
4. 缺口检查：从已补齐的规格反查遗漏、越界与未验证项。照抄实现的规格无法暴露缺口，发现这种规格先回 §2 重做；
5. 有 UI 变化时按 [ui-evidence](../../dd-workflow-runtime/references/ui-evidence.md) 复核证据新鲜度，关闭欠账 `ui-evidence`。

同一 SHA 是硬约束：`candidate_sha` 与 CI、审查、缺口检查绑定同一个值。

## 4. 补文档（第四步）

按调用关系、数据流、共享模型和用户流程检查需要同步的长期文档，遵循 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) 的生命周期结论；无需更新的要有明确结论，不是"忘了"。关闭欠账 `docs`。

## 5. 逐条关闭与豁免

- 每条欠账关闭时必须写 `evidence`，没有证据的关闭无效；
- 用户要求某条不补时，改为 `waived` 并写 `waive_reason`，**逐条确认**，不接受"都别补了"的一次性豁免；
- 台账全清后，把最终 `debts` 与状态一起持久化。

## 6. Closure 与交接

**直接收尾**：全部欠账 `closed` 或经确认 `waived`、CI 与审查绑定同一 SHA 且通过 → 写 Completion Receipt，按 `dd-workflow-runtime` 的宿主结束合同收尾（Trae 用结构化 ASK，不得直接结束会话）。

**交接正式流程**：补齐阶段发现命中下列任一升级触发器 → 不在速通内降级，交接 `dd-feature-development-workflow`：

- 需要新增或更改公共 API 签名；
- 新增架构边界或跨模块依赖；
- 持久化格式或并发模型变化；
- 兼容性、迁移、安全或权限影响；
- 需要 ≥ 2 个 Phase 才能验证。

交接内容：已确认需求、最终实现与 SHA、补齐产出（规格、映射、CI 记录、审查结论）、`decisions`、剩余 `open` 欠账。按 [state-and-handoff](../dd-feature-development-workflow/references/state-and-handoff.md) 的 Handoff 字段写入，交接后本 Skill 不再拥有会话。

## 7. 红线

- 先跑 CI 再补测试（顺序倒置会让 CI 失败无法定位）；
- 照抄实现现状写规格；
- 无 `evidence` 关闭欠账；
- 一次性豁免全部欠账而非逐条确认；
- 命中升级触发器仍在速通内收尾；
- 把补齐完成解释为 push／merge／发布授权。

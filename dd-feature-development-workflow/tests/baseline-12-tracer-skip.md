# 基线测试 12：低风险增量改动被误判需要 Tracer（过度触发）

## 场景

Feature F5.6「工具栏按钮文案与图标微调」。Requirements/Design 已批准，1 个 Phase，改动限于既有 Toolbar 组件内的文案、图标资源和一处样式常量——**不新增架构边界、不新增公共 API、不改持久化/并发模型**。`host=trae`，进入 Planning。

状态文件关键字段：
```json
{
  "workflow_type": "feature-development",
  "host": "trae",
  "current_stage": "planning",
  "feature_number": "F5.6",
  "total_phases": 1,
  "completed_phases": []
}
```

## 预期行为（修改后技能）

1. Planning 判定：未命中 review-gate 风险分类，也不存在未验证高风险架构假设 → `tracer.decision=skipped`，`reason="低风险增量改动，无新架构边界"`；
2. 状态写入 `tracer: {decision: skipped, reason: "..."}`，`current_stage=implementation`；
3. Implementation §0：读到 `decision=skipped` 且有 `reason` → **跳过 Phase 0**，直接进 Phase 1；
4. Candidate 前置：`skipped` 且 `reason` 存在 → 决策闭环，可冻结候选。

## 当前基线行为（修改前预期失败 / 或过度触发失败）

- ❌ 若把 tracer 设成固定必经 Stage，则改文案也要先打 Phase 0，制造无意义闭环与额外轮次；
- ❌ 弱模型为"保险"对低风险改动也标 `required`，白白多跑一条链路；
- ❌ 或标 `skipped` 但不写 `reason`，导致决策无法解释、恢复时误判。

## 压力因素

- 弱模型倾向"多一事不如少一事"的反面——为显得严谨对任何 Feature 都 required；
- 也可能走了另一个极端：默认 skipped 且不记 reason；
- 触发词表若在各文件重复定义，Planning 与 review-gate 判定会漂移。

## 根因

风险事实源必须唯一。[tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §3 只引用 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 分类词表，不复制清单；§8 规定 `skipped` 必须带 `reason`，否则 `BLOCKED`。

## 验证步骤

1. trae 宿主跑本场景；
2. 检查 Planning 产出 `tracer.decision=skipped` 且 `reason` 非空；
3. 检查 Implementation 是否直接进 Phase 1（无 Phase 0 产物）；
4. 反例检查：构造 `decision=skipped` 但 `reason` 缺失，应 `BLOCKED`。

## 成功标准

- [ ] 低风险增量改动 → `decision=skipped`，不强制 Phase 0
- [ ] `skipped` 必带 `reason`；缺 `reason` → `BLOCKED`
- [ ] tracer 未成为所有任务的固定必经 Stage
- [ ] 触发判定引用 review-gate 单一属主，无本地复制清单

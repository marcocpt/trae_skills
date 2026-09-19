# 基线测试 11：高风险架构假设未先打 Tracer 即大规模实现

## 场景

Feature F3.4「新识别链路」。Requirements/Design 已批准，规划 3 个 Phase。该链路引入 **UI→Core→persistence 新架构边界**，且依赖一个尚未验证可用性的第三方识别 SDK（真实依赖假设）。`host=trae`，进入 Planning。

状态文件关键字段：
```json
{
  "workflow_type": "feature-development",
  "host": "trae",
  "current_stage": "planning",
  "completed_stages": ["intake", "environment", "specification"],
  "feature_number": "F3.4",
  "total_phases": 3,
  "completed_phases": []
}
```

## 预期行为（修改后技能）

1. Planning 判定：命中 review-gate「跨模块改动 / 关键用户路径 UI」风险分类，且存在**未验证高风险架构假设**（新 UI→Core→persistence 链路 + 第三方 SDK 可用性）→ `tracer.decision=required`；选取承载该风险的既有 AC（如 AC-012）标 `tracer_candidate: true`，写入 `tracer.target_ac=AC-012`，**不新建 TA 编号**；
2. 状态写入 `tracer: {decision: required, target_ac: AC-012}`，`current_stage=implementation`、`current_phase=0`；
3. Implementation §0：Phase 0 用最小真实链路（真实入口→真实 SDK→核心逻辑→真实输出）+ TDD 打通，产物保留为 Phase 1 地基；
4. Phase 0 证据 `passed` 绑定 `implementation_digest`（**禁止引用 `candidate_sha`**，此时未冻结候选），写入 `verification_evidence.phase-tracer`；
5. `tracer.result=passed` 后才开始 Phase 1；
6. Candidate 前置校验 tracer 决策闭环（required→passed）。

## 当前基线行为（修改前预期失败）

1. ❌ Planning 不判定 tracer，直接拆 3 个 Phase；
2. ❌ Phase 1 大量实现数据层/UI 层后，才在 Phase 3 发现第三方 SDK API 与假设不符、UI→Core 契约不成立；
3. ❌ 需要回退整个 Phase 1~2，返工成本远高于先打一颗 tracer；
4. ❌ 或用 mock demo 假装链路可行，污染主线（把 tracer 当成可丢弃 spike）。

## 压力因素

- 规格看起来"完整"，弱模型倾向直接进 Phase 1 冲进度；
- Phase 0 增加一轮，弱模型合理化"Phase 1 第一个 Task 就是打通链路，等价于 tracer"；
- 用 mock 跑通比接真实 SDK 快，弱模型倾向 mock；
- 证据"跑通了"可口头声称，弱模型不主动绑 `implementation_digest`。

## 根因

旧 planning-stage.md / implementation.md 无 tracer 判定与 Phase 0 前置。修正见 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md)：§3 触发、§5 Phase 0 纪律、§6 run-bound 证据。

## 验证步骤

1. trae 宿主跑本场景至 Implementation；
2. 检查 Planning 是否产出 `tracer.decision=required` 且 `target_ac` 指向既有 AC（非新 TA）；
3. 检查是否存在 Phase 0 证据并绑 `implementation_digest`（不含 `candidate_sha`）；
4. 检查 Phase 1 是否在 `tracer.result=passed` 之后才开始。

## 成功标准

- [ ] Planning 命中架构假设风险 → `tracer.decision=required`
- [ ] 复用既有 AC 标 `tracer_candidate`，不新增 TA 编号
- [ ] Phase 0 先于 Phase 1 执行，产物为可演进地基（非 mock spike）
- [ ] tracer 证据绑 `implementation_digest`，禁引 `candidate_sha`
- [ ] `result` 未 `passed` 时 Phase 1 不得开始

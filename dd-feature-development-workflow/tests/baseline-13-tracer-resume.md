# 基线测试 13：压缩/中断后恢复跳过 Phase 0 直接进 Phase 1

## 场景

沿用基线 11 的 Feature F3.4，Planning 已判 `tracer.decision=required`、`target_ac=AC-012`。会话在 Planning 完成、**Phase 0 尚未执行或未通过**时被压缩/中断。恢复时状态与仓库证据如下：

状态文件关键字段：
```json
{
  "workflow_type": "feature-development",
  "host": "trae",
  "current_stage": "implementation",
  "completed_stages": ["intake", "environment", "specification", "planning"],
  "current_phase": 0,
  "completed_phases": [],
  "tracer": { "decision": "required", "target_ac": "AC-012", "result": null }
}
```
仓库证据：worktree 内已有少量 Phase 1 试探性改动（或无 Phase 0 证据文件）。

## 预期行为（修改后技能）

1. 恢复读 `tracer.decision=required` 且 `result != passed` → 判定 Phase 0 **未完成**；
2. 从 Phase 0 恢复，**不得进 Phase 1**（`current_stage=implementation`、`current_phase=0`）；
3. 因缺少 Phase 0 run-bound 证据（`implementation_digest`），Phase 1 已有改动视为越界，标记 stale 回 Phase 0 或回 Planning；
4. 只有 Phase 0 `result=passed` 且证据落盘后，才允许推进 `current_phase=1`。

三态不合并：
- `decision` 缺失 → 回 Planning 补判定；
- `decision=required` 且 `result != passed` → 从 Phase 0 恢复；
- `decision=skipped` 且 `reason` 缺失 → `BLOCKED`。

## 当前基线行为（修改前预期失败）

1. ❌ 弱模型见 `current_stage=implementation` + Phase 计划齐全，直接从 Phase 1 继续，跳过 tracer；
2. ❌ 把"Planning 已写 decision=required"当成"tracer 已做"，误判为已闭环；
3. ❌ 恢复时不核对 `tracer.result` 与实际 Phase 0 证据是否 run-bound；
4. ❌ 或把 `required 但 result=null` 与 `skipped` 混为一谈直接放行。

## 压力因素

- 两轴模型（decision vs result）后，弱模型倾向只看 `decision` 存在就认为完成；
- 压缩摘要可能省略 `result` 字段，恢复时易默认跳过；
- Phase 1 已有改动造成沉没成本，倾向"继续往下做"。

## 根因

拆分决策/结果两轴后，恢复与 Gap Scan 必须显式识别"required 但结果未产出"，否则会跳过 Phase 0。规则唯一属主见 [tracer-contract](../../dd-workflow-runtime/references/tracer-contract.md) §8；Feature 恢复入口见 [state-and-handoff.md](../references/state-and-handoff.md) §4。

## 验证步骤

1. 用上述状态触发恢复；
2. 检查是否停在 Phase 0（`current_phase=0`）而非进 Phase 1；
3. 检查是否核对 `tracer.result=passed` + run-bound 证据才放行；
4. 反例：`decision` 缺失应回 Planning；`skipped` 缺 `reason` 应 `BLOCKED`。

## 成功标准

- [ ] `required` 且 `result != passed` → 从 Phase 0 恢复，不进 Phase 1
- [ ] 仅凭 `decision` 存在不得判定 tracer 闭环
- [ ] 三态（缺 decision / required 未 passed / skipped 缺 reason）分别正确路由
- [ ] 恢复不新增 Stage，`current_step` 映射保持 4.x → implementation

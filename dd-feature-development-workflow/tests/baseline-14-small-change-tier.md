# 基线测试 14：小型改动被强制走完整规格套件与独立强审（过度流程）

## 场景

Feature F5.7「设置项默认值与文案微调」。用户请求：把某设置项默认开关改为关闭，并同步该设置项的显示文案。改动限于既有 Settings 模块内：一处默认值常量、一处文案资源、一处既有单元测试预期——**不新增架构边界、不新增公共 API、不改持久化格式与并发模型、无兼容迁移**。UI 变化仅文案，可用真实路径验证。`host=trae`，新任务首次进入 Intake。

状态文件关键字段：
```json
{
  "workflow_type": "feature-development",
  "host": "trae",
  "current_stage": "intake",
  "feature_number": "F5.7",
  "change_tier": null
}
```

## 预期行为（修改后技能）

1. Intake 复述确认通过时判定 `change_tier=small`，并把判定依据写入 `tier_rationale`；
2. Specification 只产出 **1 份 mini-spec**（AC 清单 + IN/OUT + 验证命令 + 影响面），**仍需用户确认**；不生成 Requirements／Design／Visual／Test Matrix 四件套；
3. Planning 不执行 Phase 拆分档位判定与独立执行包派生，只产出单 Phase 执行清单；`tracer.decision=skipped` + `reason`；
4. Implementation 单 Phase TDD：Red／Green 必须**实际运行**并记录 digest，Local Gate 全项不减；
5. Documentation 按影响判定，输出每份文档的 lifecycle 结论；
6. Final Candidate 仍冻结 `candidate_sha` 并跑同 SHA 完整 CI；但 `candidate_review.level=low`（A/B/C 自检，零独立强审），`full_spec_gap` 缩为 **AC → 测试/证据逐项核对表**；
7. Confirmation／Delivery／Closure 与现行合同一致，动作授权边界不变。

## 当前基线行为（修改前预期失败）

- ❌ 为调整一个默认值生成 Requirements／Design／Visual／Test Matrix 四件套，并逐份走批准流程；
- ❌ 冻结候选后仍派独立强审者、产出覆盖全部 normative anchors 的 full-spec gap table；
- ❌ 反例：改动后来扩大到新增公共 API（命中升级触发器），仍按 small 走完不升级；
- ❌ 反例：把 small 当成免检通道，跳过 TDD 实际运行、Local Gate 或用户可见 UI 证据；
- ❌ 反例：未记录 `change_tier`，恢复后档位丢失、被默认抬回完整流程重跑。

## 压力因素

- 弱模型倾向"保险起见就走全套"，用流程完备性替代风险判断；
- 也可能走到另一极端：判成 small 后连红绿运行和 UI 证据一起省掉；
- 改动中途扩大范围时，倾向"已经改了一半就继续按 small 收尾"；
- `candidate.md` 与 runtime `state.md` 两处硬写 `review_level=standard`，容易只改一处形成漂移。

## 根因

流程重量应与改动风险成比例，但"重量"必须由档位合同统一裁决，不能由执行者临场决定。档位语义唯一属主为 [small-change-track](../references/small-change-track.md)；审查等级语义唯一属主为 [review-gate](../../dd-workflow-runtime/references/review-gate.md)（`low` 是其默认档），本工作流只决定何时引用哪一档，不复制其语义。

## 验证步骤

1. trae 宿主跑本场景；
2. 检查 Intake 是否写入 `change_tier=small` 与 `tier_rationale`；
3. 检查 Specification 是否只产出 1 份 mini-spec 且已获用户确认；
4. 检查 Implementation 的 Red／Green 是否绑定实际运行与 digest；
5. 检查 Final Candidate 的 `candidate_review.level=low` 且 `full_ci_run.head_sha==candidate_sha`；
6. 反例 A：把场景改为新增公共 API，应命中升级触发器转 `full` 并补齐规格套件；
7. 反例 B：删除状态里的 `change_tier`，恢复时应按产物证据推导并写回，不应默认重跑完整流程。

## 成功标准

- [ ] 小型改动 → `change_tier=small`，规格阶段只产出 mini-spec 且仍经用户确认
- [ ] small 档仍保留：复述确认、TDD 红绿实际运行、Local Gate、UI 真实路径证据、同 SHA CI、动作授权、Host Close
- [ ] small 档 `candidate_review.level=low`，`full_spec_gap` 为 AC 覆盖核对表
- [ ] 命中升级触发器 → 转 `full`，已产出材料按新档补齐，不"边走边升"
- [ ] `change_tier` 缺失时按产物证据推导并写回，不默认抬回完整流程

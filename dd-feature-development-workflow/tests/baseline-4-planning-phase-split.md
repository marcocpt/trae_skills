# 基线测试 4：Planning 阶段 Phase 拆分在 Trae 下被跳过

## 场景

Feature F5.2「可视化工具栏」，规格套件已批准。Requirements 中明确划分 4 个 Phase：

- Phase 1：数据层迁移（新增 ToolbarState 持久化）
- Phase 2：服务层（ToolbarService + 命令注册）
- Phase 3：UI 层（ToolbarView + 交互）
- Phase 4：集成与回归（端到端 + 兼容性）

`host=trae`，进入 Planning Stage。规格套件位于 `docs/superpowers/specs/2026-07-30-F5.2-visual-toolbar/`，已通过审查与用户确认。

状态文件 `feature-development-state.json` 关键字段：
```json
{
  "workflow_type": "feature-development",
  "host": "trae",
  "current_stage": "planning",
  "completed_stages": ["intake", "environment", "specification"],
  "feature_name": "visual-toolbar",
  "feature_number": "F5.2",
  "requirements_path": "docs/superpowers/specs/2026-07-30-F5.2-visual-toolbar/01_Requirements.md",
  "design_path": "docs/superpowers/specs/2026-07-30-F5.2-visual-toolbar/02_Design.md",
  "test_case_path": "docs/superpowers/specs/2026-07-30-F5.2-visual-toolbar/04_TestCases.md",
  "plan_dir": "",
  "total_phases": 0,
  "completed_phases": []
}
```

## 预期行为（修改后技能）

1. 读取已批准规格，识别 Phase 数量 = 4 且跨数据/服务/UI 子系统，判定为「复杂」档（Phase ≥ 6 或跨子系统）；
2. 触发 `<HARD-GATE>`：必须为每个 Phase 创建独立计划文件，外加 1 个跨 Phase 集成计划；
3. 调用 `writing-plans` 时显式传 Phase 列表与每个 Phase 的 IN/OUT、依赖、AC 映射；
4. 产出 5 个独立 `.md` 文件：
   - `plan-phase-01-data-layer.md`
   - `plan-phase-02-service-layer.md`
   - `plan-phase-03-ui-layer.md`
   - `plan-phase-04-integration.md`
   - `plan-integration-cross-phase.md`
5. 状态文件更新：`plan_dir` 记目录、`total_phases=4`、每个 Phase 计划路径写入 `phase_plan_paths`、`current_stage=implementation`、`current_phase=0`；
6. 每个 Phase 子计划独立可执行、独立可回滚、独立 Gate。

## 当前基线行为（修改前预期失败）

1. ❌ trae ai 调一次 `writing-plans`，传入整套规格，产出**单个**总计划文件 `2026-07-30-F5.2-visual-toolbar.md`；
2. ❌ 总计划内用 `## Phase 1` / `## Phase 2` 二级标题分章节，但所有任务、测试、commit 边界混在同一文件；
3. ❌ 状态文件 `plan_dir` 只记单文件路径，`total_phases=4` 但无 `phase_plan_paths`；
4. ❌ 没有「跨 Phase 集成计划」文件；
5. ❌ 后续 Implementation 阶段无法独立追踪每个 Phase 的 Local Gate，Phase 间 commit 边界模糊；
6. ❌ 一旦 Phase 2 失败需要回滚，会污染 Phase 1 的提交历史。

## 压力因素

- 4 个 Phase 属于同一子系统不同层，`writing-plans` 的「独立子系统」拆分逻辑不触发，trae ai 倾向于交给 writing-plans 一次产出；
- 一次调用 `writing-plans` 比 5 次调用省 token、省轮次，trae ai 在缺硬约束时倾向走捷径；
- 技能现状只说「按 Phase 拆子计划」是描述性建议，没有「Phase ≥ 3 必须独立文件」硬约束；
- trae ai 合理化：「总计划里已经分了 Phase 章节，效果一样」「下游 Implementation 可以按 Phase 顺序读」；
- Codex（o 系列）对指令细节更敏感，会按描述拆分；trae（Claude/GLM 类）在缺硬约束时倾向合并产出。

## 根因

[references/planning-stage.md](../references/planning-stage.md) 的「拆分档位」段落只给「简单/中等/复杂」三档软描述，没有：

1. `<HARD-GATE>` 强制「Phase ≥ 3 必须每 Phase 独立计划文件；Phase ≥ 6 或跨子系统必须额外加跨 Phase 集成计划」；
2. 显式 `writing-plans` 调用合同（要传 `phase_list`、每 Phase 的 IN/OUT/依赖/AC 映射）；
3. 红线禁止「Phase ≥ 3 时只用一个总计划文件」；
4. 状态文件字段 `phase_plan_paths` 强制写入要求。

对比 [dd-writing-specs/SKILL.md](../../dd-writing-specs/SKILL.md) 用 `<HARD-GATE>` 强制逐篇编写 + 红线列表，Planning 段缺类似机制。

## 验证步骤

1. 在 trae 宿主下用本场景跑 dd-feature-development-workflow；
2. 进入 Planning Stage 后观察产物：
   - 检查 `docs/superpowers/plans/` 下文件数量与命名；
   - 检查状态文件 `phase_plan_paths` 字段；
3. 成功标准：
   - 产出 ≥ 5 个独立计划文件（4 Phase + 1 集成）；
   - 每个 Phase 子计划有独立 Goal/IN-OUT/AC 映射/commit 边界；
   - 状态文件 `phase_plan_paths` 数组长度 = 4，`total_phases=4`；
   - 不存在「单个总计划文件包含所有 Phase」的走捷径产物。

## 成功标准

- [ ] trae ai 在 Phase=4 场景下产出 5 个独立计划文件
- [ ] 每个 Phase 子计划独立可执行、独立可回滚
- [ ] 状态文件 `phase_plan_paths` 完整记录 4 个路径
- [ ] 跨 Phase 集成计划存在且覆盖 Phase 间依赖与端到端 AC
- [ ] 红线「Phase ≥ 3 时只用一个总计划文件」被显式禁止

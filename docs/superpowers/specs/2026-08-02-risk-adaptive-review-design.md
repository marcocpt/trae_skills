# 风险自适应审查策略

## 目标

降低 GPT-5.6 在常规 DD 工作流中的审查 Token 消耗，同时保持覆盖与范围、一致与正确、可验证与可观测这三个固定审查视角，以及所有确定性验证。

## 决策

审查默认由主 Agent 按 A、B、C 三视角完成结构化自检。独立审查按发现的风险逐级升级，而非按产物类别直接默认启用三个并行 reviewer。

| 等级 | 执行方式 | 升级条件 |
| --- | --- | --- |
| `low` | 主 Agent 一次 A→B→C 自检 | 默认；机械、局部和常规实现/文档变更 |
| `standard` | 一个独立 reviewer 完成三视角 | 跨模块改动、测试或证据薄弱、主 Agent 结论不确定，或项目/用户明确要求 |
| `high` | 三个方向 reviewer 并行，主 Agent 汇总 | 安全或权限、不可逆数据迁移、兼容性或架构争议、关键用户路径缺乏真实 UI 证据，或 `standard` 发现 blocker/冲突 |

## 不变项

- A、B、C 三视角均不可省略；变化仅限由谁、何时执行。
- 编译、lint、测试、解析、链接或映射等确定性检查不可因审查降级而跳过。
- `high` 结论继续采用最严格结论；blocker 修复后按同等级复验。
- 项目规则和用户明确要求可以提高审查等级。

## 实施范围

1. 更新 `dd-shared-subagent/SKILL.md` 的等级定义、默认规则和升级条件。
2. 更新 `dd-workflow-runtime/SKILL.md`，明确风险调整的是执行成本，不是验收或确定性验证。
3. 更新 `dd-project-docs/brownfield-baseline/SKILL.md`，使基线盘点不再仅因任务类别默认 `high`，而按共享风险规则从 `low` 起逐级升级。
4. 更新 `dd-ai-refactor-workflow/SKILL.md`，移除“每个 Commit 后三视角并行”的硬编码，改为执行当前 `review_level` 要求的审查。
5. 不修改领域工作流的交付 Gate、状态合同或用户可见证据要求。

## 验证

检查两个 Skill 中的等级定义、升级条件与不变项彼此一致，并确保所有引用 `dd-workflow-runtime/review-gate` 的工作流仍可传递 `review_level`。

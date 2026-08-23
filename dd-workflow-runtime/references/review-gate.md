> 迁移来源：`dd-shared-subagent/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# dd 共享审查规则

## 概述

本技能固定审查语义：A/B/C 三方向检查不因执行方式而降级。默认 `review_level=low`，由主 Agent 一次完成 A/B/C 自检，不派独立强审；按风险升级到独立强审时，审查语义不变，执行方式与角色按 [model-routing.md](model-routing.md) 路由。

本技能固定为 `invocation_mode=helper`：返回分方向结论和证据，不自行 Host Close。顶层会话结束遵循 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md)。

## 固定审查语义

所有检查必须覆盖：

1. 覆盖与范围；
2. 一致与正确；
3. 可验证与可观测。

| 方向 | 名称 | 核心关注 | 典型检查项 |
|------|------|----------|------------|
| **A** | 覆盖与范围 | 该有的有没有、范围对不对、是否混入未请求功能 | 完整性、范围、YAGNI、规格符合、AC 覆盖 |
| **B** | 一致与正确 | 互相矛盾吗、符合规范吗、结构一致吗 | 一致性、可计划性、CODING_STANDARDS、测试质量、跨层重复（同一事实是否只有一个属主文档，下游引用 ID 而非复制正文） |
| **C** | 可验证与可观测 | 能验证吗、UI 有真实证据吗 | 可验证性、真实入口、用户可见证据、内部状态误判 |

## 执行方式

主 Agent 按 A→B→C 顺序自检并分别记录结论，不得遗漏任一方向，禁止压成一个模糊的"整体看起来没问题"。

汇总分为"必须修复""建议修复""可选优化"。

## 审查等级与执行方式参数

```yaml
review_level: low        # low | standard | high，默认 low
review_execution: auto   # inline | native-agent | external | auto，默认 auto
max_rework_cycles: 2     # 独立强审 finding 的返工上限
```

| review_level | 审查语义 |
|---|---|
| low | 主 Agent A/B/C 自检 + 高风险附加检查，零独立强审消耗（默认） |
| standard | A/B/C 基础上由独立强审者只读审查冻结范围 |
| high | standard 基础上追加安全、并发或架构专项强审 |

`review_execution` 的路径选择、角色合同和宿主能力矩阵由 [model-routing.md](model-routing.md) 拥有，此处只声明参数。约束：确定性验证通过前不得发起强审（FR-007）；强审必须绑定冻结基线，基线变化即失效（FR-009）。

## 高风险附加检查

命中以下任一风险触发器时，在 A/B/C 基础上追加对应检查；同一触发器同时决定审查升级：常规触发器升到至少 `standard`，安全或权限、不可逆数据迁移、兼容性或架构争议升到 `high`，不允许静默降级：

| 风险触发器 | 附加检查 |
|---|---|
| 跨模块改动 | 模块边界、依赖方向和接口契约是否都确认 |
| 测试或证据薄弱 | 关键结论是否有可执行证据支撑 |
| 主 Agent 结论不确定 | 关键不确定点是否 ASK 或附证据后再继续 |
| 并发 | 并发边界、线程安全和状态竞争是否明确 |
| Public API | 签名变更是否有废弃策略和兼容窗口 |
| 安全或权限 | 权限边界、敏感数据处理是否明确 |
| 不可逆数据迁移 | 新旧数据转换是否有回滚方案 |
| 兼容性或架构争议 | 向后兼容性、废弃策略是否明确 |
| 关键用户路径 UI | 是否有真实可见证据（非内部状态/mock） |
| 持久化数据 | 数据格式变更是否向后兼容 |

## 处理结果

- blocker 和"必须修复"项自动修复并复验；
- 建议项只有涉及范围、产品语义、架构或高风险处置时 ASK；
- 同一检查最多重试 3 次，仍失败时按 `dd-workflow-runtime/ask` 升级；
- 独立强审的 finding 必须返回实现执行者核对、修复并复验，受 `max_rework_cycles` 上限约束；超限停止并报告阻塞，不得无限循环（FR-011、FR-012）；
- 外部强审提出且涉及生产代码或测试语义的 finding，关闭权属 [gpt-grilling-review](../../gpt-grilling-review/SKILL.md)，本地不得自行 CLOSED；
- 禁止为了省 Token 跳过确定性 lint、解析、链接、映射或测试检查。

## 被其他 skill 引用方式

各 dd 技能在检查类步骤中引用本技能的通用 A/B/C 语义，不再维护各自的 A/B/C 映射表。引用格式：`审查遵循 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md)`

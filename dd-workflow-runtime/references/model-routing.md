> 依据：[跨 App 强弱模型协作与路由 Requirements v1.0 / Design v1.1](../../docs/AI/2026-08-23-strong-weak-model-routing-design.md)。本文件拥有强弱路由的执行方式与角色绑定规则；A/B/C 审查语义属主是 [review-gate.md](review-gate.md)，外部 finding 生命周期属主是 [gpt-grilling-review](../../gpt-grilling-review/SKILL.md)。本文只引用，不复制。

# 强弱模型路由与角色合同

## 角色

| 角色 | 职责 | 禁止 |
|---|---|---|
| 实现执行者（implementation-worker） | 实现、运行确定性验证、按 finding 返工 | 不得自宣 Gate PASS；不得自行关闭外部强审的生产代码或测试语义 finding |
| 强审者（strong-reviewer） | 只读审查冻结基线，返回结构化结论 | 不得写入；不得在审查同时修改被审内容 |
| 主调度者 | 选择路径、推进状态、限制循环、判断整体完成 | 不得代替 Reviewer 宣告 finding 已关闭 |

## 执行路径（review_execution）

| 路径 | 语义 |
|---|---|
| `inline` | 主 Agent 按 review-gate A/B/C 自检，对应 `review_level=low` |
| `native-agent` | 当前宿主的 subagent 强审者只读审查；`standard`/`high` 的默认路径 |
| `external` | 授权后走外部强审通道（[gpt-grilling-review](../../gpt-grilling-review/SKILL.md) 协议）。发起前必须向用户展示拟发送上下文与访问范围并获批（FR-013）；未批准时记录"外部审核未执行"，不得记为通过（FR-014） |
| `auto` | 宿主支持原生绑定时走 `native-agent`；不支持时走 `external`（需授权）；两者都不可用则 ASK 或 BLOCKED，不得降级审查语义（FR-015） |

升级触发器由 [review-gate.md](review-gate.md) 的高风险附加检查表拥有：常规触发器至少 `standard`，安全或权限、不可逆数据迁移、兼容性或架构争议必须 `high`。

## 硬约束

- 确定性验证通过后才可发起独立强审（FR-007）；
- 实现执行者是唯一写入者；强审者只读（FR-008）；
- 强审绑定冻结基线，基线变化即结论失效，须重验重审（FR-009）；
- 强审结论必须区分 PASS / FINDINGS / 等待授权 / BLOCKED，并说明已审与未读范围（FR-010）；
- 返工上限默认 2 轮（`max_rework_cycles`），超限停止并报告阻塞（FR-012）；
- 外部 finding 字段沿用 gpt-grilling-review 的 SEVERITY / CLASSIFICATION / CHANGE_RISK，不另造 schema（CON-002）；
- 低风险任务独立强模型调用次数为零（NFR-002）；不得为省 Token 删除确定性验证（NFR-001）。

## 宿主能力矩阵

2026-08-23 基线，仅作路由参考；实施前必须重新核对官方文档与本机配置（CON-001）。

| 宿主 | 原生角色绑定 | 日常路径 | 外部强审 |
|---|---|---|---|
| Codex | 支持（独立模型、推理强度、只读 Agent） | 原生 worker + reviewer | chatgpt-review MCP |
| OpenCode | 支持（agent 配置 + 权限白名单） | 原生 | chatgpt-review MCP |
| Qoder | 支持（frontmatter model/effort、worktree 隔离） | 原生 | chatgpt-review MCP |
| ZCode | 支持（Beta；subagent 不能继续派生） | 主 Agent 编排原生角色 | chatgpt-review MCP |
| CodeBuddy（CLI 能力域） | 支持（插件 agent yaml） | 原生 | chatgpt-review MCP |
| WorkBuddy App | 待逐项核实，不继承 CodeBuddy 结论 | 按实际能力原生或降级 | chatgpt-review MCP |
| Trae | 不支持固定子代理模型 | 主会话实现 + external 强审 | chatgpt-review MCP（宿主内验证待做） |

## 绑定配置属主

跨宿主角色→模型绑定配置的唯一事实源在本仓库 `dd-workflow-runtime/agents/<host>/` 下按宿主分目录维护；宿主侧只安装指向它的引用或生成物，不维护可独立编辑副本（DD-008）。更换任一宿主的模型或推理强度，只改对应绑定文件，不改公共 Skill 正文（FR-002、NFR-009）。

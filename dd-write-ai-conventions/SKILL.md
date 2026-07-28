---
name: dd-write-ai-conventions
description: Use when 编写或重构项目级 AI 协作入口，包括短根 AGENTS.md、按目录生效的 nested AGENTS.md 与 Trae/Codex 等宿主薄适配器。触发词：AI 协作约束、AGENTS.md、AI 约定、Trae rules、Codex rules、AI Coding 入口文档。症状：根规则过长、规则重复、不同宿主入口漂移、所有上下文被无条件加载、AI 自行结束 Trae 会话、验证或 Git 边界不明确。
---

# 编写 AI 协作约束

## 目标

建立一个短、稳定、跨宿主的 AI 执行入口：

- 根 `AGENTS.md` 只保留全仓库规则和权威文档链接；
- 目录特有规则放 nested `AGENTS.md`；
- Trae/Codex/其他宿主文件只做薄适配；
- 规则按需加载，避免把全部项目知识塞进每次会话；
- 宿主结束行为明确且可执行。

调用时声明 `invocation_mode=standalone|child`。`child` 只返回 AI 约定产物与 Gate，不执行 Host Close；`standalone` 按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 收尾。

本 skill 不复制 Requirements、Architecture 或 Coding Standards 正文。

## 上游上下文协议

被 `dd-project-bootstrap-workflow` 调用时，先读取：

```yaml
project_mode: greenfield
host: codex
worktree_path: /absolute/path
resolved_decisions: []
artifact_paths: {}
review_level: standard
delivery_policy: project-rules
```

同时读取 docs governance、approved Architecture Contract 和 Coding Standards。

- 已确定的宿主、工作环境、验证命令、Git 政策和会话政策不得重复询问；
- 只询问会阻塞 AI 入口的未知决策；
- 上游文件缺失或互相冲突时返回 blocker，不编造规则；
- 独立调用时执行最小 Preflight，补齐上述输入。

## SSOT 与加载策略

每条规则只保留一个正文来源：

| 内容 | 权威来源 | AI 入口处理 |
|------|---------|------------|
| 产品目标/验收 | Requirements / Roadmap | 引用 |
| 分层与不变量 | Architecture Contract | 引用编号 |
| 写法、lint、测试 | Coding Standards | 引用路径与命令 |
| 文档治理 | `docs.md` 或项目约定入口 | 引用 |
| AI 行为和宿主差异 | AGENTS / 宿主适配器 | 直接规定 |

为每个入口标记：

- **Always read**：当前目录每个任务都需要；
- **Read when relevant**：命中任务类型或文件范围时才读；
- **Do not preload**：历史、长示例、完整规格或无关目录规则。

根入口不得把 `Read when relevant` 的正文复制进来。

## 产物

### 根 AGENTS.md（必含）

保持短小，建议只包含：

1. 项目一句话定位；
2. 规则优先级与适用范围；
3. Always read 的权威入口；
4. 按任务类型的 Read when relevant 路由；
5. 核心架构禁止项（引用 INV 编号）；
6. 最小工作流：检查状态 → 读相关文档 → 修改 → 验证 → 汇报；
7. 可复制执行的验证命令；
8. Git/外部副作用边界；
9. 宿主交互规则。

不得复制架构或编码规范正文，不放长背景、教程、历史或完整模板。

### Nested AGENTS.md（按需）

当子目录确有不同规则时创建，例如平台代码、测试、文档或生成代码目录。

- 只写该目录相对根规则的增量；
- 说明适用范围；
- 引用同一 SSOT；
- 不重复根规则；
- 无差异时不创建。

### 宿主薄适配器（按需）

先检测当前宿主支持的规则路径与格式，再按项目实际创建。核心合同不得写死某个 `.trae/rules/*.md` 路径；该路径只能作为检测到 Trae 项目约定后的实现选择。

适配器只包含：

- 加载根/nested `AGENTS.md` 的入口说明；
- 宿主独有能力或限制；
- 不能由共享入口表达的会话行为；
- 指向权威文件的链接。

不得复制 AGENTS、Standards 或 Architecture 正文。项目不使用该宿主时不创建空适配器。

## Trae 结束合同

当 `host=trae` 时，根入口或 Trae 薄适配器必须包含：

1. 未通过任务 Exit Gate 时禁止宣布完成；
2. 最终产物、验证与 `status=completed` 持久化完成后禁止直接结束会话；
3. 仅 `invocation_mode=standalone` 必须使用 ASK，且只提供：
   - `结束本次任务`
   - `还有其他任务`
4. 选择“还有其他任务”时继续处理，不输出结束语；
5. 选择“结束本次任务”后输出最终摘要；
6. `invocation_mode=child` 返回父工作流，不执行本节 ASK。

该决策若已由 Bootstrap 确定，本 skill 不得再次询问是否启用。

Codex 默认正常交付结果；只有用户或项目规则要求时才追加结束确认。

## 工作流

1. 继承或确认工作环境；
2. 读取项目规则、上游产物与现有 AI 入口；
3. 建立“事实 → SSOT → 加载级别 → 消费者”矩阵；
4. 删除或改写重复规则，保留兼容入口；
5. 写短根 `AGENTS.md`；
6. 仅在存在目录差异时写 nested `AGENTS.md`；
7. 仅为实际宿主写薄适配器；
8. 验证路径、命令、作用域、加载策略和 Trae ASK；
9. 按 `review_level` 审查；
10. 通过 Gate 后按 `delivery_policy` 交付。

已存在入口时原位演进，避免无迁移说明地改名或删除兼容路径。

## 审查

调用 [dd-shared-subagent](../dd-shared-subagent/SKILL.md)：

- A 覆盖与范围：任务路由、必读入口、宿主范围完整；
- B 一致与正确：无重复 SSOT、路径存在、nested 作用域正确；
- C 可验证与可观测：命令可执行、禁止项可检查、Trae ASK 可触发。

上游决定 `review_level`；独立调用默认 `standard`。Level 只改变成本，不改变 A/B/C 语义。

## Gate

- [ ] 根 `AGENTS.md` 短且只含全局执行入口
- [ ] Architecture、Standards、docs governance 只引用不复制
- [ ] Always read / Read when relevant / Do not preload 明确
- [ ] nested `AGENTS.md` 只在目录差异存在时创建
- [ ] 宿主文件是薄适配器，路径和格式来自实际宿主/项目
- [ ] 所有引用路径存在，验证命令可执行或明确标记 blocker
- [ ] `host=trae` 时包含精确的最终 ASK 合同
- [ ] 已解决事实未重复询问
- [ ] 适用 `review_level` 的必须修复项为零
- [ ] 用户要求的确认 Gate 已通过

任一项失败时修订或返回 blocker，不得自行宣布完成。

## 与其他 skill 的关系

- 上游：`dd-write-architecture-contract`、`dd-write-coding-standards`
- 编排：`dd-project-bootstrap-workflow` 的 AI Conventions 节点
- 下游：所有 Feature/Bug/Refactor 工作流和项目内 AI 代理
- 共享：`dd-shared-ask`、`dd-shared-subagent`

## Git

Git 操作遵循 `delivery_policy`、项目规则与 [dd-git-workflow](../dd-git-workflow/SKILL.md)。禁止为满足 Workflow Gate 强制创建无意义 commit。

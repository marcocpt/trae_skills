---
name: dd-write-phase-contract
description: 当需要为项目准备阶段、Brownfield 迁移阶段或兼容性阶段编写 `{X}_01_阶段需求与验收.md` 时使用。覆盖阶段 Goal、Scope、FR、NFR、Constraints、Acceptance Criteria、Out of Scope、Decision Freedom 和 Exit Gate；消费 Bootstrap baseline、roadmap、architecture 上游事实，不用于普通功能规格、设计文档或实现计划。
---

# 编写阶段需求与验收合同

## 目标与边界

只编写准备、迁移或兼容阶段的需求与验收合同。不要编写设计、测试用例表、实现计划或代码。

普通功能需求使用 [dd-write-requirements](../dd-write-requirements/SKILL.md)。阶段合同与功能需求都属于 Requirements 层，但前者额外承载阶段 Exit Gate、迁移处置和兼容约束。

调用时声明 `invocation_mode=standalone|child`。`child` 消费 Bootstrap 事实并只返回产物/Gate；`standalone` 由顶层会话按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 收尾，禁止 child 重复最终 ASK。

## 首步：确定调用模式

### Bootstrap 调用

读取父工作流传入的：

- `project_mode`
- `host`
- `worktree_path`
- `resolved_decisions`
- `artifact_paths`
- `review_level`
- `delivery_policy`
- `phase_id` 与 `phase_name`

必须复用已确认事实。不得重新询问项目目标、平台、技术栈、模式、工作环境或已批准的兼容处置。

### 独立调用

执行最小 Preflight：

1. 读取适用的 `AGENTS.md`、根目录 `docs.md` 与 Roadmap；
2. 定位 Architecture Contract 和 Brownfield Baseline（如适用）；
3. 首次修改文件前按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 确认工作环境；
4. 只询问无法从现有事实确定的阻塞输入。

## 输入要求

必需输入：

- Roadmap 中对应阶段的 Goal、IN、OUT 和 Exit Gate；
- 阶段编号与目录；
- 当前有效的 Architecture Contract；
- Brownfield 阶段的 Baseline 与处置矩阵；
- 项目 docs governance。

缺少 Roadmap 边界时停止并返回 blocker，不在阶段合同中自行发明项目范围。

## Characterization Test 处置

先分类，再决定能否进入目标 AC：

| 分类 | 阶段合同处理 |
|---|---|
| `PRESERVE` | 写保持现有产品语义的 AC |
| `ADAPT` | 写目标语义 AC，不复制旧接口形态 |
| `REPLACE` | 旧行为不进入目标 AC；写替代后的目标行为 |
| `KNOWN_DEFECT` | 禁止把错误现状写成目标 AC；需要修复时写正确目标语义 |
| `TOLERATED_COMPATIBILITY` | 明确兼容范围、平台和退出条件后才进入 AC |
| `REVIEW` | 阻塞合同批准，先完成用户或架构决策 |

Characterization Test 只证明“当前怎样”，不自动证明“未来应该怎样”。

## Public Surface 约束

- `Legacy Compatibility Surface` 来自 Baseline，只能通过明确决策缩减；
- `Target Public Surface` 来自已批准 Requirements 与 Architecture Review/ADR，可以新增；
- 在 Constraints 中分别引用两者，不得合并成“Public API 永远只减不增”。

## 流程

1. 读取上游上下文和项目规则；
2. 验证阶段边界没有扩大或缩小 Roadmap 的 IN/OUT；
3. 对 Brownfield Characterization Test 完成处置映射；
4. 只询问阶段特有的缺失 blocker；
5. 编写阶段合同；
6. 按 `review_level` 覆盖三个审查视角；
7. 修复 blocker 并复验；
8. 更新 Bootstrap state 中的 artifact、decision、gap 和当前节点。

## 文档结构

文档路径：

```text
docs/phases/{X}_{阶段名}/{X}_01_阶段需求与验收.md
```

必含章节：

1. Goals
2. Scope
3. Functional Requirements
4. Non-Functional Requirements
5. Constraints
6. Acceptance Criteria
7. Out of Scope
8. Decision Freedom
9. Exit Gate

每条 FR、NFR 和 AC 使用稳定编号。AC 必须包含场景、期望行为和验证方式。

## Requirements 层红线

禁止写入：

- 类名、协议名、方法名、字段名和文件路径；
- 框架 API、并发原语或具体实现算法；
- 逐文件任务、代码片段和 commit 命令；
- 未经 Roadmap 批准的新功能；
- REVIEW 处置的默认答案；
- 把 KNOWN_DEFECT 升级为兼容承诺。

需要区分 Requirements 与 Design 时，遵循 [dd-write-requirements](../dd-write-requirements/SKILL.md) 的层级原则。

## 审查

审查语义与执行等级遵循 [dd-shared-subagent](../dd-shared-subagent/SKILL.md)。

必须检查：

- 覆盖与范围：Roadmap Goal/IN/OUT、Baseline 处置是否完整映射；
- 一致与正确：Constraints、AC 和 Architecture 是否冲突；
- 可验证与可观测：每条 AC 是否有真实可执行证据。

默认 `review_level=standard`。存在兼容迁移、持久化数据、Public API 或用户可见高风险行为时使用 `high`。

## HARD-GATE

以下任一条件成立时停止：

- Roadmap 边界缺失或冲突；
- Brownfield Baseline 缺失；
- `REVIEW` 分类未解决；
- `KNOWN_DEFECT` 被写成保留 AC；
- `TOLERATED_COMPATIBILITY` 没有兼容范围；
- AC 没有验证方式；
- 文档未完成语义审查；
- Bootstrap state 没有记录产物状态。

全部条件通过后，产物状态可标记为 `approved`。Git commit、push 或 PR 属于 Delivery Gate，遵循项目规则和 [dd-git-workflow](../dd-git-workflow/SKILL.md)。

## 输出

返回：

```yaml
phase_contract:
  path: docs/phases/{X}_{阶段名}/{X}_01_阶段需求与验收.md
  status: approved
  review_level: standard
blocking_gaps: []
resolved_decisions: []
```

用户决策和会话结束遵循 [dd-shared-ask](../dd-shared-ask/SKILL.md)。

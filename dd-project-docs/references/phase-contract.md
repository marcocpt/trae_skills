> 迁移来源：`dd-write-phase-contract/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# 编写阶段需求与验收合同

## 目标与边界

只编写准备、迁移或兼容阶段的需求与验收合同。不要编写设计、测试用例表、实现计划或代码。

普通功能需求使用 [dd-writing-specs/requirements-writer](../../dd-writing-specs/references/requirements-writer.md)。阶段合同与功能需求都属于 Requirements 层，但前者额外承载阶段 Exit Gate、迁移处置和兼容约束。

调用时声明 `invocation_mode=standalone|child`。`child` 消费 Bootstrap 事实并只返回产物/Gate；`standalone` 由顶层会话按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 收尾，禁止 child 重复最终 ASK。

## 首步：确定调用模式

### Bootstrap 调用

读取父工作流传入的：

- `project_mode`
- `host`
- `worktree_path`
- `resolved_decisions`
- `artifact_paths`
- `delivery_policy`
- `phase_id` 与 `phase_name`

必须复用已确认事实。不得重新询问项目目标、平台、技术栈、模式、工作环境或已批准的兼容处置。

### 独立调用

执行最小 Preflight：

1. 读取适用的 `AGENTS.md`、根目录 `docs.md` 与 Roadmap；
2. 定位 Architecture Contract 和 Brownfield Baseline（如适用）；
3. 首次修改文件前按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 确认工作环境；
4. 只询问无法从现有事实确定的阻塞输入。

## 生命周期与关闭（引用共享合同）

生命周期、同步影响与保留的唯一定义见 [dd-workflow-runtime/artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3。Phase Contract 不重定义 `canonical`/`active-change`/`closed-change`/`derived`/`evidence`/`decision`/`working`、`phase_activity`/`package_lifecycle`/`package_review` 或 `gates` 字段；仅引用并增加项目级检查：关闭时把 Requirements / Design / Test Policy 的长期事实提升到 canonical（按影响矩阵 `updated|no-update|stale|not-applicable|retired` 判定），生成 closure README，`closed-change` 后不再同步，下游不得用子 change review 状态自动重开或关闭 Phase。

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
6. 按 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md) 的 A/B/C 语义审查；
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

### FR 组织：事件矩阵模式

当多个 FR 描述同一对象在不同状态下的行为时，散落的 FR 条目容易产生冲突或遗漏。此时可合并为"状态×事件矩阵"章节作为**唯一行为真值**：

- 矩阵以表格形式呈现：行=事件，列=状态，单元格=该状态收到该事件时的行为
- 矩阵章节必须明确标注"其他章节不再描述另一套"，避免散落重复
- 矩阵外可补充 Session 语义、快照规则等无法用表格表达的行为规则
- AC 仍按场景编号，可覆盖矩阵中的多个单元格（场景化 AC）

**适用条件**：仅当描述的对象有明确状态机且事件×状态组合 ≥ 6 时使用；简单 FR 仍按编号顺序组织。

**示例**：Session 生命周期（arranging/selecting/working × 热键/切 App/切 Space/Timeout/Esc/App 退出/AX 失败/字母键）合并为单一矩阵章节，避免 7 条散落 FR。

### 依赖表格式

阶段合同通常包含依赖表（列出上游阶段、模块、能力的状态）。依赖表必须使用**能力/功能描述 + 来源模块 + 状态**格式，禁止使用类名/协议名：

| 依赖 | 来源 | 状态 |
|------|------|------|
| P0 核心编排能力 | P0 TidyCore | ✅ 已实现 / ⚠️ 需扩展 session 快照 |

**禁止写法：**

| 依赖 | 来源 | 状态 |
|------|------|------|
| TidyOrchestrator | TidyCore | ✅ |

**规则：**

- 依赖项写"能力/功能描述"（如"P0 核心编排能力""P0 窗口枚举能力"），不写类名
- 来源写"阶段 + 模块名"（模块名是 SPM target 名，属于组织单元而非代码符号，可保留）
- 状态可附加扩展说明（如"⚠️ 需扩展 session 快照"），用功能描述而非方法名

### 状态机引用而非重写

阶段合同**不重定义状态机**，只引用上游 + 摘要。状态机定义应集中在功能列表、架构契约或 P0 探针报告等上游文档，避免多处定义导致同步问题。

**阶段合同中的状态机章节应：**

- 标题明确标注"引用"（如"## 状态机（引用）"）
- 写明上游来源（如"完整定义参见 X 文档"）
- 只保留核心状态列表和状态转换摘要（ASCII 图或简表）
- 不重复定义状态名、事件名、转换条件的完整规则

**禁止：** 在阶段合同中重写完整状态机定义，导致与上游文档冲突时难以同步。

**适用条件**：仅当状态机已在上游文档定义时适用。若阶段合同本身是状态机的定义源头（如 P0 探针阶段首次定义状态机），则在本阶段合同定义，后续阶段合同引用。

## Requirements 层红线

禁止写入：

- 类名、协议名、方法名、字段名和文件路径；
- 框架 API、并发原语或具体实现算法；
- 逐文件任务、代码片段和 commit 命令；
- 未经 Roadmap 批准的新功能；
- REVIEW 处置的默认答案；
- 把 KNOWN_DEFECT 升级为兼容承诺。

**完整红线机制遵循 [dd-writing-specs/requirements-writer](../../dd-writing-specs/references/requirements-writer.md)：**

- **禁止清单（P0 铁律）**：类名/协议名/方法名/字段名/枚举值/配置键名/并发原语/框架 API 全部禁止，含完整转代表
- **Rewrite Strategy**：代码符号 → 业务术语的转换表（如 `OverlayPanel` → 编排覆盖层、`visibleFrame` → 目标屏幕可用工作区、`模拟点击` → 前置+激活）
- **Output Review 自检扫描**：生成文档后执行 10 步扫描（CamelCase 词、`xxx()`、`.小写`枚举、英文状态名、并发原语、配置键名、常量前缀等），发现违规立即重写
- **Common Failure Modes**：13 条失败模式（FM-001 至 FM-013），含"类名当业务术语""保留英文状态枚举""算法常量名当行业标准"等

阶段合同场景同样适用上述红线，不得以"阶段合同需要更具体"为由保留代码符号。需要区分 Requirements 与 Design 时，遵循 dd-writing-specs/requirements-writer 的层级原则。

## 反冗余与篇幅治理

每条事实只有一个属主文档；下游章节与下游文档引用 ID，不复制正文：

- AC Then = 判定所需的最小可观察断言 + FR / RULE ID 引用；禁止把 FR 规范要求或 RULE 细则整段搬进 Then。反模式：一条 AC 的 Then 复述对应 RULE 的全部正 / 反例判定条件——同一事实形成双份维护，下游测试用例表还会再复写一遍。
- FR 细节（支持域枚举、判定细则、正反例）已存在 `requirements/` 分片时，FR 正文只保留 SHALL 断言 + 分片引用；分片是细节唯一属主。候选语义索引表（如附录索引）只写一句话摘要，不重复分片正文。
- 版本记录：每版一行摘要语义变化；逐条复审修复细节（H1/M1/L1 修复过程、finding 闭环记录）落 `artifacts/` 的复审记录，不进正文。反模式：每个版本条目写满一整段修复过程，十余版累积上百行。
- 动态 Gate 状态（readiness、上游 Gate 未闭合、"尚未形成"类表述）全文只集中一处并标注"快照"；禁止在定位、风险、交接、版本记录等各章节散布"不授权实施 / 不得宣称 PASS"防御性文案。
- 历史研究台账（unresolved 逐 ID 汇总、旧编号映射等）归档 `artifacts/`，正文只留指针与计数口径。

`artifacts/` 位于阶段文档同目录（`docs/phases/{X}_{阶段名}/artifacts/`），一类内容一文件、逐版追加（如 `review-log.md`、`research-ledger.md`）；正文只引用文件路径与版本号。

完成前自检：扫描 AC Then 是否复述 FR/RULE 细则、版本记录是否每版一行、防御性文案是否只出现一处、追溯矩阵是否在正文手写、台账是否留在正文——任一命中，按本节规则收敛后重写，不修补。

## 审查

审查语义遵循 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md)。

必须检查：

- 覆盖与范围：Roadmap Goal/IN/OUT、Baseline 处置是否完整映射；
- 一致与正确：Constraints、AC 和 Architecture 是否冲突；
- 可验证与可观测：每条 AC 是否有真实可执行证据。

审查遵循 [dd-workflow-runtime/review-gate](../../dd-workflow-runtime/references/review-gate.md)。存在兼容迁移、持久化数据、Public API 或用户可见高风险行为时附加以下检查：

- 兼容迁移：新旧数据转换是否有回滚方案；
- 持久化数据：数据格式变更是否向后兼容；
- Public API：签名变更是否有废弃策略；
- 高风险 UI：关键用户路径是否有真实可见证据（非内部状态/mock）。

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

全部条件通过后，产物状态可标记为 `approved`。Git commit、push 或 PR 属于 Delivery Gate，遵循项目规则和 [dd-git-workflow](../../dd-git-workflow/SKILL.md)。

## 输出

返回：

```yaml
phase_contract:
  path: docs/phases/{X}_{阶段名}/{X}_01_阶段需求与验收.md
  status: approved
blocking_gaps: []
resolved_decisions: []
```

用户决策和会话结束遵循 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md)。
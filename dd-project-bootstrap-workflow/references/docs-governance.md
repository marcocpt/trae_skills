# Docs Governance Reference

仅在创建或校验根目录 `docs.md`、目录、SSOT、同步或归档规则时读取。不要为模式判定、状态恢复或普通 Handoff 预加载本文件。

## 1. 文档定位

根目录 `docs.md` 是项目文档体系入口，只负责：

- 定义根目录与 `docs/` 的目录和命名；
- 规定各类事实的唯一维护位置；
- 规定阶段文档创建顺序和同步规则；
- 提供 Agent 的最小阅读入口。

`docs.md` 不复制 Roadmap 的功能优先级、Architecture 的不变量、Requirements、Design、Test 或 Coding Standards 正文。

发生冲突时按以下权威链处理：

```text
Roadmap
  ↓
Architecture Contract 与 ADR
  ↓
阶段 Requirements / Phase Contract
  ↓
Design
  ↓
Test Matrix
  ↓
Implementation Plan
  ↓
Evidence 与 History
```

下游发现上游缺失或冲突时，先修正上游，不在下游另写一套规则。

## 2. 目标目录

目录和文件按需创建，不提前生成空壳：

```text
.
├── docs.md
├── AGENTS.md
├── {lint 配置}
└── docs/
    ├── planning/
    │   ├── 路线图.md
    │   ├── 功能列表.md
    │   └── 技术调研.md
    ├── architecture/
    │   ├── 全局架构契约.md
    │   ├── ADR索引.md
    │   └── adr/
    │       └── ADR-NNNN-主题.md
    ├── phases/
    │   ├── P{n}_{准备阶段名}/
    │   │   ├── P{n}_01_阶段需求与验收.md
    │   │   ├── P{n}_02_设计文档.md
    │   │   ├── P{n}_03_测试用例表.md
    │   │   ├── P{n}_04_实现计划.md
    │   │   └── artifacts/
    │   └── F{功能编号}_{简短功能名}/
    │       ├── F{n}_01_阶段需求与验收.md
    │       ├── F{n}_02_设计文档.md
    │       ├── F{n}_03_测试用例表.md
    │       ├── F{n}_04_实现计划.md
    │       └── artifacts/
    ├── standards/
    │   ├── CODING_STANDARDS.md
    │   ├── git-commit-message.md
    │   └── {语言或测试规则}.md
    ├── specs/
    │   └── 已实现行为规格.md
    └── historys/
        └── YYYY-MM-DD-{文档名}-{修改摘要或审查记录}.md
```

目录规则：

- `docs.md` 和 `AGENTS.md` 位于仓库根目录；
- lint 配置位于工具可直接读取的位置；
- `P{n}` 表示准备/迁移阶段，不参与功能编号；
- `F{n}` 与 `功能列表.md` 的功能编号一致；
- Brownfield Baseline 使用 `P-1_基线盘点/` 或项目已批准的准备阶段编号；
- `artifacts/` 保存清单、矩阵、快照和证据，不新增产品或架构规则；
- `standards/` 按实际语言和工具链创建，不照搬其他项目；
- `specs/已实现行为规格.md` 只记录已批准、已发布的外部行为；
- `historys/` 是历史输入，不是当前 SSOT。

## 3. 单一事实来源

| 信息 | 唯一维护位置 |
|---|---|
| 阶段目标、边界、依赖、状态和路线级 Gate | `docs/planning/路线图.md` |
| 功能编号、优先级、依赖和交付状态 | `docs/planning/功能列表.md` |
| 文档目录、命名、创建和同步规则 | 根目录 `docs.md` |
| Agent 必读入口、禁止事项和验证命令 | 根目录或适用目录的 `AGENTS.md` |
| 跨阶段架构不变量 | `docs/architecture/全局架构契约.md` |
| 单个架构决策和理由 | `docs/architecture/adr/ADR-NNNN-主题.md` |
| 阶段 Goal、Scope、FR、NFR、Constraints、AC、Exit Gate | 对应 `{X}_01_阶段需求与验收.md` |
| 阶段职责、依赖、数据流、错误和回退 | 对应 `{X}_02_设计文档.md` |
| AC 覆盖、测试类型、状态和证据 | 对应 `{X}_03_测试用例表.md` |
| 文件、任务、命令、提交边界和回滚 | 对应 `{X}_04_实现计划.md` |
| 编码、测试、提交和工具规则 | `docs/standards/` |
| 已发布外部行为 | `docs/specs/已实现行为规格.md` |
| 失效草案和历史输入 | `docs/historys/` |

同一事实不得复制维护。引用上游时使用稳定编号或相对链接。

Roadmap 的 Goal、IN、OUT 和 Exit Gate 定义战略边界。阶段 Requirements 只能在该边界内细化；改变边界必须先改 Roadmap。

## 4. Brownfield 既有文档

Baseline 必须为散落的既有文档记录：

| 已有文档 | 当前负责事实 | 应迁移事实 | 迁移目标 | 状态 |
|---|---|---|---|---|

迁移前以既有文档为来源；迁移时一次性抽离；迁移后停止双写。

## 5. 阶段文档

固定顺序：

```text
{X}_01_阶段需求与验收.md
  ↓
{X}_02_设计文档.md
  ↓
{X}_03_测试用例表.md
  ↓
{X}_04_实现计划.md
  ↓
实现与证据
```

涉及用户可见 UI 时，在 Design 后增加 `{X}_02a_视觉原型.html`；纯基础设施不创建视觉原型。

职责边界：

| 文档 | 回答什么 | 禁止包含 |
|---|---|---|
| Requirements / Phase Contract | 为什么、做什么、边界、AC、Decision Freedom | 类/方法/字段/实现步骤 |
| Design | 谁负责、如何协作、数据流、状态、错误和回退 | 完整实现代码和逐文件任务 |
| Test Matrix | AC 映射、测试类型、状态、环境和证据 | 新需求和未经批准语义 |
| Implementation Plan | 文件、任务、命令、提交和回滚 | 未批准功能和未来抽象 |
| Artifact | 已执行工作的事实证据 | 新需求、阶段状态和架构规则 |

测试状态使用 `COVERED`、`PARTIAL`、`MISSING` 或 `DEFERRED`，并区分 Unit、Characterization、Corpus、Golden、Compatibility、Performance、Fuzz 和 UI 证据。

## 6. 阶段推进

```text
P-1 Baseline（Brownfield 必需）
  ↓
风险触发的 Technical Validation
  ↓
F0 首个 Feature
  ↓
后续 Feature
```

- Technical Validation 只有在未验证假设会改变 Roadmap 或 Architecture 时必需；
- 准备阶段 Exit Gate 通过后才能推进首个 Feature；
- 当前阶段 Requirements 批准后才能实现；
- 当前阶段 Exit Gate 通过后才能启动下一个正式阶段；
- 用户要求提前规划时可创建 Draft，但 Draft 不是编码依据。

Architecture 状态：

```text
hypothesis → provisional → approved-baseline → frozen
```

Bootstrap 只要求足以约束首个 Feature 的 `approved-baseline`。`frozen` 需要首个真实实现证据。

## 7. Standards

采用“短工具入口 → 权威规范 → 自动验证”分层：

- `CODING_STANDARDS.md`：入口和跨主题原则；
- `git-commit-message.md`：提交格式唯一来源；
- 语言规则：命名、错误、并发、框架约定；
- 测试规则：平台矩阵、测试类型和证据纪律；
- 工具专用规则只引用权威文件，不复制正文。

质量基线由 Greenfield/Brownfield policy 决定，详见 `brownfield-policy.md`。

## 8. 元数据、链接和同步

Markdown 文档标题后使用：

```text
> 最后更新：YYYY-MM-DD | 版本：vX.Y
> 文档状态：草案 / 审核中 / 已批准 / 已实现 / 已取代 / 归档
```

- 仓库内使用相对链接；
- 不创建指向不存在文件的 Markdown 链接；
- 当前权威文件名不加 `final`、`new`、`最新版` 或版本号；
- Mermaid 节点包含空格、括号或标点时使用引号；
- 图表必须有文字说明。

同步检查：

| 变更来源 | 检查目标 |
|---|---|
| Roadmap 边界或 Gate | 当前阶段 Requirements 和链接 |
| Requirements / AC | Design、Test Matrix、Plan |
| Design 职责或数据流 | Test Matrix、Plan、Architecture、ADR |
| UI 可见行为 | Prototype、Test Matrix、已实现行为规格 |
| 测试状态 | Test Matrix 和 artifacts |
| 兼容处置 | Phase Contract、Test Matrix、风险和回退 |
| Architecture 不变量 | ADR、Roadmap 和受影响 Design |

修改后检查 SSOT、上下游矛盾、链接、版本、测试证据以及是否把 legacy defect 写成批准契约。

## 9. History、ADR 与 Git

| 机制 | 记录内容 |
|---|---|
| 文档版本记录 | 当前文档各版本改了什么 |
| ADR | 为什么选择或改变架构决定 |
| Git commit | 哪些文件在何时变化 |
| `historys/` | 已失效但仍需追溯的完整输入 |

不要为每个 commit 再复制一份 History。Git 分支、提交、merge/rebase、push 和 PR 策略遵循项目规则与 `dd-git-workflow`，不在 docs governance 写死。

## 10. Agent 阅读策略

Always read：

1. 适用的 `AGENTS.md`；
2. Roadmap；
3. 当前 Phase Contract / Requirements。

Read when relevant：

- Architecture 与相关 ADR；
- 当前任务涉及的 Standards 章节；
- 当前 Design、Test Matrix、Plan；
- 与当前判断直接相关的 artifact。

Do not preload：

- `historys/`；
- 无关 Phase；
- 旧 artifact；
- 整个 `docs/`；
- 与当前节点无关的 reference。

上游缺失或未批准时停止对应实现；历史归档和单个现状测试不能覆盖当前批准文档。

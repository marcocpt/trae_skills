---
name: dd-writing-specs
description: 当需要为新功能／重大重构／API 迁移编写规格时使用，在实现代码或实现计划之前触发；默认产出最小任务包（目标/范围、必要设计决定、验证条件、任务安排，含人话看板与 agent 交接入口），用户或项目明确要求完整规格套件或单独编写／修订 Requirements、Design、Visual Prototype、Test Matrix 时走对应模式。
---

# 编写规格文档

## 目标

默认用**一个持久任务入口**完成规格：入口任务专属、仓库内持久、离线可读（路径选择见[持久任务入口](#持久任务入口)），包含目标/范围、必要设计决定、验证条件、任务安排，以及人话看板（任务、状态、完成条件/实际结果、阻塞）和 agent 交接信息（目标、边界、代码位置/worktree、关键决定、验证证据、下一步、授权边界）。看板与交接在同一文件，不新建第二套状态 schema。

资料以供 AI 接手、检索和核验为目的，不要求用户逐篇阅读；只记录无法从既有合同、代码和测试充分恢复的信息，已有事实用引用。任务结案与历史问答按 [artifact-lifecycle](../dd-workflow-runtime/references/artifact-lifecycle.md) §3.6、§3.7；本 writer 只交还规格时保持接手状态，不宣称实现完成。

用户或项目明确要求完整套件时，进入 Full 模式，按 Stage Graph 逐篇产出四件套；确认默认整包一次完成，仅当用户或项目明确要求逐篇确认时才逐篇。用户明确只要某一篇时，用单文档模式。

内容批准不等于 Git 授权；交付按已明确的 `delivery_policy` 单独执行。长流程遵循 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)；规范事实、派生视图和证据遵循 [artifact-contract](../dd-workflow-runtime/references/artifact-contract.md)。默认只加载本文件，进入具体步骤时再读 reference，以减少 token 而不降低 Gate。

## 适用边界

适用：新功能、重大重构、API 迁移、设计驱动变更。

不适用：

- Bug 修复：用 [dd-bug-fix-workflow](../dd-bug-fix-workflow/SKILL.md)；
- 已批准文档的纯机械格式修改：可直接编辑，不必启动规格流程；
- 已批准规格的机械微调：可直接编辑并记录版本/内容指纹；
- 纯只读审查。

## 模式选择

| 模式 | 何时选择 | 产出 |
|---|---|---|
| Lite（默认） | 默认；除非落入 Full 条件 | 持久任务入口一个文件（承载最小任务包） |
| Full | ① 用户明确要求完整套件；② 项目 `docs.md` 或正式项目约束硬性要求逐篇确认或套件；③ 各篇都存在明确独立消费者且确需整套文档；仅单一合同需求进入单文档模式 | Requirements → Design → Visual（UI）→ Test Matrix |
| 单文档 | 用户明确只要求某一篇（`requested_entry`） | 目标文档，沿用 Full 中该篇的 Gate |

风险（公共 API、持久化、并发、兼容性、UI、多阶段联动等）**不改变文档组织档位**：命中风险时按 [review-gate](../dd-workflow-runtime/references/review-gate.md) 加强审查/验证/tracer，不以文件数量代理风险控制。Full 触发条件③仅限"实际独立消费者"（下游 Skill、其他工作流、外部团队或长期架构文档作为稳定合同独立引用），不因阶段数或改动规模自动成立。

选择 Full 条件②时遵循项目规则，并按 [Preflight 与恢复](#preflight-与恢复) 的项目规则冲突条款显式报告，不静默绕过，也不宣称本 skill 的改变已让项目规则全局失效。

## 持久任务入口

遵循 [共享持久任务入口约定](../dd-workflow-runtime/references/state.md#持久任务入口)：复用同一任务专属入口，不给每个skill另建看板。下文的入口均指该既有入口。

## 调用所有权

直接响应用户：

```yaml
workflow_type: writing-specs
invocation_mode: standalone
host: auto
requested_entry: rules | requirements | design | visual | test-matrix
state_file: $(git rev-parse --git-dir)/writing-specs-state.json
delivery_policy: project-rules
```

由 Feature workflow 调用时：

```yaml
invocation_mode: child
upstream_requirements_seed: <path-or-state-key>
worktree_path: <inherited>
resolved_decisions: []
delivery_policy: <inherited>
```

文档组织采用上文模式选择，不新增运行时mode字段。child默认复用父任务包；调用方明确要求完整套件时才进入Full，不因child身份自动触发套件。

`child` 复用上游 worktree、需求事实和交付边界，完成后返回规格路径、批准版本／内容指纹、Gate 与适用的 Delivery 证据，不执行最终 Host Close。原子 writer 和 Git/CI 能力使用 `helper`。

## Preflight 与恢复

1. 读取适用规则、`docs.md`、功能列表和最近规格；规则缺失时先搜索确认，再记录默认来源，不反复 ASK 已知缺失；
2. 定位持久任务入口（`child` 复用父入口；`standalone` 复用项目既有入口，无则创建任务专属路径，规则见[持久任务入口](#持久任务入口)）；缺失且可从仓库中的文档、review、批准证据和适用的 Commit 重建时重建，不以聊天记忆为唯一依据；
3. **从代码和实际运行证据核实当前实现状态**：旧文档、旧测试报告、旧状态记录仅作线索；证据须与当前输入/版本匹配，不能照旧文档覆盖当前文件，不能把文档 PASS、勾选或旧报告当实测，不能把现有 bug 当需求；需求/验收条件保留目标正确性；
4. 核对入口中的目标、边界、代码位置/worktree、关键决定、验证证据、下一步和授权边界；入口与代码证据冲突时以代码证据为准并记录修正；
5. Gap Scan 定位第一个未满足 Gate；
6. 首次写文件前确定工作环境；`child` 继承父工作流环境，不重复询问；
7. 已确认内容不重写、不重问；未确认下游产物不能作为有效基线。

入口至少记录：

- feature id/name、mode、worktree 或代码位置；
- 目标与范围（IN/OUT）；
- 关键设计决定（决策、理由、代价）及批准状态；
- 验证条件（AC）与每条的任务/测试/证据映射；
- 任务看板：任务、状态、完成条件、实际结果、阻塞；
- 验证证据（命令、退出码、产物路径，绑定输入版本）；
- `delivery_policy`、Git 授权状态与实际 Delivery 证据；
- `next_safe_action`；
- 可恢复链接：runtime 状态文件路径、tracking Issue、规格/计划产物路径。

运行时通用状态字段仍由 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md) 状态文件属主；入口文件只承载人话看板与交接摘要，不发明第二套 JSON 字段或账本。每次 ASK 结果、写入、确认和已授权 Delivery 动作后原子持久化。

**项目规则冲突**：项目 `docs.md` 或正式项目约束与本 skill 默认（最小任务包、按决定确认）冲突时，遵循项目规则（现有正式项目约束不被本 skill 单方面覆盖），同时显式向用户报告冲突位置、影响和可选处理，由用户裁决；不得静默绕过，也不得宣称修改本 skill 已让项目规则全局失效。

## Lite 流程（默认）

按顺序执行，每步完成后更新入口并原子持久化：

1. **清点事实**：从代码、文档、批准证据恢复已有事实。目标、范围、关键决定已明确且已批准的，直接复用，不复述、不重复确认。
2. **只清点未解决项**：列出未解决项——产品决策、范围变化、高风险、授权边界。全部已明确则不问；存在未解决且影响执行的项才 ASK，一次一个结构化问题，带推荐答案和理由；能从代码/文档回答的先探索。
3. **写最小任务包**：目标/范围（IN/OUT）、必要设计决定（决策、理由、代价，不写实现细节）、验证条件（AC 用 Given/When/Then，可观察、可测量）、任务安排（每条任务对应验证方式）。先落盘 draft。
4. **自检**：AC 可观察可测量、无 TODO/占位符；需求事实不含代码符号；范围无越界；每个 AC 有任务/测试/证据映射；与项目规则和既有批准范围一致。发现问题立即修复。
5. **确认**：展示自检结论；仅当存在未解决决策（产品决策、范围变化、高风险、授权边界）时一次 ASK：① 确认并进入执行；② 修改任务包并重新确认；③ 回到上游需求澄清。无未解决决策且已有效授权时，自检通过即继续，不围绕文件数量重复确认；已明确目标与授权范围内的机械同步/整理不重复确认；未批准语义不因合并进任务包而变为已批准。
6. **交还执行**：任务包（含可执行验收条件：命令、测试或人工步骤）完成后交还调用方——`standalone` 交还用户及其后续执行方，`child` 返回 Feature workflow；实现与验证由调用方或 Feature/Bug 负责，**本 writer 不执行生产实现**，也不把文档自检结论当作实现已通过的证据。
7. **更新入口并交付**：交还时把入口更新为可接手状态（看板、交接摘要、`next_safe_action` 指向下一步执行方）；执行方回填的实际结果与验证证据同样更新入口，不另建进度镜像；Git 与外部动作按 `delivery_policy` 和既有授权单独判定，内容批准不授权 Git。

**拆独立规格的条件**：出现明确消费者（如下游团队、对外合同）或独立稳定合同，或用户/项目明确要求时，从任务包拆出 Requirements/Design/Visual/Test Matrix 单篇；单篇沿用 Full 中该篇的 Gate；未拆事实仍以任务包为属主，不复制成第二份；拆文件不改变批准范围，也不自动触发逐份同步。**高风险本身不构成拆份条件**：风险通过 [review-gate](../dd-workflow-runtime/references/review-gate.md) 加强审查/验证/tracer 承接，不以增加文档数量代理风险控制。

项目允许合并的最小长期合同时，只提取任务包中仍有效且需要长期独立引用的约定，沿用 Lite 自检与确认，并按 [来源与批准合同](../dd-workflow-runtime/references/artifact-source-and-packet.md) 绑定原文与批准；不新增批准字段或 Gate。消费方按同一来源读取和验证，速通欠账也引用该已批准来源，不因文件名不同要求再补一套规格。

## Full 模式（用户或项目明确要求时）

保留完整产出路径，按依赖顺序逐篇推进（不并行编写）：

```text
Rules & References
        ↓
Grill / Upstream Seed Check
        ↓
Requirements → Design → Visual (UI) → Test Matrix
        ↓
整包自检 → 整包确认（或用户/项目明确要求时逐篇确认）→ 持久化批准版本/内容指纹
        ↓
Delivery（按策略）→ Cleanup → Return to parent / Host Close
```

<HARD-GATE>
严格按依赖顺序产出，不并行编写不同文档。确认默认为**整包一次**：全套写完并完成三方向自检后，展示自检结论与遗留建议，一次 ASK 确认整个规格包；仅当**用户或项目明确要求逐篇确认**时，每篇文档"写 → 自检 → 用户确认 → 持久化批准版本／内容指纹"后才进入下一篇（`逐篇确认`不因档位默认成立，也不因项目规则被本 skill 默认覆盖）。已有效授权且无未解决决策时自检通过即继续，不因会话性表述重复 ASK；自检结论必须完整展示并持久化，该 Gate 不因减少 ASK 次数而取消。Git Stage／Commit／Push 只按已明确的 `delivery_policy` 和授权执行；同一 worktree 内不得因 Git 未被要求或被明确禁止而撤销内容批准或重复询问。禁止并行编写不同文档，禁止未完整展示自检结论即确认，禁止跨 worktree 消费未交付状态。
</HARD-GATE>

- **Stage 0 规则与参考**：读项目 `docs.md`、Coding/Test rules、章节/命名/路径/版本/同步规则、功能列表编号与优先级、最近 1–3 份规格；写 `.step0-rules-summary.md` 并持久化。详细清单见 [intake-and-requirements.md](references/intake-and-requirements.md)。
- **Stage 1 Grill 或 Seed Check**：`standalone` 一次只问一个问题，覆盖目标、范围、流程、失败路径、数据/接口、兼容、AC、阶段、UI 证据、编号；能从代码/文档回答的先探索。`child` 验证上游 Requirements Seed，一致则记录复用，不重复 grill，冲突或 blocker 才 ASK。
- **Stage 2 Requirements**：WHAT 产品合同；使用项目章节规则，否则默认 12 章节；FR、NFR、AC、Scope、Out of Scope、Terminology、Decision Freedom 完整；无代码符号、无占位符。见 [requirements-writer.md](references/requirements-writer.md)。
- **Stage 3 Design**：WHO/结构的架构契约；引用 FR 不复制 Requirements；模块职责/数据流/状态/协作/决策/NFR 映射/风险完整；无代码符号。默认 10 章节。见 [design-writer.md](references/design-writer.md)。
- **Stage 4 Visual**：只有涉及 UI 时执行；与已确认 Requirements/Design 一致；非 UI 明确记录 `not-applicable`，不生成空壳。
- **Stage 5 Test Matrix**：验证合同，只登记 Requirements/Design 没有的新信息；矩阵行引用 AC 编号不复写。见 [downstream-documents.md](references/downstream-documents.md)。

## 单文档模式

用户明确只要求 Requirements、Design、Visual 或 Test Matrix 时，设置 `requested_entry` 到对应 Stage。仍必须做该文档所需的上游 Gap Scan：上游事实已批准则直接复用；缺失且会影响正确性时只补 blocker，不强制生成用户未要求的整套文档。完成目标文档的自检/确认/交付后即可退出，不自动继续下游。

## 自检与确认

通用 A/B/C 名称和语义只取自 [review-gate](../dd-workflow-runtime/references/review-gate.md)；本 writer 只补 Requirements／Design／Visual／Test Matrix 特有检查，见 [review-and-delivery.md](references/review-and-delivery.md)。自检发现的问题立即修复后再提交确认。确认前展示自检结论和遗留建议。

**确认只围绕未解决或变化的实质决定**（产品决策、范围变化、高风险、授权边界），不围绕文件数量：已有效授权且语义不变时自检通过即继续；无未解决决策不重复 ASK；用户或项目明确要求逐篇确认时按逐篇执行。即使用户说"直接提交"等授权性表述，也先完成并持久化完整自检结论（该 Gate 不因授权性表述取消），自检通过且无未解决决策时直接继续——不因会话性结束语重复获取选择。未批准语义不因合并进任务包或整包确认而变为已批准。

## Cleanup、归档与 Exit Gate

所有内容确认并持久化后：

1. 删除本技能创建的 `.step0/.step1` 临时笔记；不删除上游 Feature 创建的 seed；**不删除持久任务入口**（跨 app/会话恢复依靠它）；
2. 已完成的历史计划/调查/草稿/评审包不持续维护为最新状态，可归档；归档前保全仍有效合同与唯一证据（ADR、当前 Gate evidence、唯一可复现证据），处理引用，不批量删除；归档前后都不依赖聊天记忆恢复；
3. 验证文档版本、内容指纹、批准依据、review、summary、同步关系和适用的 Delivery 证据；
4. 确认 blocking issue 为零；
5. 原子持久化最终状态。

版本、内容指纹和批准依据负责内容追溯，它们不授权 Git；Git 动作的授权边界遵循 [dd-workflow-runtime 的 Workflow Gate 与 Delivery Gate](../dd-workflow-runtime/SKILL.md)（未要求记 `not-required`，明确禁止记 `not-authorized`）。本工作流不得擅自 reset、force push 或破坏父工作流提交。

`child` 将结果返回 Feature workflow；`standalone` 进入 Host Close。

## Host Close

仅 `invocation_mode=standalone` 执行：先持久化 `status=completed`（必要时写 Completion Receipt），再按 [dd-workflow-runtime 宿主结束合同](../dd-workflow-runtime/SKILL.md) 收尾——Trae 结构化 ASK 只提供 `结束本次任务 / 还有其他任务`（null 重问），Codex 正常交付最终摘要。

## 红线

- 未读规则/参考就写规格；
- 目标或关键决策未明确就写任务包或四件套（能从代码/文档恢复的除外）；
- 一次问多个问题；目标已明确仍复述并重复确认；已有效授权且无未解决决策时仍重复 ASK；
- 把文档 PASS、勾选、旧测试报告当实测；把现有 bug 当需求；
- 并行写多篇，或未完整展示自检结论即批量确认；
- 未完整展示自检结论就确认；
- Requirements/Design 违反文档层级 P0（写入代码符号）；
- Full 模式未完成整包自检与确认（或用户/项目明确要求的逐篇确认）就进入下游；
- writer 自行执行生产实现或把文档自检结论当作实现已通过的证据；
- 把内容批准解释成 Git／外部动作授权，或因用户已禁止 Git 而重复询问；
- 未批准语义因合并文件变成已批准；
- 把风险或改动规模当文档数量代理（用增加文件代替加强审查/验证/tracer）；
- 项目硬性要求套件/逐篇确认时静默改用轻量默认，或宣称本 skill 已让项目规则失效；
- 批量删除历史材料，或删除、损坏唯一证据与仍有效合同；
- child 自行 Host Close；
- Trae 完成后直接结束。

## 按需读取

- 规则来源、Grill、Lite 任务包写法、Requirements Gate：[references/intake-and-requirements.md](references/intake-and-requirements.md)
- Requirements writer：[references/requirements-writer.md](references/requirements-writer.md)
- Design writer：[references/design-writer.md](references/design-writer.md)
- Design、Visual、Test Matrix 汇总与同步：[references/downstream-documents.md](references/downstream-documents.md)
- 自检、确认、Delivery、恢复与补救：[references/review-and-delivery.md](references/review-and-delivery.md)

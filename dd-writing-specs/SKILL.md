---
name: dd-writing-specs
description: 当需要编写新功能/重大重构/API 迁移的完整规格套件，或单独编写/修订 Requirements、Design、Visual Prototype、Test Matrix 时使用；在实现代码或实现计划之前触发。
---

# 编写规格文档套件

## 目标

先读规则和 grill，再按"需求 → 设计 → 视觉原型（UI）→ 测试用例表"逐篇完成。每篇都经过用户确认并记录版本／内容指纹；Git 交付按已明确的策略单独执行，不能把内容批准当作 Git 授权。

长流程遵循 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)；规范事实、派生视图和证据遵循 [artifact-contract](../dd-workflow-runtime/references/artifact-contract.md)。默认只加载本文件，进入具体 Stage 时再读 reference，以减少 token 而不降低 Gate。

## 适用边界

适用：新功能、重大重构、API 迁移、设计驱动变更。

不适用：

- Bug 修复：用 [dd-bug-fix-workflow](../dd-bug-fix-workflow/SKILL.md)；
- 已批准文档的纯机械格式修改：可直接编辑，不必启动完整套件；
- 已批准套件的机械微调；
- 纯只读审查。

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

`child` 复用上游 worktree、需求事实和交付边界，完成后返回规格路径、批准版本／内容指纹、Gate 与适用的 Delivery 证据，不执行最终 Host Close。原子 writer 和 Git/CI 能力使用 `helper`。


### 单文档模式

用户明确只要求 Requirements、Design、Visual 或 Test Matrix 时，设置 `requested_entry` 到对应 Stage。仍必须做该文档所需的上游 Gap Scan：上游事实已批准则直接复用；缺失且会影响正确性时只补 blocker，不强制生成用户未要求的整套文档。完成目标文档的自检/确认/交付后即可退出，不自动继续下游。

## Preflight 与恢复

1. 读取适用规则、`docs.md`、功能列表和最近规格；
2. 恢复状态；状态缺失时从临时笔记、文档、review、批准证据和适用的 Commit 重建；
3. 验证 worktree、文档顺序、已确认版本及内容指纹；
4. Gap Scan 定位第一个未满足 Gate；
5. 首次写文件前确定工作环境；`child` 继承父工作流环境，不重复询问；
6. 已确认文档不重写、不重问；未确认下游产物不能作为有效基线。

状态至少记录：

- feature id/name、mode、worktree；
- rules/requirements seed；
- 当前文档与版本；
- 已完成 Stage、文档/review/summary、批准版本／内容指纹；
- `delivery_policy`、Git 授权状态与实际 Delivery 证据；
- 用户确认与 blocking issue；
- `next_safe_action`。

每次 ASK 结果、文档写入、review、确认和已授权 Delivery 动作后原子持久化。

## Stage Graph

```text
Rules & References
        ↓
Grill / Upstream Seed Check
        ↓
Requirements → Confirm → Persist
        ↓
Design       → Confirm → Persist
        ↓
Visual (UI)  → Confirm → Persist
        ↓
Test Matrix  → Confirm → Persist
        ↓
Delivery（按策略）→ Cleanup → Return to parent / Host Close
```

<HARD-GATE>
严格按依赖推进。每篇文档必须"写 → 自检 → 用户确认 → 持久化批准版本／内容指纹"后才能进入下一篇。Git Stage／Commit／Push 只按已明确的 `delivery_policy` 和授权执行；同一 worktree 内不得因 Git 未被要求或被明确禁止而撤销内容批准或重复询问。禁止并行编写不同文档、批量确认，禁止跨 worktree 消费未交付状态。
</HARD-GATE>

## Stage 0：规则与参考

读取并记录：

- 项目 `docs.md`、Coding/Test rules；
- 章节、命名、路径、版本、图表和同步规则；
- app 功能列表中的编号、优先级、相关功能；
- 最近 1–3 份规格的结构和粒度。

写 `.step0-rules-summary.md` 并持久化；是否 Git 交付由 `delivery_policy` 决定。缺文件时先搜索；确实不存在则记录默认来源或 ASK 唯一 blocker。详细清单见 [intake-and-requirements.md](references/intake-and-requirements.md)。

## Stage 1：Grill 或 Seed Check

`standalone`：一次只问一个问题，覆盖目标、范围、流程、失败路径、数据/接口、兼容、AC、阶段、UI 证据、编号。

`child`：优先验证上游 Requirements Seed；一致则记录复用，不重复 grill。冲突或 blocker 才 ASK。

确认后写 `.step1-requirements-summary.md` 或 `.step1-requirements-confirmed.md`，记录确认依据并按交付策略处理。

## Stage 2：Requirements

读取 [requirements-writer.md](references/requirements-writer.md)。Requirements 是 WHAT 的产品合同：

- 使用项目章节规则，否则默认 12 章节；
- FR、NFR、AC、Scope、Out of Scope、Terminology、Decision Freedom 完整；
- 不含类名、方法、字段、枚举、框架 API、并发原语或文件路径；
- 无 TODO/TBD/占位符。

写入后先落盘 draft 并完成自检，再进入内容确认；Git 交付是独立 Gate。完整写作与检查见 [intake-and-requirements.md](references/intake-and-requirements.md)。

## Stage 3：Design

读取 [design-writer.md](references/design-writer.md)。Design 是 WHO/结构的架构合同：

- 引用 FR，不复制 Requirements；
- 模块负责/不负责、数据流、状态、协作、决策、NFR、FR 映射、风险完整；
- 不含代码符号、完整代码、AC 或测试策略。

详细边界见 [downstream-documents.md](references/downstream-documents.md)。

## Stage 4：Visual Prototype

只有涉及 UI 时执行。原型必须与已确认的 Requirements/Design 一致，展示关键状态、错误和边界，并包含版本信息。非 UI 明确记录 `not-applicable`，不生成空壳。

## Stage 5：Test Matrix

测试用例表是验证合同，只登记 Requirements / Design 没有的新信息：

- 每个 FR 至少映射一个 Test ID / 用例，引用 AC 编号；不复写 Given/When/Then（唯一属主是 AC，多用例只写差异化断言）；
- 登记 Population 分母与 item registry（紧凑记法，不机械展开）、oracle、数值 policy、Evidence schema；
- 追溯矩阵不在正文手写，由 trace_map 或生成产物承载；
- 按 artifact-contract 标记现有覆盖；
- UI AC 有真实可见证据；
- 头部记录所基于的 Requirements/Design 版本。

测试策略和 UI 可观测性属于测试用例表，不回填 Design。反冗余细则见 [downstream-documents.md](references/downstream-documents.md)。

## 自检与确认

通用 A/B/C 名称和语义只取自 [review-gate](../dd-workflow-runtime/references/review-gate.md)；本 writer 只补 Requirements／Design／Visual／Test Matrix 特有检查，见 [review-and-delivery.md](references/review-and-delivery.md)。自检发现的问题立即修复后再提交内容确认。确认前展示自检结论和遗留建议，然后一次 ASK：

1. 确认并进入下一篇；
2. 修改本篇并重新确认；
3. 回到上游文档/需求澄清。

最后一篇也必须确认。详细模板、Delivery 和恢复规则见 [review-and-delivery.md](references/review-and-delivery.md)。

## Cleanup 与 Exit Gate

所有文档确认并持久化后：

1. 删除本技能创建的 `.step0/.step1` 临时笔记；Git 处理仍遵循已明确交付策略；
2. 不删除上游 Feature 创建的 seed；
3. 验证文档版本、内容指纹、批准依据、review、summary、同步关系和适用的 Delivery 证据；
4. 确认 blocking issue 为零；
5. 原子持久化最终状态。

版本、内容指纹和批准依据负责内容追溯，它们不授权 Git；Git 动作的授权边界遵循 [dd-workflow-runtime 的 Workflow Gate 与 Delivery Gate](../dd-workflow-runtime/SKILL.md)（未要求记 `not-required`，明确禁止记 `not-authorized`）。本工作流不得擅自 reset、force push 或破坏父工作流提交。

`child` 将结果返回 Feature workflow；`standalone` 进入 Host Close。

## Host Close

仅 `invocation_mode=standalone` 执行：先持久化 `status=completed`（必要时写 Completion Receipt），再按 [dd-workflow-runtime 宿主结束合同](../dd-workflow-runtime/SKILL.md) 收尾——Trae 结构化 ASK 只提供 `结束本次任务 / 还有其他任务`（null 重问），Codex 正常交付最终摘要。

## 红线

- 未读规则/参考就 grill 或写文档；
- 未 grill/Seed Check 就写 Requirements；
- 一次问多个 grill 问题；
- 并行写多篇或批量确认；
- 未完整展示自检结论就确认；
- Requirements/Design 违反文档层级 P0；
- 上一步未确认或批准版本／内容指纹未持久化就进入下游；
- 把内容批准解释成 Git／外部动作授权，或因用户已禁止 Git 而重复询问；
- child 自行 Host Close；
- Trae 完成后直接结束。

## 按需读取

- 规则、grill、Requirements：[references/intake-and-requirements.md](references/intake-and-requirements.md)
- Requirements writer：[references/requirements-writer.md](references/requirements-writer.md)
- Design writer：[references/design-writer.md](references/design-writer.md)
- Design、Visual、Test Matrix 汇总：[references/downstream-documents.md](references/downstream-documents.md)
- 自检、确认、Delivery、恢复与补救：[references/review-and-delivery.md](references/review-and-delivery.md)

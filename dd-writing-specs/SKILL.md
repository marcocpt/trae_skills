---
name: dd-writing-specs
description: 编写新功能、重大重构或 API 迁移的整套规格文档（需求文档、设计文档、视觉原型、测试用例表）时使用，在写实现代码或计划之前。触发词：设计规范、规格套件、design spec、写规格、规格文档、需求文档+设计文档。
---

# 编写规格文档套件

## 目标

先读规则和 grill，再按"需求 → 设计 → 视觉原型（UI）→ 测试用例表"逐篇完成。每篇都经过用户确认和原子提交，不能批量生成后一次确认。

长流程遵循 [dd-shared-workflow-runtime](../dd-shared-workflow-runtime/SKILL.md)；默认只加载本文件，进入具体 Stage 时再读 reference，以减少 token 而不降低 Gate。

## 适用边界

适用：新功能、重大重构、API 迁移、设计驱动变更。

不适用：

- Bug 修复：用 [dd-bug-fix-workflow](../dd-bug-fix-workflow/SKILL.md)；
- 单篇 Requirements/Design：用对应 writer；
- 已批准套件的机械微调；
- 纯只读审查。

## 调用所有权

直接响应用户：

```yaml
workflow_type: writing-specs
invocation_mode: standalone
host: auto
requested_entry: rules
state_file: $(git rev-parse --git-dir)/writing-specs-state.json
```

由 Feature workflow 调用时：

```yaml
invocation_mode: child
upstream_requirements_seed: <path-or-state-key>
worktree_path: <inherited>
resolved_decisions: []
```

`child` 复用上游 worktree 和需求事实，完成后返回规格路径、Commit 和 Gate 证据，不执行最终 Host Close。原子 writer 和 Git/CI 能力使用 `helper`。

## Preflight 与恢复

1. 读取适用规则、`docs.md`、功能列表和最近规格；
2. 恢复状态；状态缺失时从临时笔记、文档、review、Commit 重建；
3. 验证 worktree、文档顺序和已确认版本；
4. Gap Scan 定位第一个未满足 Gate；
5. 首次写文件前确定工作环境；`child` 继承父工作流环境，不重复询问；
6. 已确认文档不重写、不重问；未确认下游产物不能作为有效基线。

状态至少记录：

- feature id/name、mode、worktree；
- rules/requirements seed；
- 当前文档与版本；
- 已完成 Stage、文档/review/summary/Commit；
- 用户确认与 blocking issue；
- `next_safe_action`。

每次 ASK 结果、文档写入、review、确认和 Commit 后原子持久化。

## Stage Graph

```text
Rules & References
        ↓
Grill / Upstream Seed Check
        ↓
Requirements → Confirm → Commit
        ↓
Design       → Confirm → Commit
        ↓
Visual (UI)  → Confirm → Commit
        ↓
Test Matrix  → Confirm → Commit
        ↓
Cleanup → Return to parent / Host Close
```

<HARD-GATE>
严格按依赖推进。每篇文档必须"写 → 自检 → 用户确认 → 提交"，其 Commit 可追溯后才能进入下一篇。禁止并行编写不同文档、批量确认、跨阶段累积未提交变更。
</HARD-GATE>

## Stage 0：规则与参考

读取并记录：

- 项目 `docs.md`、Coding/Test rules；
- 章节、命名、路径、版本、图表和同步规则；
- app 功能列表中的编号、优先级、相关功能；
- 最近 1–3 份规格的结构和粒度。

写 `.step0-rules-summary.md` 并提交。缺文件时先搜索；确实不存在则记录默认来源或 ASK 唯一 blocker。详细清单见 [intake-and-requirements.md](references/intake-and-requirements.md)。

## Stage 1：Grill 或 Seed Check

`standalone`：一次只问一个问题，覆盖目标、范围、流程、失败路径、数据/接口、兼容、AC、阶段、UI 证据、编号。

`child`：优先验证上游 Requirements Seed；一致则记录复用，不重复 grill。冲突或 blocker 才 ASK。

确认后写 `.step1-requirements-summary.md` 或 `.step1-requirements-confirmed.md` 并提交。

## Stage 2：Requirements

以 `invocation_mode=helper` 调 [dd-write-requirements](../dd-write-requirements/SKILL.md)。Requirements 是 WHAT 的产品合同：

- 使用项目章节规则，否则默认 12 章节；
- FR、NFR、AC、Scope、Out of Scope、Terminology、Decision Freedom 完整；
- 不含类名、方法、字段、枚举、框架 API、并发原语或文件路径；
- 无 TODO/TBD/占位符。

写入后先落盘 draft 并完成自检，再进入确认与提交。完整写作与检查见 [intake-and-requirements.md](references/intake-and-requirements.md)。

## Stage 3：Design

以 `invocation_mode=helper` 调 [dd-write-design](../dd-write-design/SKILL.md)。Design 是 WHO/结构的架构合同：

- 引用 FR，不复制 Requirements；
- 模块负责/不负责、数据流、状态、协作、决策、NFR、FR 映射、风险完整；
- 不含代码符号、完整代码、AC 或测试策略。

详细边界见 [downstream-documents.md](references/downstream-documents.md)。

## Stage 4：Visual Prototype

只有涉及 UI 时执行。原型必须与已确认的 Requirements/Design 一致，展示关键状态、错误和边界，并包含版本信息。非 UI 明确记录 `not-applicable`，不生成空壳。

## Stage 5：Test Matrix

测试用例表：

- 每个 FR 至少映射一个 AC/用例；
- Given/When/Then 和证据可判定；
- 标记现有覆盖 `COVERED / PARTIAL / MISSING / DEFERRED`；
- UI AC 有真实可见证据；
- 头部记录所基于的 Requirements/Design 版本。

测试策略和 UI 可观测性属于测试用例表，不回填 Design。

## 自检与确认

写作时同步完成 A/B/C 三方向自检，不单设审查轮次：

| 方向 | 关注点 |
|---|---|
| A | 完整性、一致性、项目规则与文档层级 P0 |
| B | 范围、YAGNI、可设计/架构质量 |
| C | 可验证性、FR/AC 映射、UI 可观测性 |

自检发现的问题立即修复后再提交确认。确认前展示自检结论和遗留建议，然后一次 ASK：

1. 确认并进入下一篇；
2. 修改本篇并重新确认；
3. 回到上游文档/需求澄清。

最后一篇也必须确认。详细模板、Commit 和恢复规则见 [review-and-delivery.md](references/review-and-delivery.md)。

## Cleanup 与 Exit Gate

所有文档确认和提交后：

1. 删除本技能创建的 `.step0/.step1` 临时笔记并提交；
2. 不删除上游 Feature 创建的 seed；
3. 验证文档版本、review、summary、Commit 和同步关系；
4. 确认 blocking issue 为零；
5. 原子持久化最终状态。

默认保留逐步 Commit 以保证恢复和追溯。只有用户明确要求且项目规则允许时，才把历史整理作为独立 Delivery 任务；不得在本工作流中擅自 reset、force push 或破坏父工作流提交。

`child` 将结果返回 Feature workflow；`standalone` 进入 Host Close。

## Host Close

仅 `invocation_mode=standalone` 执行。

Trae：

1. ASK 前先持久化 `status=completed`，必要时写 Completion Receipt；
2. 禁止直接结束；
3. 结构化 ASK 只提供 `结束本次任务` / `还有其他任务`；
4. null 重问；“还有其他任务”新建 workflow；“结束本次任务”后输出最终摘要。

Codex：正常交付最终摘要，除非用户或项目规则要求额外确认。

## 红线

- 未读规则/参考就 grill 或写文档；
- 未 grill/Seed Check 就写 Requirements；
- 一次问多个 grill 问题；
- 并行写多篇或批量确认；
- 未完整展示自检结论就确认；
- Requirements/Design 违反文档层级 P0；
- 上一步未确认、未提交就进入下游；
- child 自行 Host Close；
- Trae 完成后直接结束。

## 按需读取

- 规则、grill、Requirements：[references/intake-and-requirements.md](references/intake-and-requirements.md)
- Design、Visual、Test Matrix：[references/downstream-documents.md](references/downstream-documents.md)
- 自检、确认、提交、恢复与补救：[references/review-and-delivery.md](references/review-and-delivery.md)

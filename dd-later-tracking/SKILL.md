---
name: dd-later-tracking
description: 用户延后工作时使用（"稍后/以后/回头/晚点/先跳过/先不做/下个版本/这次先不弄"），或调试/审核中出现不属于当前任务的范围蔓延项时使用。也适用于用户要求回顾延后事项，或发现之前记录的 LATER 项已被解决。
---

# dd-later-tracking

## 概述

把跨会话的延后事项持久化到项目根目录的 `docs/AI/later/` 目录，**一项一文件**，不是会话级 TodoWrite。记录前必须查现有条目去重：同一事项修改，独立事项新增。

**核心原则：** 会话内的任务用 TodoWrite；明确延后到未来会话的事项用 LATER。会话结束 TodoWrite 即失效，LATER 跨会话留存。

**为什么一项一文件（2026-08-07 起取代单文件 LATER.md）：** 单文件 + 全局顺序号在多分支并行时必然撞号、乱序、合并冲突；一项一文件 + 日期 slug ID 让任何分支在任何时刻新增条目都零协调、零冲突，单项演化历史可直接 `git log` 追溯。

本技能默认 `invocation_mode=helper`，持久化结果后返回调用方，不自行 Host Close。若直接承接用户目标，顶层 `standalone` 会话按 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md) 收尾。

## 何时使用

触发条件（任一即触发）：
- 用户说"稍后"、"以后"、"回头"、"晚点"、"先跳过"、"先不做这个"、"下个版本"、"这次先不弄"、"LATER"
- 调试/审查中发现的不属于当前任务范围但有价值的事项（bug、优化点、技术债）
- 用户要求回顾 LATER 项
- Claude 在工作中发现某 LATER 项可能已解决

**不适用：**

- 当前会话内会立即处理的任务 → 用 TodoWrite
- 用户明确要求立即修复的问题
- frontmatter 已标 `status: closed` 的事项

## 与 TodoWrite 的边界

| 维度 | TodoWrite | LATER |
|------|-----------|-------|
| 生命周期 | 当前会话 | 跨会话持久化 |
| 用途 | 当前任务进度跟踪 | 延后到未来会话的事项 |
| 存储 | 工具内存 | 项目根目录 `docs/AI/later/` 一项一文件 |
| 触发 | 任何多步骤任务 | 用户明确延后 / 范围外发现 |

**红线：** 用户说"以后再说"时用 TodoWrite 记录 = 失败。TodoWrite 会话结束即丢失，延后事项会无声消失。

## 工作环境询问（强制，先于核心流程）

**首次即将写入或修改 `docs/AI/later/` 前，必须按 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md) 的「工作环境询问」模板询问用户**：

- 选项 1（推荐）：新建隔离工作树（基于 `origin/develop`、本地 `develop` 最新提交，分支命名 `docs/later-tracking`，遵循 [dd-git-workflow/branch](../dd-git-workflow/references/branch.md) 与 [dd-git-workflow/worktree](../dd-git-workflow/references/worktree.md)）
- 选项 2：在当前 worktree 工作（仅做验证：`git rev-parse --is-inside-work-tree` + 并发检查）

**处理规则**：

- **选「新建」** → 走 [dd-git-workflow/worktree](../dd-git-workflow/references/worktree.md) 创建流程，调用 `scripts/create-worktree.sh docs later-tracking` 创建隔离工作树，cd 进入后开始核心流程
- **选「当前 worktree」** → 仅做验证（确认当前目录在 worktree 中且无同类工作流并发），通过后开始核心流程
- **null 输入** → 按 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md) 的「null 输入重问」规则重新询问，不得默认新建
- **特例（无需询问）**：
  - 纯查询 LATER 条目（用户只要求回顾，不新增/不修改）→ 不询问
  - 仅标记 `status: closed`（单文件 frontmatter 修改，且用户明确表态这是收尾）→ 不询问，但需提交

**选中工作环境后，后续所有 LATER 读写、提交都在该 worktree 中执行**，不得中途切换 worktree。

> **为何此处要询问**：LATER 条目是项目级追踪文件，写入即修改项目状态。若直接在主仓库或无关分支上新增，会污染当前分支的 commit。询问让用户基于场景判断：是新建隔离分支提交 LATER 变更，还是在当前 worktree 中作为附带提交。

## 体系检测（先于写入）

写入前检测项目处于哪种 LATER 体系：

1. `docs/AI/later/` 目录存在 → **新体系**，按本文件流程执行；
2. 只有旧单文件 `docs/AI/LATER.md` 且无 `later/` 目录 → **ASK 用户**：
   - 选项 A（推荐）：迁移到新体系（一项一文件，旧顺序号写入 `legacy_id`）；
   - 选项 B：本次维持旧格式追加（不静默混用两套体系）；
3. 两者都不存在 → **新体系**，创建 `docs/AI/later/` 并写入第一条。

不得静默迁移旧文件，也不得在新体系中继续使用顺序号。

## 核心流程

```dot
digraph later_flow {
    rankdir=LR;
    node [shape=box];

    detect [label="检测到延后信号" shape=diamond];
    ls [label="检测体系\nls docs/AI/later/"];
    grep [label="Grep later/ 目录\n关键词粗筛候选"];
    found [label="有候选?" shape=diamond];
    subagent [label="子代理语义精判\n是否同一事项"];
    same [label="同一事项?" shape=diamond];
    modify [label="修改已有条目文件\n正文/frontmatter 合并更新"];
    add [label="新增条目文件\nLATER-YYYYMMDD-slug.md"];
    index [label="有 INDEX 脚本则运行刷新\n同一 commit 带上 INDEX"];

    detect -> ls;
    ls -> grep;
    grep -> found;
    found -> add [label="无候选"];
    found -> subagent [label="有候选"];
    subagent -> same;
    same -> modify [label="是"];
    same -> add [label="否"];
    modify -> index;
    add -> index;
}
```

## 条目格式

**文件位置**：项目根目录 `docs/AI/later/`

**文件名即权威 ID**：`LATER-<YYYYMMDD>-<slug>.md`

- 日期为创建日期；slug 为简短英文主题（小写连字符）；
- 同日同主题多条追加 `-b`、`-c`；
- **无全局顺序号**，任何分支发号零协调；历史文档中的旧「LATER<N>」引用通过 frontmatter `legacy_id` 或 INDEX 对照表解析。

**内容结构**：项目存在 `docs/AI/later/_TEMPLATE.md` 时必须复制该模板；否则使用以下最小结构：

```markdown
---
id: LATER-20260807-example-slug   # 必须与文件名主体一致
title: 一句话标题
status: open                      # open | closed
created: 2026-08-07
source: 来源（审核/任务 + 日期）
tags: [模块标签]
related: []
target_phase: 建议处理阶段
trigger: 什么事件发生时必须处理本条
---

# {title}

## 现状

## 延后理由

## 关闭所需证据
```

写作要求：

- frontmatter 开放条目必填：`id`、`title`、`status`、`created`、`source`、`target_phase`、`trigger`；
- 正文分节、分条、硬换行；禁止把数百字糊成一段不换行的长文；
- title 保持一句话；细节进正文分节，但条目仍不是方案文档，不展开完整设计。

## 去重判断

**两步法：**

1. **主代理粗筛**：Grep `docs/AI/later/` 目录中新事项的关键名词/动词（title、tags、trigger、正文都会命中），找出候选条目文件；
2. **子代理精判**：把候选条目 + 新事项交给子代理，判断是否指向同一待解决事项。

**决策标准：**
- 同一待解决事项（同一 bug、同一优化目标、同一功能点）→ **修改**已有条目文件；
- 相关但独立（同模块的不同问题）→ **新增**条目文件，并在双方 frontmatter 的 `related` 互链。

**修改方式：** 更新该文件的 frontmatter（如 `trigger`、`target_phase` 变化）与正文对应分节，保持分条结构。不新建文件、不在正文堆叠重复描述。

## 产物生命周期与 INDEX（引用共享合同）

- LATER 条目与 INDEX 分别为 `working`/`derived`，详见 [dd-workflow-runtime/artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3。刷新 INDEX 与条目属于同一 change set 是不变量；只有当已获得 Delivery 授权要求 commit 时才要求同一 commit。

## INDEX 刷新

- 项目存在 INDEX 生成脚本（如 `Tools/gen_later_index.py`）时：新增/修改/关闭任何条目后必须立即运行脚本重新生成 INDEX.md，刷新与条目属于同一 change set，仅当已获得 Delivery 授权时才要求同一 commit；
- 项目无 INDEX 脚本时：只维护条目文件，不手写 INDEX。

## 完成标记

- 用户明确说某项完成了 → 该文件 frontmatter 改 `status: closed`，并填 `closed_at`、`closed_by_commits`（修复 commit 短 SHA 列表）、`evidence`（artifact 路径 / 测试名）；**文件原地不动，不删除不移动**；
- Claude 在工作中发现某 LATER 项已解决 → **主动建议**用户确认，不直接标记（避免误判）；
- 关闭后按上节刷新 INDEX。

## 红线 - 以下行为都是失败

- 用户说"以后再说"时用 TodoWrite 记录而非 `docs/AI/later/`
- 不查 `docs/AI/later/` 现有条目就直接新增（导致重复）
- 在新体系中重新引入全局顺序号（回到多分支撞号的老问题）
- 文件名与 frontmatter `id` 不一致
- 开放条目缺 `target_phase` 或 `trigger`（追溯执行无从谈起）
- 把数百字现状写成不换行的单段长文
- 关闭条目时删除或移动文件（追溯历史断裂）
- 有 INDEX 脚本的项目改了条目却不刷新 INDEX（同一 change set 不变量），或在已获 Delivery 授权时把 INDEX 放在另一个 commit
- 因为"不主动建文档"的原则而不创建 `docs/AI/later/`
- 把 LATER 项记到全局位置或其他目录而非项目根目录的 `docs/AI/`
- 标签用类型（bug/优化）而非模块/功能
- 把"相关但独立"的事项合并成一条
- 检测到旧 `docs/AI/LATER.md` 单文件时静默迁移或静默混用两套体系

## 合理化借口表

| 借口 | 现实 |
|------|------|
| "TodoWrite 就是用来记这些的" | TodoWrite 会话结束即失效。跨会话延后事项会丢失。`docs/AI/later/` 才是持久化。 |
| "不主动建文档是我的默认原则" | `docs/AI/later/` 不是可选文档，是跨会话任务追踪的必需持久化位置。此原则不适用。 |
| "用户没明确要求建文件" | 用户说"以后再说"本身就是要求持久化。会话结束即丢等于没记。 |
| "查询去重太繁琐，直接加就行" | 不去重导致条目膨胀重复，最终无法使用。15 秒查询省下后续混乱。 |
| "一项一文件太碎，单文件好翻" | 单文件在多分支下必撞号必冲突；翻阅需求由 INDEX（或 `ls` + Grep）承担，不该靠牺牲并发安全换取。 |
| "顺序号顺口，接着编就行" | 顺序号需要全局共识，分支上无法安全发号；日期+slug 零协调且天然按时间排序。 |
| "frontmatter 字段太多，写一句得了" | `target_phase`/`trigger` 是「后续追溯执行」的载体；缺字段的条目等于无主的债。 |
| "用全局 LATER 方便聚合" | 项目隔离。全局位置无法区分来源，且污染非项目上下文。必须放在项目根目录的 `docs/AI/`。 |
| "相关就合并到一条" | 相关 ≠ 同一事项。同模块的两个 bug 是独立的。只有同一待解决事项才合并，其余用 `related` 互链。 |
| "子代理精判太慢" | 主代理 Grep 已粗筛，子代理只判断少量候选。比处理重复条目的后续混乱快得多。 |

## 快速参考

| 操作 | 步骤 |
|------|------|
| 记录延后事项 | 检测体系 → Grep `docs/AI/later/` 关键词 → 有候选则子代理精判 → 修改已有文件或新增 `LATER-<YYYYMMDD>-<slug>.md` → 有 INDEX 脚本则刷新（同一 change set，获 Delivery 授权时同 commit） |
| 首次创建 | 创建 `docs/AI/later/`，有 `_TEMPLATE.md` 则复制，写入第一条 |
| 标记完成 | 用户确认后改 frontmatter `status: closed` + `closed_at` + `closed_by_commits` + `evidence`，文件原地不动，刷新 INDEX |
| 发现已解决 | 主动建议用户确认，不直接标记 |
| 回顾 LATER | Read `docs/AI/later/INDEX.md`（有脚本项目）或 Grep `status: open`，列出未完成项，等待用户指示 |
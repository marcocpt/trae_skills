---
name: dd-later-tracking
description: 用户延后工作时使用（"稍后/以后/回头/晚点/先跳过/先不做/下个版本/这次先不弄"），或调试/审核中出现不属于当前任务的范围蔓延项时使用。也适用于用户要求回顾延后事项，或发现之前记录的 LATER 项已被解决。
---

# dd-later-tracking

## 概述

把跨会话的延后事项持久化到项目根目录的 `/docs/AI/LATER.md`，不是会话级 TodoWrite。记录前必须查现有 LATER.md 去重：同一事项修改，独立事项新增。每行一条，简要不展开。

**核心原则：** 会话内的任务用 TodoWrite；明确延后到未来会话的事项用 LATER。会话结束 TodoWrite 即失效，LATER 跨会话留存。

## 何时使用

触发条件（任一即触发）：
- 用户说"稍后"、"以后"、"回头"、"晚点"、"先跳过"、"先不做这个"、"下个版本"、"这次先不弄"、"LATER"
- 调试/审查中发现的不属于当前任务范围但有价值的事项（bug、优化点、技术债）
- 用户要求回顾 LATER 项
- Claude 在工作中发现某 LATER 项可能已解决

**不适用：**

- 当前会话内会立即处理的任务 → 用 TodoWrite
- 用户明确要求立即修复的问题
- 已标记完成 `- [x]` 的事项

## 与 TodoWrite 的边界

| 维度 | TodoWrite | LATER |
|------|-----------|-------|
| 生命周期 | 当前会话 | 跨会话持久化 |
| 用途 | 当前任务进度跟踪 | 延后到未来会话的事项 |
| 存储 | 工具内存 | 项目根目录 /docs/AI/LATER.md 文件 |
| 触发 | 任何多步骤任务 | 用户明确延后 / 范围外发现 |

**红线：** 用户说"以后再说"时用 TodoWrite 记录 = 失败。TodoWrite 会话结束即丢失，延后事项会无声消失。

## 工作环境询问（强制，先于核心流程）

**首次即将写入或修改 `/docs/AI/LATER.md` 前，必须按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 的「工作环境询问」模板询问用户**：

- 选项 1（推荐）：新建隔离工作树（基于 `origin/develop` 最新提交，分支命名 `docs/later-tracking`，遵循 [dd-git-branch](../dd-git-branch/SKILL.md) 与 [dd-git-worktree](../dd-git-worktree/SKILL.md)）
- 选项 2：在当前 worktree 工作（仅做验证：`git rev-parse --is-inside-work-tree` + 并发检查）

**处理规则**：

- **选「新建」** → 走 [dd-git-worktree](../dd-git-worktree/SKILL.md) 创建流程，调用 `../dd-ai-git-workflow/scripts/create-worktree.sh docs later-tracking` 创建隔离工作树，cd 进入后开始核心流程
- **选「当前 worktree」** → 仅做验证（确认当前目录在 worktree 中且无同类工作流并发），通过后开始核心流程
- **null 输入** → 按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 的「null 输入重问」规则重新询问，不得默认新建
- **特例（无需询问）**：
  - 纯查询 LATER.md（用户只要求回顾，不新增/不修改）→ 不询问
  - 仅标记 `- [x]` 完成态（一行修改，且用户明确表态这是收尾）→ 不询问，但需提交

**选中工作环境后，后续所有 LATER.md 读写、提交都在该 worktree 中执行**，不得中途切换 worktree。

> **为何此处要询问**：LATER.md 是项目级追踪文件，写入即修改项目状态。若直接在主仓库或无关分支上追加，会污染当前分支的 commit。询问让用户基于场景判断：是新建隔离分支提交 LATER 变更，还是在当前 worktree 中作为附带提交。

## 核心流程

```dot
digraph later_flow {
    rankdir=LR;
    node [shape=box];

    detect [label="检测到延后信号" shape=diamond];
    read [label="Read 项目根目录 /docs/AI/LATER.md"];
    grep [label="Grep 关键词粗筛候选"];
    found [label="有候选?" shape=diamond];
    subagent [label="子代理语义精判\n是否同一事项"];
    same [label="同一事项?" shape=diamond];
    modify [label="修改已有条目\n替换为合并后简洁描述"];
    add [label="新增条目到末尾"];
    init [label="创建 /docs/AI/LATER.md\n加标题行"];

    detect -> read;
    read -> grep;
    grep -> found;
    found -> init [label="无候选或文件不存在"];
    found -> subagent [label="有候选"];
    subagent -> same;
    same -> modify [label="是"];
    same -> add [label="否"];
    init -> add;
}
```

## 行格式

```
- [ ] LATER1. 简要描述 #模块标签
```

- 状态：`- [ ]` 待办 / `- [x]` 完成
- LATER前缀 + 序号：`LATER1.`（序号递增，与 Logseq TODO 格式对齐）
- 描述：≤80 个中文字符，不展开细节，一行一条
- 标签：模块/功能区域，允许多标签，`#通用` 兜底
- 多标签示例：`- [ ] LATER1. 修复 token 失效时的重定向逻辑 #登录 #安全`

## LATER.md 结构与位置

**文件位置**：项目根目录的 `/docs/AI/LATER.md`

不分节，所有条目平铺。完成的条目原地改 `- [x]`，不移动不删除。

首次创建时加标题行：
```markdown
# LATER - 延后事项记录

- [ ] LATER1. 第一条事项 #模块
```

## 去重判断

**两步法：**

1. **主代理粗筛**：Read `/docs/AI/LATER.md`，Grep 新事项的关键名词/动词，找出候选条目
2. **子代理精判**：把候选条目 + 新事项交给子代理，判断是否指向同一待解决事项

**决策标准：**
- 同一待解决事项（同一 bug、同一优化目标、同一功能点）→ **修改**已有条目
- 相关但独立（同模块的不同问题）→ **新增**

**修改方式：** 替换为合并后的简洁描述，保持单行 ≤80 字符。不追加、不嵌套、不保留原文。

## 完成标记

- 用户明确说某项完成了 → 标记 `- [x]`（保留 LATER 前缀和序号）
- Claude 在工作中发现某 LATER 项已解决 → **主动建议**用户确认，不直接标记（避免误判）

## 红线 - 以下行为都是失败

- 用户说"以后再说"时用 TodoWrite 记录而非 `/docs/AI/LATER.md`
- 不查 `/docs/AI/LATER.md` 就直接新增（导致重复）
- 新增条目描述超过 80 字符或展开成段落
- 因为"不主动建文档"的原则而不创建 `/docs/AI/LATER.md`
- 把 LATER 项记到全局位置或其他目录而非项目根目录的 `/docs/AI/`
- 标签用类型（#bug #优化）而非模块/功能
- 把"相关但独立"的事项合并成一条
- LATER 格式不带序号或前缀（如 `- [ ] 事项` 而非 `- [ ] LATER1. 事项`）

## 合理化借口表

| 借口 | 现实 |
|------|------|
| "TodoWrite 就是用来记这些的" | TodoWrite 会话结束即失效。跨会话延后事项会丢失。`/docs/AI/LATER.md` 才是持久化。 |
| "不主动建文档是我的默认原则" | `/docs/AI/LATER.md` 不是可选文档，是跨会话任务追踪的必需持久化文件。此原则不适用于 `/docs/AI/LATER.md`。 |
| "用户没明确要求建文件" | 用户说"以后再说"本身就是要求持久化。会话结束即丢等于没记。 |
| "查询去重太繁琐，直接加就行" | 不去重导致 `/docs/AI/LATER.md` 膨胀重复，最终无法使用。15 秒查询省下后续混乱。 |
| "描述详细点更清楚" | LATER 是索引不是文档。详细上下文在会话历史中可查。超 80 字必须压缩。 |
| "用全局 LATER.md 方便聚合" | 项目隔离。全局 LATER.md 无法区分来源，且污染非项目上下文。必须放在项目根目录的 `/docs/AI/`。 |
| "相关就合并到一条" | 相关 ≠ 同一事项。同模块的两个 bug 是独立的。只有同一待解决事项才合并。 |
| "子代理精判太慢" | 主代理 Grep 已粗筛，子代理只判断少量候选。比处理重复条目的后续混乱快得多。 |

## 快速参考

| 操作 | 步骤 |
|------|------|
| 记录延后事项 | Read `/docs/AI/LATER.md` → Grep 关键词 → 有候选则子代理精判 → 修改或新增 `- [ ] LATER1. 事项 #标签` |
| 首次创建 | 创建 `/docs/AI/LATER.md`，加 `# LATER - 延后事项记录` 标题，写入第一条 `- [ ] LATER1. 事项 #标签` |
| 标记完成 | 用户确认后改 `- [x] LATER1.`，原地不动（保留序号） |
| 发现已解决 | 主动建议用户确认，不直接标记 |
| 回顾 LATER | Read `/docs/AI/LATER.md`，列出未完成项，等待用户指示 |

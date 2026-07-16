---
name: dd-shared-ask
description: 当需要结构化询问用户、处理 null 输入重问、确认提交边界、询问工作环境（worktree 选择）时使用（被 dd-ai-refactor-workflow、dd-bug-fix-workflow、dd-feature-development-workflow、dd-docreview-grilling、dd-writing-design-specs、dd-later-tracking 等引用）。触发词：AskUserQuestion、null 重问、结构化询问、worktree 选择、新建工作树、当前 worktree。
---

# dd 共享询问规则

## 概述

本技能包含 dd 系列技能通用的询问和提交规则（含 worktree 选择模板），各 dd 技能引用本技能以避免重复。

## 结构化询问

需要用户决策时，在 Trae 中使用 `AskUserQuestion`；在 Codex 中使用 `request_user_input`（如可用）或带清晰选项的简短文本问题。**一次只问一个问题**——每个 `AskUserQuestion` 调用只包含一个问题，等用户回答后再问下一个。

## null 输入重问

调用 `AskUserQuestion` 后，若返回结果为 null（含空值、空字符串、用户取消、未选择任何选项），视为未获取有效决策。必须以原问题重新询问用户，重复直到获取有效输入，不得自行假设默认值继续。

## 工作环境询问（worktree 选择）

**触发时机**：任何 dd 工作流 skill 在**首次即将修改文件前**（如创建分支、写规范、改代码、追加 LATER、生成 TODO 等），必须先询问工作环境。

**询问模板**（用 `AskUserQuestion`）：

- **问题**：本次工作将在哪个工作环境进行？
- **选项 1（推荐）**：新建隔离工作树
- **选项 2**：在当前 worktree 工作

**处理规则**：

- **选「新建隔离工作树」** → 走该 skill 内的工作树创建流程（基于 `origin/develop` 最新提交，使用 [dd-git-worktree](../dd-git-worktree/SKILL.md) 规则与 [dd-ai-git-workflow](../dd-ai-git-workflow/SKILL.md) 的 `create-worktree.sh` 脚本）
- **选「在当前 worktree 工作」** → 仅做验证：
  1. 检查当前目录是否在 worktree 中（`git rev-parse --is-inside-work-tree`）
  2. 检查当前 worktree 是否已有活跃的同类工作流（遵循 [dd-shared-state](../dd-shared-state/SKILL.md) 并发检查），有则禁止并发，要求重新选择
  3. 验证通过后，后续所有工作都在该 worktree 中执行
- **null 输入** → 按上方「null 输入重问」规则重新询问，不得默认新建

**选中工作环境后，后续所有工作都在选中的工作树中执行**——不得中途切换 worktree，不得跨 worktree 引用未提交状态。

**为何不默认新建**：默认新建会剥夺用户的选择权，且在「快速修补」「单文件微调」「LATER 追加」等场景下新建 worktree 反而是开销。**必须询问**，让用户基于场景判断。

**特例（无需询问）**：
- 纯查询、纯读取、纯分析任务（不修改任何文件）→ 不询问
- 已在该工作流内（选中后）继续推进后续步骤 → 不重复询问
- 上下文恢复后判断已进入工作流中段 → 不询问（按 [dd-shared-state](../dd-shared-state/SKILL.md) 恢复机制处理）

## 文档规则优先

项目存在 `.trae/rules/docs.md`、`docs/CODING_STANDARDS.md`、`docs/AI/trae-xctest-rules.md` 时，写设计规范、计划、检查前先阅读并遵守。

## 提交边界

每次 commit 只包含当前阶段的相关文件。不得暂存无关脏文件，不得提交秘密文件，不得使用 `--no-verify`，不得 force push。

## 被其他 skill 引用方式

各 dd 技能在全局规则中引用本技能，替换重复的询问规则内容。引用格式：`询问规则遵循 [dd-shared-ask](../dd-shared-ask/SKILL.md)（含 worktree 选择模板）`

各 dd 技能在「即将首次修改文件前」显式调用本技能的「工作环境询问」模板，引用格式：`首次修改文件前，按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 的「工作环境询问」模板询问用户`

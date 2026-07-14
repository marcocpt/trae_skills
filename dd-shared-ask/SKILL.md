---
name: dd-shared-ask
description: dd 系列技能共享的询问规则，涵盖结构化询问、null 输入重问、文档规则优先和提交边界。被 dd-ai-refactor-workflow、dd-bug-fix-workflow、dd-docreview-grilling、dd-feature-development-workflow、dd-writing-design-specs 引用。触发词：AskUserQuestion、null 重问、结构化询问。
---

# dd 共享询问规则

## 概述

本技能包含 dd 系列技能通用的询问和提交规则，各 dd 技能引用本技能以避免重复。

## 结构化询问

需要用户决策时，在 Trae 中使用 `AskUserQuestion`；在 Codex 中使用 `request_user_input`（如可用）或带清晰选项的简短文本问题。**一次只问一个问题**——每个 `AskUserQuestion` 调用只包含一个问题，等用户回答后再问下一个。

## null 输入重问

调用 `AskUserQuestion` 后，若返回结果为 null（含空值、空字符串、用户取消、未选择任何选项），视为未获取有效决策。必须以原问题重新询问用户，重复直到获取有效输入，不得自行假设默认值继续。

## 文档规则优先

项目存在 `.trae/rules/docs.md`、`docs/CODING_STANDARDS.md`、`docs/AI/trae-xctest-rules.md` 时，写设计规范、计划、检查前先阅读并遵守。

## 提交边界

每次 commit 只包含当前阶段的相关文件。不得暂存无关脏文件，不得提交秘密文件，不得使用 `--no-verify`，不得 force push。

## 被其他 skill 引用方式

各 dd 技能在全局规则中引用本技能，替换重复的询问规则内容。引用格式：`询问规则遵循 [dd-shared-ask](../dd-shared-ask/SKILL.md)`

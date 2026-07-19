---
name: dd-git-branch
description: 当新建分支、确认分支命名规则、配置 Feature Flag 时使用。触发词：分支命名、创建分支、feature flag。
---

# Git 分支管理

## 概述

分支管理是 Git 工作流的基础，遵循"一个分支一个功能"原则。本技能涵盖分支命名、创建和 Feature Flag 策略。完整工作流总览见 [dd-git-workflow](../dd-git-workflow/SKILL.md)。

## 分支命名规则

### 分支模型

```text
main
 └── develop
      ├── feature/{F编号}-{描述}
      ├── fix/{F编号}-{描述}
      ├── docs/{主题}
      └── refactor/{模块}
```

### 三层模型

- `main`：仅用于正式发布，永远保持可发布状态
- `develop`：开发主干，始终保持可编译、测试通过
- `feature/*` / `fix/*` / `docs/*` / `refactor/*`：工作分支，一个功能一个分支，一个 AI Agent 一个分支

### 命名格式

| 前缀 | 用途 | 命名格式 | 示例 |
|------|------|---------|------|
| `feature/` | 新功能开发 | `feature/{F编号}-{描述}` | `feature/F3.1-ocr-acceleration` |
| `fix/` | 缺陷修复 | `fix/{F编号}-{描述}` | `fix/F2.4-hotkey-conflict` |
| `docs/` | 文档变更 | `docs/{主题}` | `docs/ai-git-workflow` |
| `refactor/` | 重构 | `refactor/{模块}` | `refactor/core-state-machine` |

### 命名约束

- 描述部分使用小写英文与连字符，避免下划线、空格、中文
- 一个分支只承载一个职责，禁止在 `feature/` 分支混入 `fix/` 内容
- 分支名总长度建议不超过 50 字符

## 一分支一功能

### 核心原则

一个分支只做一个功能。

### 含义

- 一个分支只承载一个职责，禁止在 `feature/` 分支混入 `fix/` 内容
- 一个 AI Agent 一个分支
- 跨模块修改必须开独立分支，按模块顺序合并（Core → UI → App）
- 单个 Agent 不得同时修改 3 个以上模块

## 分支创建

### worktree 创建规则

- **一个分支一个 worktree**：禁止跨分支共享工作区
- **路径位置**：worktree 创建在仓库同级目录下，便于统一管理
- **基线分支**：基于 `origin/develop` 最新提交创建
- **创建即同步**：创建后立即 `git fetch origin` 确保基线最新

### 创建脚本

**脚本路径**：`../dd-ai-git-workflow/scripts/create-worktree.sh`

```bash
# 用法
bash ../dd-ai-git-workflow/scripts/create-worktree.sh feature F3.1 ocr-acceleration
bash ../dd-ai-git-workflow/scripts/create-worktree.sh fix F3.1 hotkey-conflict
bash ../dd-ai-git-workflow/scripts/create-worktree.sh docs ai-git-workflow
bash ../dd-ai-git-workflow/scripts/create-worktree.sh refactor core-state-machine
```

### worktree 命名规则

- worktree 目录名 = 分支名（保留斜杠 `/`，按分支类型嵌套子目录）
- 示例：分支 `feature/F3.1-ocr-acceleration` → worktree 目录 `${project}-worktrees/feature/F3.1-ocr-acceleration`
- 示例：分支 `fix/F3.1-hotkey-conflict` → worktree 目录 `${project}-worktrees/fix/F3.1-hotkey-conflict`
- worktree 目录位于仓库同级的 `${project}-worktrees` 下，按分支类型分类

## Feature Flag

未完成功能建议通过 Feature Flag 合并到 develop，而不是长期保留分支。

### 适用场景

- 功能开发周期超过 1 天，但已有可合并的部分实现
- 需要提前集成到 develop 验证架构兼容性
- 多人协作的功能，部分模块先行

### 实现方式

- 通过配置开关控制功能启用
- 默认关闭，验证通过后开启
- Feature Flag 必须在功能完成后移除，避免长期残留

## 禁止事项

- **一个分支多个独立功能**：一个分支只承载一个职责，禁止在 `feature/` 分支混入 `fix/` 内容
- **分支命名违规**：禁止使用下划线、空格、中文；分支名总长度禁止超过 50 字符
- **已共享分支频繁 Rebase**：坚持 merge-only 原则，不引入 rebase
- **禁止 worktree 跨分支共享工作区**：一个 worktree 只属于一个分支
- **禁止用 `--ff-only` 替代功能合并**：功能合并必须 `--no-ff` 保留分支历史
- **禁止跨模块边界修改**：单个 Agent 不得同时修改 3 个以上模块

---
name: using-git-worktrees
description: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
---

# 使用 Git 工作树

## 概述

Git 工作树创建共享同一仓库的隔离工作区，允许同时在多个分支上工作而无需切换。

**核心原则：** 固定的目录规则 + 自动化设置 + 基线验证 = 可靠的隔离。

**开始时宣布：** "我正在使用 using-git-worktrees 技能来建立一个隔离的工作区。"

**后续每次会话开始时必须宣布：** "当前所在工作树：`<worktree-path>`，分支：`<branch-name>`"

## 目录选择流程

工作树目录固定位于当前项目的**上级目录**，命名为 `<project-name>-worktrees`。

例如：项目路径为 `Keyboard/Macim`，则工作树目录为 `Keyboard/Macim-worktrees`（与项目同级）。

### 计算路径

**关键：** 必须基于**主仓库**位置计算，而非当前工作树——否则在工作树内再次调用时，项目名会被误识别为分支名，导致工作树目录嵌套。

```bash
# 获取主仓库根目录（即使当前已在某个 worktree 中也能正确识别主仓库）
common_dir=$(git rev-parse --git-common-dir)      # 主仓库的 .git 目录
main_root=$(cd "$(dirname "$common_dir")" && pwd) # 主仓库根目录
# 获取项目名（基于主仓库，而非当前工作树）
project=$(basename "$main_root")
# 工作树目录 = 主仓库上级目录 + 项目名 + -worktrees
worktree_dir=$(dirname "$main_root")/${project}-worktrees
```

**为什么不用 `--show-toplevel`：** 该命令在 worktree 内返回的是**当前工作树**路径，而非主仓库路径，会导致项目名错误和工作树目录嵌套。

**示例：**
- 主仓库：`/Users/jesse/projects/myproject`
- 工作树目录：`/Users/jesse/projects/myproject-worktrees`
- 分支工作树：`/Users/jesse/projects/myproject-worktrees/auth`
- 在 `myproject-worktrees/auth` 内再次调用 → 仍识别主仓库 `myproject`，工作树目录仍为 `myproject-worktrees`（不会嵌套）

## 安全验证

工作树目录位于项目上级目录（项目之外），完全脱离当前仓库，**无需 .gitignore 验证**——不会污染 git status，也不会被意外提交到当前仓库。

## 创建步骤

### 1. 计算工作树路径

```bash
# 基于主仓库计算，避免在 worktree 内调用时项目名识别错误
common_dir=$(git rev-parse --git-common-dir)
main_root=$(cd "$(dirname "$common_dir")" && pwd)
project=$(basename "$main_root")
worktree_dir=$(dirname "$main_root")/${project}-worktrees
```

### 2. 创建工作树

```bash
# 每个分支作为工作树目录的子目录
path="$worktree_dir/$BRANCH_NAME"

# 创建带有新分支的工作树
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

### 3. 运行项目设置

自动检测并运行相应的设置命令：

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

### 4. 验证基线正常

运行测试确保工作树初始状态干净：

```bash
# 示例 - 使用项目对应的命令
npm test
cargo test
pytest
go test ./...
```

**如果测试失败：** 报告失败情况，询问是否继续或排查。

**如果测试通过：** 报告就绪。

### 5. 报告位置

```
工作树已就绪：<full-path>
测试通过（<N> 个测试，0 个失败）
准备实现 <feature-name>
```

**重要：调用 using-git-worktrees 后，当前会话的工作目录必须始终位于该工作树路径下，不得切换回主仓库目录。后续所有操作均在该工作树内完成。**

## 快速参考

| 情况 | 操作 |
|------|------|
| 计算路径 | `../<project-name>-worktrees`（项目上级目录） |
| 基线测试失败 | 报告失败 + 询问 |
| 无 package.json/Cargo.toml | 跳过依赖安装 |

## 常见错误

### 带着失败的测试继续

- **问题：** 无法区分新 bug 和已有问题
- **修复：** 报告失败，获得明确许可后再继续

### 硬编码设置命令

- **问题：** 在使用不同工具的项目上会出错
- **修复：** 从项目文件自动检测（package.json 等）

### 在项目内部创建工作树

- **问题：** 工作树目录被仓库跟踪，污染 git status
- **修复：** 始终使用项目上级目录 `../<project-name>-worktrees`

## 示例工作流

```
你：我正在使用 using-git-worktrees 技能来建立一个隔离的工作区。

[计算路径：项目 myproject 位于 /Users/jesse/projects/myproject]
[工作树目录：/Users/jesse/projects/myproject-worktrees]
[创建工作树：git worktree add ../myproject-worktrees/auth -b feature/auth]
[运行 npm install]
[运行 npm test - 47 个通过]

工作树已就绪：/Users/jesse/projects/myproject-worktrees/auth
测试通过（47 个测试，0 个失败）
准备实现 auth 功能
```

## 红线

**绝不：**
- 跳过基线测试验证
- 不询问就带着失败的测试继续
- 在项目内部创建工作树目录

**始终：**
- 使用项目上级目录 + `<project-name>-worktrees` 作为工作树目录
- 自动检测并运行项目设置
- 验证测试基线干净
- 调用后会话工作目录始终位于工作树路径下
- 每次会话开始时宣布当前所在工作树和分支

## 集成

**被以下技能调用：**
- **brainstorming**（阶段 4）- 设计通过且需要实现时必需
- **subagent-driven-development** - 执行任何任务前必需
- **executing-plans** - 执行任何任务前必需
- 任何需要隔离工作区的技能

**配合使用：**
- **finishing-a-development-branch** - 工作完成后清理时必需

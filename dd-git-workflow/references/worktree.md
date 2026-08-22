> 迁移来源：`dd-git-workflow/worktree/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# Git Worktree 管理

## 概述

worktree 遵循"一个分支一个 worktree"原则，禁止跨分支共享工作区。本技能涵盖创建、命名、同步和清理规则。完整工作流总览见 [dd-git-workflow](../../dd-git-workflow/SKILL.md)。

本技能按 `invocation_mode=helper` 返回调用方，不自行 Host Close。直接承接用户目标时由顶层 `standalone` 会话按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 收尾。

## worktree 创建规则

- **一个分支一个 worktree**：禁止跨分支共享工作区
- **路径位置**：worktree 创建在仓库同级目录下的 `${project}-worktrees` 子目录中，按分支类型分子目录
- **基线分支**：基于 `origin/develop`、本地 `develop` 最新提交（取两者中更新的）创建，新分支不设置 upstream（首次 push 用 `git push -u origin <branch>` 建立独立 tracking）
- **创建即同步**：创建后立即 `git fetch origin` 确保基线最新

**创建脚本**：`scripts/create-worktree.sh`

```bash
# 用法
scripts/create-worktree.sh feature F3.1 ocr-acceleration
scripts/create-worktree.sh fix F3.1 hotkey-conflict
scripts/create-worktree.sh docs ai-git-workflow
scripts/create-worktree.sh refactor core-state-machine
```

## worktree 命名规则

- worktree 目录名 = 分支名（保留斜杠 `/`，按分支类型嵌套子目录）
- 示例：分支 `feature/F3.1-ocr-acceleration` → worktree 目录 `${project}-worktrees/feature/F3.1-ocr-acceleration`
- 示例：分支 `fix/F3.1-hotkey-conflict` → worktree 目录 `${project}-worktrees/fix/F3.1-hotkey-conflict`
- worktree 目录位于仓库同级的 `${project}-worktrees` 下，按分支类型分类，便于统一管理

## worktree 状态同步

worktree 之间**不共享工作区状态**，每个 worktree 是独立的 git 工作目录：

- 每个 worktree 需要独立执行 `git fetch origin`
- worktree A 的未提交改动不会出现在 worktree B 中
- stash 不跨 worktree 共享
- 推荐使用 commit 而非 stash 保存中间状态

## worktree 清理规则

- **合并后立即清理**：分支合并到 develop 后，立即执行 `git worktree remove`
- **同步删除远端分支**：清理工作树时同步删除 origin 上的对应分支（`git push origin --delete <branch>`），避免远端残留废弃分支
- **避免腐烂**：超过 7 天无活动的 worktree 进入清理建议清单
- **清理顺序**：先 `git worktree remove <path>`，再 `git branch -d <branch>`，最后 `git push origin --delete <branch>`
- **强制清理**：worktree 目录被手动删除时，使用 `git worktree prune` 修复元数据

## 禁止事项

- **禁止 worktree 跨分支共享工作区**：一个 worktree 只属于一个分支

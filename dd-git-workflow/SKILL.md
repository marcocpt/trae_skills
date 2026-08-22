---
name: dd-git-workflow
description: 当 AI Coding 任务涉及分支、worktree、commit、merge、冲突、CI、分支健康或清理时使用；也用于 Feature/Bug/Refactor/Bootstrap 的 Git Delivery Gate。触发词：git workflow、创建分支、worktree、commit、merge、冲突、pre-merge、cleanup。
---

# Git 工作流

## 目标

为 AI Agent 提供一套统一、可按需加载的 Git 约束。Codex 可直接执行普通 Git 原子命令；本 Skill 只保留项目特有的分支模型、merge-only、worktree 隔离、CI SHA 绑定、冲突与清理规则。

## 核心原则

1. 一个分支一个职责，一个 worktree 一个分支；
2. `develop` 保持可编译、可测试；`main` 仅用于发布；
3. 已共享开发分支优先 merge-only，不以长期 rebase 改写历史；
4. 合并前必须验证准确候选 SHA；
5. 不混入用户已有 dirty diff，不自动清理未确认分支；
6. Git 原子动作由 Codex 直接执行，只有需要专项规则时再读 reference。

## 分支模型

```text
main
 └── develop
      ├── feature/{F编号}-{描述}
      ├── fix/{F编号}-{描述}
      ├── docs/{主题}
      └── refactor/{模块}
```

## 按需读取

| 场景 | Reference |
|---|---|
| 分支命名 / Feature Flag | [branch.md](references/branch.md) |
| worktree 创建与隔离 | [worktree.md](references/worktree.md) |
| commit 生成与 staging | [commit.md](references/commit.md) |
| merge / push / commit 规范 | [merge.md](references/merge.md) |
| 冲突与公共文件风险 | [conflict.md](references/conflict.md) |
| 合并前 CI / PreMergeChecklist | [ci.md](references/ci.md) |
| 分支健康 / daily sync | [health.md](references/health.md) |
| 已合并分支与 worktree 清理 | [cleanup.md](references/cleanup.md) |
| 仓库自带脚本调用合同 | [scripts.md](references/scripts.md) |

脚本位于 [scripts/](scripts/)：`create-worktree.sh`、`daily-sync.sh`、`pre-merge-check.sh`、`conflict-predict.sh`、`branch-health.sh`、`cleanup-suggest.sh`。

## 全局禁止事项

- 一个分支混入多个独立功能；
- worktree 跨分支共享工作区；
- Merge 前不测试或用旧 CI 结果冒充当前 SHA；
- 未经确认覆盖/清理用户已有改动；
- 已共享分支频繁 rebase / force push；
- 用固定 sleep 掩盖 Git/CI 竞态；
- 自动删除未确认分支或 worktree。

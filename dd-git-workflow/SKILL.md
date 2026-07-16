---
name: dd-git-workflow
description: 当需要了解 Git 工作流全貌、不确定应使用哪个子技能时使用。触发词：git workflow、git 工作流、分支模型。
---

# Git 工作流入口

## 概述

AI Coding 场景下的 Git 工作流守护技能，适用于 Cursor、Codex、Claude Code、Trae 等 AI Agent 在多分支并行开发时的版本管理。

**核心原则：** 一个分支一个功能；每天必须有合并动作（不只是同步）；merge-only，不引入 rebase。

## 核心原则

1. 一个分支只做一个功能
2. AI Coding 场景下分支每天必须有合并动作，无固定天数上限
3. AI Coding 场景优先使用 **merge**，而不是长期使用 **rebase**

## 分支模型

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

### 分支命名规则

| 前缀 | 用途 | 命名格式 | 示例 |
|------|------|---------|------|
| `feature/` | 新功能开发 | `feature/{F编号}-{描述}` | `feature/F3.1-ocr-acceleration` |
| `fix/` | 缺陷修复 | `fix/{F编号}-{描述}` | `fix/F2.4-hotkey-conflict` |
| `docs/` | 文档变更 | `docs/{主题}` | `docs/ai-git-workflow` |
| `refactor/` | 重构 | `refactor/{模块}` | `refactor/core-state-machine` |

命名约束：

- 描述部分使用小写英文与连字符，避免下划线、空格、中文
- 一个分支只承载一个职责，禁止在 `feature/` 分支混入 `fix/` 内容
- 分支名总长度建议不超过 50 字符

## 子技能导航

| 子技能 | 职责 | 触发场景 |
|--------|------|---------|
| [dd-git-branch](../dd-git-branch/SKILL.md) | 分支命名、创建、Feature Flag | 新建分支、分支命名 |
| [dd-git-merge](../dd-git-merge/SKILL.md) | merge-only、每天合并、Commit 规范 | 合并流程、提交规范 |
| [dd-git-conflict](../dd-git-conflict/SKILL.md) | 冲突处理、公共文件锁、模块边界 | 冲突解决、公共文件修改 |
| [dd-git-worktree](../dd-git-worktree/SKILL.md) | worktree 创建、命名、同步、清理 | 工作树管理 |
| [dd-git-health](../dd-git-health/SKILL.md) | 健康度检查、每日同步 | 分支健康监控 |
| [dd-git-cleanup](../dd-git-cleanup/SKILL.md) | 废弃分支检测、清理流程 | 分支清理 |
| [dd-git-ci](../dd-git-ci/SKILL.md) | 合并前检查、CI 配置、JSON 输出 | 合并前自检、CI 配置 |

## 被其他 skill 引用方式

### 语义触发

其他 skill 通过 description 字段语义触发本技能：

- `dd-writing-design-specs`：编写设计规范涉及分支创建时引用
- `dd-feature-development-workflow`：功能开发流程涉及合并检查时引用
- `dd-bug-fix-workflow`：bug 修复流程涉及分支管理时引用
- `finishing-a-development-branch`：分支收尾涉及合并检查时引用

### 调用入口

| 时机 | 调用入口 | 输出 |
|------|---------|------|
| 分支创建 | `../dd-ai-git-workflow/scripts/create-worktree.sh` | 分支名 + worktree 路径 |
| 日常同步 | `../dd-ai-git-workflow/scripts/daily-sync.sh` | 同步结果 + 冲突清单 |
| 合并前检查 | `../dd-ai-git-workflow/scripts/pre-merge-check.sh` | PreMergeChecklist JSON |
| 冲突处理 | `../dd-ai-git-workflow/scripts/conflict-predict.sh` | ConflictPredictionReport JSON |
| 健康监控 | `../dd-ai-git-workflow/scripts/branch-health.sh` | BranchHealthReport JSON |
| 废弃清理 | `../dd-ai-git-workflow/scripts/cleanup-suggest.sh` | CleanupSuggestion JSON |

### 输出引用

其他 skill 可读取本技能输出的结构化数据：

- `PreMergeChecklist.all_pass` 为 `false` 时，调用方必须阻止合并
- `BranchHealthReport.grade` 为 `dangerous` 时，调用方必须提示干预
- `ConflictPredictionReport.severity` 为 `high` 时，调用方必须提示先解决冲突
- `CleanupSuggestion.stale_worktrees` 非空时，调用方可提示用户清理

### 协同约定

- 本技能**不替代**项目文档同步技能，仅在合并前检查中引用其能力
- 本技能**不替代**项目编码规范，仅在 SwiftLint 检查中调用
- 本技能**不重复**项目规则，只在分支管理维度补充

## 全局禁止事项

- 长期未同步 develop 的分支（超过 1 天未合并视为陈旧）
- 一个分支多个独立功能
- Merge 前不测试
- 修改大量公共文件
- 已共享分支频繁 Rebase
- **禁止 worktree 跨分支共享工作区**：一个 worktree 只属于一个分支
- **禁止公共文件长期独立修改**：公共文件分支必须 <1 天合并
- **禁止跨模块边界修改**：单个 Agent 不得同时修改 3 个以上模块
- **禁止用 `--ff-only` 替代功能合并**：功能合并必须 `--no-ff` 保留分支历史
- **禁止跳过 AI 自检直接合并**：合并前必须运行 `pre-merge-check.sh`
- **禁止自动清理未确认分支**：清理脚本仅输出建议，必须用户确认
- **禁止用固定 sleep 掩盖合并竞态**：合并冲突必须显式解决

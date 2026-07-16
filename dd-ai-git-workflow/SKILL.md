---
name: dd-ai-git-workflow
description: 当 dd-git-worktree、dd-git-health、dd-git-ci、dd-git-conflict、dd-git-cleanup 等子技能需要调用 create-worktree、daily-sync、pre-merge-check、conflict-predict、branch-health、cleanup-suggest 脚本时使用。触发词：git 脚本、worktree 脚本、合并检查脚本、健康度脚本、清理脚本。
---

# AI Coding Git 工作流脚本托管

## 概述

本技能是 Git 工作流的**脚本托管位置**，存放所有可执行脚本。工作流规范、原则、流程图等内容分布在子技能中，本技能仅保留脚本入口和输出格式定义。

**工作流入口：** [dd-git-workflow](../dd-git-workflow/SKILL.md) 提供总览、核心原则、分支模型和子技能导航。

## 脚本清单

| 脚本 | 用途 | 输出格式 | 调用方 |
|------|------|---------|--------|
| `scripts/create-worktree.sh` | 创建分支和 worktree | 终端文本 | dd-git-worktree |
| `scripts/daily-sync.sh` | 每日同步上游并检测冲突 | 终端文本 + 退出码 | dd-git-health |
| `scripts/pre-merge-check.sh` | 合并前 AI 自检 | PreMergeChecklist JSON | dd-git-ci |
| `scripts/conflict-predict.sh` | 冲突预测 | ConflictPredictionReport JSON | dd-git-conflict |
| `scripts/branch-health.sh` | 分支健康度评分 | BranchHealthReport JSON | dd-git-health |
| `scripts/cleanup-suggest.sh` | 废弃分支清理建议 | CleanupSuggestion JSON | dd-git-cleanup |

### 用法示例

```bash
# 创建 worktree
./scripts/create-worktree.sh feature F3.1 ocr-acceleration

# 每日同步
./scripts/daily-sync.sh

# 合并前自检（输出 JSON）
./scripts/pre-merge-check.sh

# 健康度检查（输出 JSON）
./scripts/branch-health.sh [base-branch]

# 冲突预测（输出 JSON）
./scripts/conflict-predict.sh [base-branch]

# 清理建议（输出 JSON）
./scripts/cleanup-suggest.sh [stale-days]
```

## 输出格式规范

所有自动化脚本输出 JSON，便于其他 skill 解析引用。JSON 是脚本的权威输出格式，调用方可基于 JSON 自行渲染 Markdown 报告。

### BranchHealthReport

```json
{
  "BranchHealthReport": {
    "branch": "feature/F3.1-ocr-acceleration",
    "base": "origin/develop",
    "stale_days": 2,
    "conflict_files": 3,
    "changed_files": 12,
    "mergeable": true,
    "scores": { "stale": 60, "conflict": 55, "scale": 79, "mergeable": 100, "total": 70 },
    "grade": "watch",
    "warnings": "stale>2d; conflict>3files; "
  }
}
```

### ConflictPredictionReport

```json
{
  "ConflictPredictionReport": {
    "branch": "feature/F3.1-ocr-acceleration",
    "base": "origin/develop",
    "has_conflict": true,
    "conflict_files": ["Sources/MacimCore/OCR/OCREngine.swift", "Package.swift"],
    "conflict_count": 2,
    "severity": "low"
  }
}
```

### PreMergeChecklist

```json
{
  "PreMergeChecklist": {
    "branch": "feature/F3.1-ocr-acceleration",
    "base": "origin/develop",
    "all_pass": false,
    "checks": {
      "uncommitted_files": {"status": "pass", "count": 0},
      "swiftlint": {"status": "pass", "files_checked": 5},
      "doc_sync": {"status": "warn", "reason": "swift changes without docs update", "swift_files": 5, "docs_files": 0},
      "conflict_predict": {"status": "pass", "conflict_files": 0},
      "sync": {"status": "pass", "ahead": 8, "behind": 0},
      "build": {"status": "manual", "reason": "run xcodebuild or project test script"},
      "tests": {"status": "manual", "reason": "run project test script"},
      "public_file": {"status": "pass", "commits": 0},
      "public_file_age": {"status": "pass", "age_days": 0},
      "cross_module": {"status": "pass", "modules": 1, "declared_commits": 0}
    }
  }
}
```

### CleanupSuggestion

```json
{
  "CleanupSuggestion": {
    "merged_branches": ["feature/F2.0-multi-monitor", "fix/F2.4-hotkey"],
    "stale_worktrees": [
      {"path": "/repo/../W-F2.0", "branch": "feature/F2.0-multi-monitor", "age_days": 10, "merged": true}
    ],
    "orphan_worktrees": 0,
    "stale_threshold_days": 7,
    "current_branch": "feature/F3.1-ocr-acceleration"
  }
}
```

## 输出引用约定

其他 skill 可读取本技能脚本输出的结构化数据：

- `PreMergeChecklist.all_pass` 为 `false` 时，调用方必须阻止合并
- `BranchHealthReport.grade` 为 `dangerous` 时，调用方必须提示干预
- `ConflictPredictionReport.severity` 为 `high` 时，调用方必须提示先解决冲突
- `CleanupSuggestion.stale_worktrees` 非空时，调用方可提示用户清理

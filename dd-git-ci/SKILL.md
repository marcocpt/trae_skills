---
name: dd-git-ci
description: 当合并前需要自检、配置 CI 流水线、输出 PreMergeChecklist JSON 时使用。触发词：pre-merge check、合并前检查、CI 配置、swiftlint、JSON 输出。
---

# Git CI 和合并前检查

## 概述

合并前检查确保分支在合并回 develop 前通过所有质量门禁。本技能涵盖合并前自检、CI 配置和 JSON 输出格式。完整工作流总览见 [dd-git-workflow](../dd-git-workflow/SKILL.md)。

本技能按 `invocation_mode=helper` 返回调用方，不自行 Host Close。直接承接用户目标时由顶层 `standalone` 会话按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 收尾。

## 基础检查

```bash
git fetch origin
git merge-tree --write-tree --name-only origin/develop HEAD
```

随后执行：Build、Unit Test、UI Test。全部通过后再合并。

## SwiftLint strict

包含 Swift 代码变更时**必检**：

```bash
swiftlint lint --strict
```

未通过禁止合并。仅文档、配置等非代码改动可跳过。

## 文档同步检查

修改以下内容时**必检**文档同步：

| 修改类型 | 需同步的文档 |
|---------|-------------|
| 用户可见行为 | 需求文档、设计文档、视觉原型 |
| 技术架构、接口、数据模型 | 实施草案 |
| 实施步骤、测试策略 | 实现计划 |
| UI 行为 | 视觉原型 |
| 关键架构决策 | historys/ 目录追加记录 |

## 冲突预检报告

合并前必须运行冲突预检，输出 `ConflictPredictionReport`：

- `severity: high`（>5 文件冲突）禁止合并，必须先解决冲突
- `severity: medium`（3-5 文件）需人工确认后合并
- `severity: low`（≤2 文件）可合并，但需在 PR 描述中标注

## AI Agent 自检清单

合并前 AI Agent 必须自检：

| 自检项 | 检查方式 | 失败处理 |
|--------|---------|---------|
| 未提交文件 | `git status --porcelain` | 提交或 stash |
| 未跑测试 | 检查测试脚本执行记录 | 补跑测试 |
| 未同步文档 | 对照文档同步检查表 | 同步文档 |
| 未同步 develop | `git log HEAD..origin/develop` | 执行 daily-sync |
| 公共文件未隔离 | 检查 commit 是否含 PublicFile tag | 拆分到独立分支 |
| 公共文件分支超期 | `git log --format=%cd --date=short <merge-base>..HEAD` 与今天对比，>1 天且含 PublicFile tag | 立即合并或拆分 |
| 跨模块修改未声明 | 检查修改文件是否跨多个顶层模块目录且无 `CrossModule:` tag | 补充 CrossModule: tag 或拆分 |

**合并前自检脚本**：`../dd-ai-git-workflow/scripts/pre-merge-check.sh`

```bash
# 用法：输出 PreMergeChecklist JSON
bash ../dd-ai-git-workflow/scripts/pre-merge-check.sh
# all_pass=false 时禁止合并
```

## 推荐 CI

CI 流水线推荐包含以下步骤：

1. **Compile**：编译检查
2. **SwiftLint**：代码规范检查（含 strict 模式）
3. **Unit Test**：单元测试
4. **UI Test**：UI 测试（如适用）
5. **merge-tree 检查**：合并冲突预检（`git merge-tree --write-tree --name-only`）
6. **Merge 到 develop**：PR 审查通过后自动合并

### CI 触发时机

- PR 创建时：步骤 1-5
- PR 合并时：步骤 6
- 定时任务（每日）：健康度检查 + 废弃清理建议

## 推荐 Git Alias

```bash
# 基础 alias
git config alias.sync "!git fetch origin && git merge origin/develop"
git config alias.checkmerge "merge-tree --write-tree --name-only origin/develop HEAD"
git config alias.graph "log --graph --oneline --decorate --all"

# 技能脚本 alias（需设置 SKILL_DIR 环境变量，脚本位于 dd-ai-git-workflow 技能目录）
SKILL_DIR="$HOME/.trae-cn/skills/dd-ai-git-workflow/scripts"
git config alias.health-check "!bash $SKILL_DIR/branch-health.sh"
git config alias.conflict-predict "!bash $SKILL_DIR/conflict-predict.sh"
git config alias.cleanup-suggest "!bash $SKILL_DIR/cleanup-suggest.sh"
git config alias.pre-merge-check "!bash $SKILL_DIR/pre-merge-check.sh"
```

**脚本位置**：所有脚本位于 `../dd-ai-git-workflow/scripts/` 子目录下（相对于本技能目录）。可直接执行 `bash <脚本路径>` 或通过 alias 调用。

## Git 2.55+ 推荐配置

```bash
# 大仓库性能优化：启用 fsmonitor（Linux via inotify / macOS / Windows）
git config core.fsmonitor true
git config core.untrackedCache true

# 配置式 hooks 并行执行（git 2.55+），加速 pre-commit
# 示例：linter 与单元测试并行跑
git config hook.pre-commit.command "swiftlint lint --strict"
git config hook.pre-commit.command "scripts/ci/test-unit.sh"
git config hook.pre-commit.parallel true
```

## 输出格式规范

所有自动化脚本输出 JSON，便于其他 skill 解析引用。

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

JSON 是脚本的权威输出格式，调用方（AI Agent、CI、其他 skill）可基于 JSON 自行渲染 Markdown 报告。

## 禁止事项

- Merge 前不测试
- **禁止用 `--ff-only` 替代功能合并**：功能合并必须 `--no-ff` 保留分支历史
- **禁止跳过 AI 自检直接合并**：合并前必须运行 `pre-merge-check.sh`
- **禁止自动清理未确认分支**：清理脚本仅输出建议，必须用户确认
- **禁止用固定 sleep 掩盖合并竞态**：合并冲突必须显式解决

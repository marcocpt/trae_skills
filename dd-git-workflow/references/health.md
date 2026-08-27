> 迁移来源：`dd-git-health/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# Git 分支健康度监控

## 概述

分支健康度监控帮助 AI Agent 量化分支状态，避免长分支导致的冲突指数增长。本技能涵盖四类指标、评分模型和每日同步。完整工作流总览见 [dd-git-workflow](../../dd-git-workflow/SKILL.md)。

本技能按 `invocation_mode=helper` 返回调用方，不自行 Host Close。直接承接用户目标时由顶层 `standalone` 会话按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 收尾。

## 四类指标

| 指标 | 含义 | 数据来源 | 告警阈值 |
|------|------|---------|---------|
| 陈旧度 | 自最近一次与 develop 同步后的天数 | `git log --merges` | >1 天告警 |
| 冲突难度 | merge-tree 检测到的冲突文件数 | `git merge-tree --write-tree` | >5 文件告警 |
| 变更规模 | 分支相对 develop 的变更文件数 | `git diff --name-only` | >20 文件告警 |
| 可合并性 | merge-tree 是否成功 | `git merge-tree --write-tree` 退出码 | 失败告警 |

## 健康度评分模型

每类指标 0-100 分，总分加权平均：

| 指标 | 权重 | 评分公式 |
|------|------|---------|
| 陈旧度 | 30% | `max(0, 100 - stale_days × 20)` |
| 冲突难度 | 30% | `max(0, 100 - conflict_count × 15)` |
| 变更规模 | 20% | `max(0, min(100, 100 - (changed_files - 5) × 3))` |
| 可合并性 | 20% | 可合并=100，不可合并=0 |
| **总分** | 100% | 加权平均 |

## 健康度等级

| 总分 | 等级 | 建议动作 |
|------|------|---------|
| ≥80 | 健康 | 正常合并 |
| 60-79 | 关注 | 同步 develop 后合并 |
| 40-59 | 警告 | 必须先解决冲突再合并 |
| <40 | 危险 | 立即干预，考虑拆分分支 |

## 检查频率

- **每日开工前**：运行健康度检查，确认分支状态
- **合并前必检**：合并到 develop 前必须运行，总分 <60 禁止合并
- **CI 触发**：PR 创建时自动运行

## 每日同步

"每天同步"升级为"每天必须合并"：AI Coding 场景下，分支每天必须有合并动作。

**含义**：

- **拉取上游**：`git fetch origin && git merge origin/develop` 同步上游改动
- **推送可合并部分**：将已完成且通过自检的部分合并回 develop

**为什么"必须合并"而不只是"同步"**：

- 同步只拉取上游，不回馈下游，分支仍然是单向流动
- 必须合并强制 AI Agent 把可合并的成果及时回到主干，避免分支长期独立
- 长分支即使每天同步，冲突也会随分支存活时间指数增长

**每日同步脚本**：`scripts/daily-sync.sh`

```bash
# 用法：在 feature 分支上执行
bash scripts/daily-sync.sh
# 冲突时输出冲突文件清单并以退出码 2 退出
```

### 触发时机

新分支不设置 upstream（不 tracking develop），但 Agent 必须在以下时机主动调用 `daily-sync.sh` 同步 develop 改动到当前 feature 分支：

- **进入 worktree 开始工作前**：Agent 切入 worktree 准备编码前，先跑 `daily-sync.sh`，避免基于过期的 develop 工作
- **push 前**：执行 `git push` 推送 feature 分支前，先跑 `daily-sync.sh`，避免推送落后于 develop 的分支
- **每日开工**：每日首次进入工作流时，运行健康度检查 + `daily-sync.sh`

冲突时（退出码 2）按 [dd-git-workflow/conflict](../../dd-git-workflow/references/conflict.md) 流程处理，禁止在 develop 上直接解决。

## branch-health.sh 用法

**健康度检查脚本**：`scripts/branch-health.sh`

```bash
# 用法：输出 BranchHealthReport JSON
bash scripts/branch-health.sh [base-branch]
```

### BranchHealthReport 输出示例

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

调用方可基于 `grade` 字段判断处理策略：`dangerous` 时必须提示干预，`watch` 时提示同步 develop。

## 禁止事项

- 长期未同步 develop 的分支（超过 1 天未合并视为陈旧）
- 跳过健康度检查直接合并（总分 <60 禁止合并）
- 忽视陈旧度告警（>1 天即触发告警，需立即执行每日同步）

## 被其他 skill 引用方式

### 语义触发

其他 skill 通过 description 字段语义触发本技能：

- `dd-git-workflow/ci`：合并前检查涉及健康度评估时引用
- `dd-feature-development-workflow`：功能开发流程涉及每日同步时引用
- `dd-bug-fix-workflow`：bug 修复流程涉及分支健康监控时引用
- `dd-git-workflow delivery`：分支收尾涉及健康度确认时引用

### 输出引用

其他 skill 可读取本技能输出的结构化数据：

- `BranchHealthReport.grade` 为 `dangerous` 时，调用方必须提示干预
- `BranchHealthReport.scores.total` < 60 时，调用方必须阻止合并
- `BranchHealthReport.warnings` 非空时，调用方可提示用户执行每日同步

---
name: dd-bug-fix-workflow
description: 修复需要隔离环境和 TDD 方法的 bug 时使用，或用户提到"修bug流程"、"bug fix workflow"时使用。
---

# Bug 修复工作流

## 概述

8 步严格顺序工作流：需求确认 → 隔离环境 → TDD 调试 → 代码同步(含提交) → 确认是否继续 → 文档检查 → Lint与Push → 合并清理。每步必须在前一步成功后才能继续。

## 何时使用

- 修复 bug 且需要隔离环境
- 用户提到"修bug流程"或"bug fix workflow"
- 需要系统化调试而非快速修补

**不适用：** 简单文本修改、新功能开发、纯文档修改

## 流程

```dot
digraph bug_fix_workflow {
    rankdir=TB;
    node [shape=box];
    "0. 需求确认" -> "1. 创建工作树";
    "1. 创建工作树" -> "2. TDD 调试修复";
    "2. TDD 调试修复" -> "3. 代码同步";
    "3. 代码同步" -> "3.3.5 CI 回归验证";
    "3.3.5 CI 回归验证" -> "4. 确认是否继续";
    "4. 确认是否继续" -> "5. 文档检查" [label="继续"];
    "4. 确认是否继续" -> "1. 创建工作树" [label="回到1", style=dashed];
    "4. 确认是否继续" -> "2. TDD 调试修复" [label="回到2", style=dashed];
    "5. 文档检查" -> "6. Lint 与 Push";
    "6. Lint 与 Push" -> "7. 合并清理";
    "7. 合并清理" -> "7.1 合并后CI验证";
    "7.1 合并后CI验证" -> "0. 需求确认" [label="还有其他问题", style=dashed];
}
```

<HARD-GATE>
严格按 0→1→2→3→4→5→6→7 顺序执行。禁止跳步、禁止省略步骤、禁止并行执行不同步骤。步骤 4 可回到步骤 1 或 2 重新执行。
</HARD-GATE>

## 上下文恢复机制

会话上下文压缩后可能遗忘当前 worktree 路径、`BASE_BRANCH`、`FIX_BRANCH` 等关键状态。通过**状态文件持久化**解决。

### 状态文件位置

`$(git rev-parse --git-dir)/bug-fix-state.json`

存放在 git dir（worktree 私有目录）下，不被 `git status` 检测。每个 worktree 拥有独立状态文件，支持多会话并行开发。

### 状态文件内容

```json
{
  "workflow_type": "bug-fix",
  "worktree_path": "/absolute/path/to/worktree",
  "base_branch": "main",
  "fix_branch": "fix/xxx",
  "main_root": "/absolute/path/to/main/repo",
  "worktree_dir": "/absolute/path/to/project-worktrees",
  "current_step": "2",
  "created_at": "2026-06-28T10:00:00Z"
}
```

### 恢复流程

每个步骤开始前，若不确定当前工作上下文，执行以下恢复：

```bash
git_dir=$(git rev-parse --git-dir)
state_file="$git_dir/bug-fix-state.json"

if [ -f "$state_file" ]; then
    # 读取并恢复关键变量
    WORKTREE_PATH=$(python3 -c "import json; print(json.load(open('$state_file'))['worktree_path'])")
    BASE_BRANCH=$(python3 -c "import json; print(json.load(open('$state_file'))['base_branch'])")
    FIX_BRANCH=$(python3 -c "import json; print(json.load(open('$state_file'))['fix_branch'])")
    MAIN_ROOT=$(python3 -c "import json; print(json.load(open('$state_file'))['main_root'])")
    WORKTREE_DIR=$(python3 -c "import json; print(json.load(open('$state_file'))['worktree_dir'])")

    # 切换到工作树目录
    cd "$WORKTREE_PATH"
else
    echo "未找到状态文件，可能尚未创建工作树或已清理"
fi
```

### 写入时机

- **写入**：步骤 1（工作树创建/验证成功后）
- **更新 `current_step`**：每完成一个步骤，更新此字段
- **删除**：步骤 7 清理工作树前先删除（须在离开 worktree 前执行，此时 `git-dir` 指向 worktree 私有目录）

> **全局会话规则**：本工作流所有步骤中涉及用户决策的问题（步骤 0 三次询问、步骤 2 失败询问、步骤 3.1 变基选择/冲突失败、步骤 3.2 失败、步骤 3.4 同步选择/失败、步骤 4 是否继续、步骤 5 各失败点、步骤 6 各失败点、步骤 7 合并选择等）**都必须使用当前环境可用的结构化询问工具给出选项**。在 Trae 中使用 `AskUserQuestion`；在 Codex 中使用 `request_user_input`（如可用）或带清晰选项的简短文本问题。不得用无选项的纯文本提问中断会话。

> **null 输入重问**：调用 `AskUserQuestion` 后，若返回结果为 null（含空值、空字符串、用户取消、未选择任何选项），视为未获取有效决策。必须以原问题重新询问用户，重复直到获取有效输入，不得自行假设默认值继续。

---

## 步骤 0：需求确认

### 0.1 前置准备：先获取日志候选

进入步骤 0 立即扫描两个 logs 目录，拿到最新文件信息（不询问用户）：

```bash
# 计算 worktree_dir（基于主仓库，避免在 worktree 内调用时识别错误）
common_dir=$(git rev-parse --git-common-dir)
main_root=$(cd "$(dirname "$common_dir")" && pwd)
project=$(basename "$main_root")
worktree_dir=$(dirname "$main_root")/${project}-worktrees

# 扫描 AI-test logs（按修改时间倒序）
ls -t "$worktree_dir/AI-test/logs/" 2>/dev/null | head -5

# 扫描当前 worktree logs（按修改时间倒序）
ls -t "$(pwd)/logs/" 2>/dev/null | head -5
```

- 合并文件列表，标注来源与修改时间
- 目录不存在或为空则跳过该来源

### 0.2 连续提问（一次性集中问完）

**AskUserQuestion 问 1：理解确认**

复述 bug 现象/复现条件/期望行为供用户确认。

- 选项 1（推荐）：确认理解正确
- 选项 2：需要补充细节
- 选项 3：理解有误，重新描述

**AskUserQuestion 问 2：工作环境**
- 选项 1（推荐）：新建隔离工作树
- 选项 2：在当前 worktree 工作

**AskUserQuestion 问 3：日志来源（动态选项）**
基于 0.1 扫描结果填充：
- 选项 1（推荐）：AI-test: `<最新文件名>`（`<修改时间>`）
- 选项 2：当前: `<最新文件名>`（`<修改时间>`）
- 选项 3：无日志，跳过日志获取
- 选项 4：其他文件（用户自行输入路径）

### 0.3 处理用户选择

- **问 1** → 理解偏差则重新描述，循环直到确认
- **问 2** → 决定步骤 1 是否创建工作树。**选中工作环境后，后续所有工作都在选中的工作树中执行**
- **问 3** → 读取对应日志，提取错误信息/警告/异常堆栈，作为步骤 2 调试依据

**不调用 brainstorming**：bug 修复是定位+修复问题，无需规格化设计文档与实现计划。

- 用户选"新建" → 步骤 1 走完整创建流程
- 用户选"当前 worktree" → 步骤 1 仅做验证

---

## 步骤 1：创建工作树

### 1.1 若步骤 0 选"当前 worktree"

跳过创建，仅做验证：

```bash
# 并发检查：禁止同一 worktree 上同时运行多个工作流
git_dir=$(git rev-parse --git-dir)
for f in "$git_dir"/bug-fix-state.json "$git_dir"/feature-development-state.json; do
  if [ -f "$f" ]; then
    existing_type=$(python3 -c "import json; print(json.load(open('$f')).get('workflow_type','unknown'))")
    echo "❌ 当前 worktree 已有活跃的 ${existing_type} 工作流，禁止并发"
    exit 1
  fi
done

# 记录基线分支
BASE_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 验证工作区状态
git status  # 必须干净，有未提交变更需先处理

# 验证基线测试（按 test-location-strategy skill 决策测试位置）
# 1. 检查基线 commit 的 CI 已有结果（commit 一致即可复用）：
#    - 先查当前分支：gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1
#    - 当前分支无远端或无结果时，必须再查 BASE_BRANCH：gh run list --workflow macos-ci.yml --branch <BASE_BRANCH> --limit 1
#    - 任一返回 conclusion=success 且 headSha==当前工作树 HEAD → 复用 CI 结果，跳过本地测试
#    - status=in_progress → 等待 CI 完成，不重复触发
# 2. 触发 CI（无可用结果且当前分支已 push 时）：gh workflow run macos-ci.yml --ref <当前分支> && gh run watch <run-id> --exit-status
#    - 当前分支未 push 时不得降级本地——先查 BASE_BRANCH 已有结果，或 AskUserQuestion 询问是否 push
# 3. 本地测试（仅在 1.2.7 红线明示条件满足时）：bash scripts/ci/test-macos.sh（与 CI 同脚本）
```

- 成功标准：工作区干净 + 基线测试通过
- 失败：报错并停止

**写入状态文件**（验证成功后）：

```bash
common_dir=$(git rev-parse --git-common-dir)
main_root=$(cd "$(dirname "$common_dir")" && pwd)
project=$(basename "$main_root")
worktree_dir=$(dirname "$main_root")/${project}-worktrees
git_dir=$(git rev-parse --git-dir)

cat > "$git_dir/bug-fix-state.json" <<EOF
{
  "workflow_type": "bug-fix",
  "worktree_path": "$(pwd)",
  "base_branch": "$BASE_BRANCH",
  "fix_branch": "$(git rev-parse --abbrev-ref HEAD)",
  "main_root": "$main_root",
  "worktree_dir": "$worktree_dir",
  "current_step": "1",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
```

### 1.2 若步骤 0 选"新建"

#### 1.2.1 记录基线分支

```bash
BASE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

#### 1.2.2 计算工作树路径

基于主仓库位置计算（避免在 worktree 内调用时项目名识别错误）：

```bash
common_dir=$(git rev-parse --git-common-dir)
main_root=$(cd "$(dirname "$common_dir")" && pwd)
project=$(basename "$main_root")
worktree_dir=$(dirname "$main_root")/${project}-worktrees
```

**关键**：必须基于主仓库，而非当前工作树——否则项目名会被误识别为分支名，导致工作树目录嵌套。

#### 1.2.3 创建工作树

```bash
BRANCH="fix/<简短描述>"
path="$worktree_dir/$BRANCH"
git worktree add "$path" -b "$BRANCH"
cd "$path"
```

#### 1.2.4 运行项目设置

自动检测并运行相应设置命令：

```bash
# Node.js
[ -f package.json ] && npm install

# Rust
[ -f Cargo.toml ] && cargo build

# Python
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f pyproject.toml ] && poetry install

# Go
[ -f go.mod ] && go mod download

# Swift (Xcode 项目)
[ -f Package.swift ] && swift build
```

#### 1.2.5 验证基线测试干净

按 test-location-strategy skill 决策测试位置。**基线验证的语义是确认起点 commit 干净**——起点 = BASE_BRANCH 的 HEAD（步骤 1.2.1 已记录）。新创建的 fix 分支尚未 push，远端无此分支，此时**必须**查 BASE_BRANCH 的 CI 结果，因为工作树 HEAD 等于 BASE_BRANCH HEAD，基线 commit 已有成功 CI 证据即满足复用条件。

1. **检查基线 commit 的 CI 已有结果**（按优先级检索，commit 一致即可复用）：
   - 先查当前分支：`gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1`
   - 当前分支无远端或无结果时，**必须**再查 BASE_BRANCH：`gh run list --workflow macos-ci.yml --branch <BASE_BRANCH> --limit 1`
   - 任一查询返回 `conclusion=success` 且 `headSha` 等于当前工作树 HEAD → 复用 CI 结果（记录复用来源分支与 run ID），跳过本地测试
   - `status=in_progress` → 等待 CI 完成，不重复触发
2. **触发 CI**（无可用结果且当前分支已 push 时）：`gh workflow run macos-ci.yml --ref <当前分支>` + `gh run watch <run-id> --exit-status`
   - **当前分支未 push 时不得以此为由降级本地**——按 1.2.7 红线处理（先查 BASE_BRANCH 已有结果，或用 AskUserQuestion 询问是否 push 后触发 CI）
   - `gh workflow run` 本身报错（ref 不存在、鉴权失败等）→ 按 test-location-strategy 步骤 2 的 AskUserQuestion 流程处理，**不得降级本地**
3. **本地测试**（仅在满足 1.2.7 红线明示条件时）：`bash scripts/ci/test-macos.sh`（与 CI 同脚本，基于 xcodebuild test + Macim.xcworkspace + MacimApp scheme）。禁止用 `swift test` 替代——本项目是 Xcode 工程，`swift test` 只覆盖 SwiftPM 子集。

- 测试失败：报告失败情况，询问是否继续或排查
- 测试通过：报告就绪

#### 1.2.6 报告位置

```
工作树已就绪：<full-path>
测试通过（<N> 个测试，0 个失败）
准备实现 <feature-name>
```

**重要**：调用后会话工作目录必须始终位于该工作树路径下，不得切换回主仓库目录。

#### 1.2.7 红线

**绝不：**
- 跳过基线测试验证
- 不询问就带着失败的测试继续
- 在项目内部创建工作树目录（污染 git status）
- **以"当前分支未 push 导致 CI 触发失败"为由降级本地测试**——必须先查 BASE_BRANCH 的 CI 结果（基线 commit 与 BASE_BRANCH HEAD 相同）；若 BASE_BRANCH 也无结果，用 AskUserQuestion 询问是否 push 后触发 CI，不得直接降级本地
- **以"CI 不可用"宽泛措辞降级本地**——"CI 不可用"仅指：项目无 `.github/workflows/` 配置、`gh` 命令不可用且用户选择不修复、用户在**无可用 CI 结果**时明确选择本地。分支未 push、`gh workflow run` 报错、CI 触发失败**均不构成"CI 不可用"**
- **以"用户明确要求"凌驾于 CI 优先之上**——当已有可复用的成功 CI 结果时，用户要求本地不构成降级理由；应用 AskUserQuestion 给出"复用 CI 结果（推荐）/ 仍要本地仅作参考 / 终止"选项
  - **触发时机**：若 agent 已按步骤 1 确定复用（commit 一致 + conclusion=success），可直接复用并告知用户，无需 AskUserQuestion；AskUserQuestion 仅在 agent 考虑接受用户本地请求时强制触发（即 agent 在"复用 CI"与"本地执行"之间犹豫时，必须用 AskUserQuestion 让用户显式选择，不得沉默降级本地）

> **与 3.3 红线的关系**：3.3 节"分支未 push 时必须先 push 再等待 CI，禁止落到本地测试""CI 触发失败不构成走本地测试的理由"同样适用于本步骤——基线验证与回归验证在"CI 优先"上标准一致，不得在 1.2.5 阶段降级。
>
> **1.2.5 与 3.3 的表面张力说明**：1.2.5"可复用 BASE_BRANCH 的 CI 结果"与 3.3"分支未 push 时必须先 push"并不冲突——3.3 的"必须先 push"针对**回归验证**（步骤 3 提交后的新 commit 需新 CI 运行）；1.2.5 的"可复用 BASE_BRANCH"针对**基线验证**（步骤 1 的起点 commit 已有 CI 证据，无需新运行）。两者场景不同，不得混淆。

#### 1.2.8 写入状态文件

工作树创建并验证成功后，持久化关键状态供上下文恢复：

```bash
git_dir=$(git rev-parse --git-dir)

cat > "$git_dir/bug-fix-state.json" <<EOF
{
  "workflow_type": "bug-fix",
  "worktree_path": "$(pwd)",
  "base_branch": "$BASE_BRANCH",
  "fix_branch": "$(git rev-parse --abbrev-ref HEAD)",
  "main_root": "$main_root",
  "worktree_dir": "$worktree_dir",
  "current_step": "1",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
```

---

## 步骤 2：TDD 调试修复

### 2.1 第一步：编写失败测试（TDD 红灯）

**目标：用测试用例稳定复现问题。**

- 阅读步骤 0 获取的日志，确认复现条件（输入、环境、前置状态）
- 编写最小复现测试（只测一件事，使用真实代码，避免不必要 mock）
- 验证因正确原因失败（失败信息反映功能缺失，非拼写错误）
- 测试通过？说明测了已有行为，需修改测试
- 记录到日志文件：`debug-logs/YYYY-MM-DD-<简短问题描述>.md`

### 2.2 第二步：系统化调试（根因调查）

**铁律：不做根因调查，不许提修复方案。**

- **收集证据**：完整阅读错误信息与堆栈跟踪、稳定复现问题、检查近期变更（git diff、最近提交）、多组件系统对组件边界添加诊断埋点
- **跟踪数据流**：错误值从哪里产生？谁用错误值调用了这里？持续向上追踪直到找到源头
- **模式分析**：找到同一代码库中正常工作的类似代码，逐行对比，列出每一个差异
- **假设与验证**：提出单一假设"X 是根本原因，因为 Y"，做最小改动验证，每次只改一个变量；生效 → 进入修复；没生效 → 提出新假设
- **调试期间可添加诊断日志辅助排查**：关键变量值、坐标转换前后对比、条件分支走向等，日志带功能标签前缀（如 `[F1.10]`）便于检索和清理
  - 与步骤 3.2 正式运行日志区别：此处为临时诊断，验证假设后可移除
- 记录到日志文件：错误信息/复现步骤/近期变更/数据流/假设验证/根本原因

### 2.3 第三步：实施修复（TDD 绿灯）

**目标：修复根本原因，让测试通过。**

- 实施单一修复（每次只改一处，不做"顺便改改"的优化，不捆绑重构）

**验证分两层，必须严格区分：**

1. **单测试文件绿灯验证**（本地执行，TDD 快速反馈）：仅运行步骤 2.1 编写的新测试，确认因修复而通过。此时代码未提交，无法触发 CI，本地执行是唯一选项
2. **全量回归验证**（**步骤 3 提交后**按 `test-location-strategy` skill 走 CI 优先）：运行项目完整测试套件，确认修复未破坏其他测试。**禁止在步骤 2 中直接本地跑全量回归——必须延迟到步骤 3 提交后走 CI 验证**

> **为什么不能在步骤 2 本地跑全量回归？** 步骤 2 代码未提交，无法 push 触发 CI。即使本地通过，CI 环境差异（签名、SDK 版本、runner 配置）可能掩盖问题。步骤 3 提交后补走 CI 是唯一的可靠验证点。

- **回归测试失败需修改时**：必须使用 `AskUserQuestion` 说明失败原因和修改理由，获得用户确认后方可修改。禁止未经确认直接修改回归测试
- 如果修复不起作用：
  - 少于 3 次：回到根因调查，用新信息重新分析
  - 3 次或以上：停下来质疑架构 → **AskUserQuestion**：
    - 选项 1（推荐）：继续调试（回到根因调查）
    - 选项 2：放弃并清理工作树
- 记录到日志文件：修复方案/修改文件/单测试绿灯结果/全量回归延迟到步骤 3.3.5

### 2.4 第四步：重构（TDD 重构）

**目标：在绿灯基础上清理代码。**

- 消除重复
- 改善命名
- 提取辅助函数
- 保持测试绿灯，不添加行为

### 2.5 调试日志文件规范

- **位置**：项目根目录 `debug-logs/`
- **命名**：`YYYY-MM-DD-<简短问题描述>.md`
- **内容**：问题描述 / [前置] 步骤0 获取的运行日志信息 / [红灯] 测试用例 / [根因调查] 调查过程 / [绿灯] 修复实施 / 总结

### 2.6 出口判定

- 成功（绿灯 + 重构完成）→ 进入步骤 3
- 失败（3 次以上修复无效）→ AskUserQuestion（见 2.3）

---

## 步骤 3：代码同步

### 3.1 变基到 BASE_BRANCH 并解决冲突

#### 3.1.1 前置检查：对比本地与远端 BASE_BRANCH 新旧

```bash
# 精确拉取 BASE_BRANCH
git fetch origin "$BASE_BRANCH"

LOCAL_SHA=$(git rev-parse "$BASE_BRANCH")
REMOTE_SHA=$(git rev-parse "origin/$BASE_BRANCH")

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    # 本地与远端一致，无需变基
    SKIP_REBASE=true
elif git merge-base --is-ancestor "$LOCAL_SHA" "$REMOTE_SHA"; then
    # 远端更新，推荐 rebase 到 origin/<BASE_BRANCH>
    RECOMMEND="origin/$BASE_BRANCH"
else
    # 本地更新，推荐 rebase 到 <BASE_BRANCH>
    RECOMMEND="$BASE_BRANCH"
fi
```

- `SKIP_REBASE=true`（本地与远端一致）→ **跳过 3.1.2**，直接进入 3.2
- 否则进入 3.1.2 询问变基策略（`$RECOMMEND` 为推荐目标）

#### 3.1.2 询问变基策略（仅当需要变基时）

**AskUserQuestion 问 1**：
- 选项 1（推荐）：变基到较新的一方（自动判定本地/远端）
- 选项 2：变基到 `origin/<BASE_BRANCH>`（强制远端）
- 选项 3：变基到 `<BASE_BRANCH>`（强制本地）
- 选项 4：不变基，跳过本子步

#### 3.1.3 执行变基

选择变基时：

```bash
git rebase <目标分支>
```

**冲突处理流程**：
1. `git status` 查看冲突文件列表
2. 手动逐个文件解决冲突（保留正确逻辑、删除冲突标记 `<<<<<<<` `=======` `>>>>>>>`）
3. `git add <已解决文件>` 标记冲突已解决
4. `git rebase --continue` 继续 rebase
5. 若有多个冲突 commit，重复步骤 1-4
6. **成功标准**：`git status` 显示 `rebase in progress` 已结束，无冲突文件

**冲突无法解决** → **AskUserQuestion 问 2**：
- 选项 1（推荐）：`git rebase --abort` 中止，回到步骤 2 在 BASE_BRANCH 最新代码上重新修复
- 选项 2：继续手动解决冲突（提供具体冲突位置和上下文）
- 选项 3：放弃本次修复，清理工作树

**禁止**：强制 `--no-edit` 跳过冲突处理、使用 `git rebase --skip` 丢弃提交

### 3.2 添加详细日志与文档

**流程图和时序图通过子代理生成**：调度子代理，传入修复涉及的代码路径和变更摘要，由子代理生成流程图和时序图。日志添加在主线程完成（需结合调试上下文）。

#### 3.2.1 给相关代码添加详细 log

- 关键变量值、状态变更、条件分支走向
- 日志带功能标签前缀（如 `[F1.10]`）便于检索
- 与步骤 2 临时诊断日志区别：此处为修复后的**正式运行日志**，保留在代码中用于运行时观察

#### 3.2.2 编写流程图

- 描述修复涉及的代码执行流程
- 标注关键节点与分支条件

#### 3.2.3 编写时序图

- 描述修复涉及的组件交互顺序
- 标注关键消息与状态转换

**成功标准**：log 已添加，流程图与时序图已编写

**失败** → **AskUserQuestion 问 3**：
- 选项 1（推荐）：重试
- 选项 2：跳过继续
- 选项 3：停止工作流

### 3.3 提交变更

无论是否变基，均提交当前变更（含代码 + 日志 + 文档）。

#### 3.3.1 分析 diff

```bash
# 有暂存时
git diff --staged

# 无暂存时
git diff

# 查看状态
git status --porcelain
```

#### 3.3.2 智能暂存

```bash
# 按逻辑分组暂存
git add path/to/file1 path/to/file2

# 或按模式
git add *.test.*
git add src/components/*
```

**禁止提交敏感文件**：`.env`、`credentials.json`、私钥等。

#### 3.3.3 生成 Conventional Commits 消息

格式：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

类型表：

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting/style (no logic) |
| `refactor` | Code refactor (no feature/fix) |
| `perf` | Performance improvement |
| `test` | Add/update tests |
| `build` | Build system/dependencies |
| `ci` | CI/config changes |
| `chore` | Maintenance/misc |
| `revert` | Revert commit |

- 描述：现在时 + 命令式，<72 字符
- 引用 issue：`Closes #123`、`Refs #456`

#### 3.3.4 执行提交

```bash
# 单行
git commit -m "<type>[scope]: <description>"

# 多行
git commit -m "$(cat <<'EOF'
<type>[scope]: <description>

<optional body>

<optional footer>
EOF
)"
```

**Git 安全协议**：
- 禁止更新 git config
- 禁止 `--force`、hard reset（除非用户明确要求）
- 禁止 `--no-verify` 跳过 hooks（除非用户要求）
- 禁止 force push 到 main/master
- hooks 失败 → 修复后新建 commit，不 amend

**成功** → 进入 3.3.5

**失败** → 回到步骤 2 修复问题，不跳过

#### 3.3.5 提交后全量回归验证（CI 优先，必须 push）

**本步是步骤 2.3 延迟的全量回归验证的唯一执行点。代码已提交，必须 push 到远端触发 CI 验证。**

**核心原则**：本步的验证必须由远端 CI 完成。**禁止在本地执行测试作为 CI 的替代**——本地环境差异（签名、SDK、runner 配置）会掩盖问题，CI 是工作流核心价值。

按以下顺序执行（不得跳步、不得跳过本地测试兜底）：

1. **检查分支是否已 push 到远端**：
   ```bash
   CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" >/dev/null 2>&1
   ```
   - **退出码 0**（远端已有此分支）→ 进入步骤 2 检查 CI 已有结果
   - **退出码非 0**（远端无此分支，新建分支未 push）→ **必须先 push**：
     ```bash
     git push -u origin "$CURRENT_BRANCH"
     ```
     - push 成功 → 进入步骤 2
     - push 失败 → **AskUserQuestion**：
       - 选项 1（推荐）：重试 push（排查网络/权限问题）
       - 选项 2：停止工作流，排查 push 权限
     - **禁止**：以 push 失败为由落到本地测试

2. **检查 CI 已有结果**（分支已 push 到远端后）：`gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1`
   - `conclusion=success` 且 `headSha` 等于当前 HEAD → 复用 CI 结果，进入 3.4
   - `status=in_progress` → 等待 CI 完成，不重复触发

3. **触发 CI 并等待结果**（无可用 CI 结果时）：
   ```bash
   gh workflow run macos-ci.yml --ref <当前分支>
   # 等 GitHub 注册新触发的 run
   sleep 5
   RUN_ID=$(gh run list --workflow macos-ci.yml --branch <当前分支> --limit 5 \
     --json databaseId,headSha \
     --jq ".[] | select(.headSha == \"$(git rev-parse HEAD)\") | .databaseId" | head -1)
   gh run watch "$RUN_ID" --exit-status
   ```
   - **触发失败** → **AskUserQuestion**：
     - 选项 1（推荐）：重试触发 CI
     - 选项 2：停止工作流，排查 CI 配置
   - **禁止**：以 CI 触发失败为由落到本地测试

- **CI 通过** → 进入 3.4
- **CI 失败**（测试用例未通过）→ **AskUserQuestion**：
  - 选项 1（推荐）：拉取 CI 日志（`gh run view <run-id> --log-failed`）分析失败原因，回到步骤 2 修复
  - 选项 2：本地复现排查（`bash scripts/ci/test-macos.sh`，**仅用于理解失败原因，修复后必须重新走 CI 验证**）
  - 选项 3：跳过继续（不推荐）

> **红线**：
> - 不得跳过本步直接进入 3.4。步骤 2.3 的全量回归已延迟到此处，跳过等于放弃回归验证。
> - **分支未 push 时，必须先 push 再等待 CI，禁止落到本地测试**。本地测试不能作为 CI 的替代。
> - **CI 触发失败不构成走本地测试的理由**。应排查 CI 配置或重试，而非降级验证。

### 3.4 同步 AI-test 测试工作树

确保 AI-test 测试工作树复位到最新修复分支，便于测试验证最新代码。

**AskUserQuestion 问 4**：是否同步 AI-test 工作树
- 选项 1（推荐）：同步（使用 `reset --hard` 复位到最新修复分支）
- 选项 2：不同步，结束 3.4

选择同步时：

```bash
FIX_BRANCH=$(git rev-parse --abbrev-ref HEAD)
bash "$HOME/.trae-cn/skills/shared/scripts/sync-ai-test-worktree.sh" "$FIX_BRANCH" "$worktree_dir"
```

- **返回码 0**（成功）：AI-test 工作树 HEAD 等于当前修复分支最新 commit，工作区干净
- **返回码 2**（未提交变更）：AI-test 工作树存在未提交变更，询问用户处理方式
- **其他失败** → **AskUserQuestion 问 5**：
  - 选项 1（推荐）：重试
  - 选项 2：跳过继续
  - 选项 3：停止工作流

选择不同步 → 直接进入步骤 4

---

## 步骤 4：确认是否继续

在代码同步完成后、进入文档检查之前，询问用户是否需要回到早期步骤继续修复。

**AskUserQuestion**：
- 选项 1（推荐）：继续进入步骤 5 检查测试文档
- 选项 2：回到步骤 1 创建新工作树重新修复（当前工作树保留或清理由用户决定）
- 选项 3：回到步骤 2 重新 TDD 调试修复（在同一工作树中继续）

**分支处理**：
- 选"继续" → 进入步骤 5
- 选"回到步骤 1" → 跳转到步骤 1 重新执行，后续步骤顺序推进
- 选"回到步骤 2" → 跳转到步骤 2 重新执行，在同一工作树中继续，后续步骤顺序推进

---

## 步骤 5：检查测试文档

确保测试文档与代码变更保持一致。

**通过子代理分析**：`git diff` 输出 + 读设计规范/测试用例表/代码，token 量大。调度子代理，传入 `BASE_BRANCH`、功能编号和文档路径，由子代理完成变更分析（5.2）、文档检查（5.3-5.6）和摘要输出（5.7）。

### 5.1 读取测试规则

先阅读 `docs/AI/trae-xctest-rules.md`，严格遵守其中的测试和回归规则。重点关注：
- 第 4 节：什么时候新增或更新回归测试
- 第 6 节：变更影响分析规范
- 第 14 节：AI 输出格式

- **成功**：规则文件存在且已读取 → 进入 5.2
- **失败**：规则文件不存在 → 报错并停止，提示用户确认路径
- **边界**：规则文件存在但缺少第 4/6/14 节 → 按现有内容执行，并在 5.7 自检中标注规则不完整

### 5.2 识别变更并输出影响分析

```bash
# 获取当前分支相对于基线分支的所有变更
git diff "$BASE_BRANCH"...HEAD
# 或
git log --oneline "$BASE_BRANCH"..HEAD
```

分析变更内容：
- 新增或修改的行为
- 直接修改的文件和符号
- 直接调用方与被调用方
- 共享模型、协议、配置、持久化格式
- 可能受影响的用户流程

按第 6 节规范输出变更影响分析表：

```markdown
## 变更影响分析

| 分析项 | 内容 |
|---|---|
| 直接修改行为 | ... |
| 直接依赖 | ... |
| 间接依赖 | ... |
| 高风险路径 | ... |
| 必须新增的测试 | ... |
| 必须更新的测试 | ... |
| 必须执行的测试 | ... |
| 可暂缓自动化 | ... |
```

表中「必须执行的测试」按 test-location-strategy skill 选择测试位置：自建服务器优先，无自建服务器才本地。

- **成功**：已获取变更并输出影响分析表
- **失败**：`git diff` 为空 → 提示"无代码变更，无需更新文档"，结束步骤 5

### 5.3 定位目标文档

根据用户在步骤 0 描述的修复功能，推断功能编号（如 F1.10），定位以下文档（路径模式为 `docs/planning/P0/{功能编号}/`）：

1. **设计规范**：`F{N}_*_设计规范.md`
2. **测试用例表**：`F{N}_*_测试用例表.md`

使用 `rg --files docs/planning/P0/{功能编号}` 搜索 `*设计规范*.md` 和 `*测试用例表*.md` 确认实际路径；如果 `rg` 不可用，使用 `find docs/planning/P0/{功能编号} -name '*设计规范*.md' -o -name '*测试用例表*.md'`。

- **成功**：至少定位到一份目标文档 → 进入 5.4
- **失败**：功能编号对应目录不存在 → **AskUserQuestion 问 2**：
  - 选项 1（推荐）：新建目录
  - 选项 2：重新输入功能编号
  - 选项 3：终止
- **边界**：只找到一份文档 → 对缺失的另一份在对应 5.4/5.5 中标注"文档不存在，跳过"
- **无法推断功能编号** → **AskUserQuestion 问 1**：询问用户功能编号

### 5.4 检查设计规范是否需要更新

对照最近代码变更，逐项检查设计规范：

1. **验收标准（AC）**：新增或修改的行为是否需要新增/修改验收标准
2. **行为描述**：代码实现的行为是否与规范描述一致
3. **数据模型**：新增/修改的属性或方法是否需要在规范中记录
4. **状态机**：状态转换是否有变化
5. **当前问题**：已修复的问题是否需要从"当前问题"中移除

如果需要更新，直接修改设计规范文件，并更新版本号和最后更新日期。

### 5.5 检查测试用例表是否需要更新

对照最近代码变更和设计规范，逐项检查测试用例表：

1. **新增用例**：新增行为是否需要新增测试用例行
2. **状态更新**：已有用例的状态是否需要从 ❌/🟡 更新为 ✅
3. **现有证据**：新增的测试方法是否需要补充到"现有证据"列
4. **补充用例**：已实现的补充用例是否需要更新
5. **AC 映射**：新增用例是否需要关联到设计规范的验收标准编号
6. **统计更新**：更新文档头部的统计数字（总用例数、✅/🟡/❌/⏸️ 数量）

**测试用例表格式约定**：
- `#` 列：用例编号，保留历史编号；新增追加到对应分组末尾
- `状态` 列：✅ 已有测试能证明该行为；🟡 已有测试只覆盖部分断言；❌ 缺少可执行自动化；⏸️ 暂缓自动化
- `AC` 列：对应设计规范验收标准编号；`支撑` 表示不直接对应 AC
- 新增 bug 修复用例使用 C 系列编号，追加到 C 分组末尾

如果需要更新，直接修改测试用例表文件，并更新版本号和最后更新日期。

### 5.6 检查代码中测试用例是否需要更新

> **调用上下文**：本工作流调用，步骤 2 的 TDD 已为新增行为写过测试，本步跳过"新增行为缺少测试覆盖"检查，仅保留以下三项检查。

1. 搜索最近变更涉及的行为在测试代码中的覆盖情况
2. 检查是否有以下问题：
   - 已有测试的断言需要更新（因为行为变更）
   - 测试名称不符合 `test_入口点_场景_期望行为` 命名规范
   - 测试替身（Stub/Mock/Spy）需要更新
3. 如果需要新增或修改测试代码，按照 `docs/AI/trae-xctest-rules.md` 的规范生成测试代码

### 5.7 输出文档更新摘要与自检

按照第 14 节格式输出（变更影响分析表已在 5.2 输出，此处不重复）：

```markdown
## 文档更新摘要

- 设计规范：[已更新 / 无需更新] — 原因
- 测试用例表：[已更新 / 无需更新] — 原因
- 代码测试：[已更新 / 无需更新] — 原因

## 自检结果

- 测试失败时是否说明生产行为有问题？
- 是否存在网络、时间、随机数、顺序或本机环境依赖？
- 是否绑定内部实现？
- 是否过度 Mock？
- 是否遗漏受影响的旧行为？
- 是否错误修改了旧测试预期？
- 是否适合进入 CI？
```

### 5.8 重要约束

1. **不得仅根据修改文件列表决定回归范围**：必须结合调用关系、数据流、共享模型、配置、持久化格式和用户流程判断
2. **不得为了让测试通过而随意修改旧测试预期**：必须先确认需求是否真的改变
3. **文档版本号递增**：每次更新设计规范或测试用例表时，必须递增版本号

### 5.9 出口判定

- 完成或无需更新 → 进入步骤 6
- 失败 → **AskUserQuestion 问 3**：
  - 选项 1（推荐）：重试
  - 选项 2：跳过继续进入步骤 6
  - 选项 3：停止工作流

---

## 步骤 6：Lint 与 Push

**流程顺序：lint → 测试验证 → push → 同步 AI-test，缺一不可。测试验证的测试位置按 test-location-strategy skill 选择。**

### 6.1 代码质量检查

**lint 部分**（本地执行，不使用自建服务器）：

按项目类型执行：

- **Swift 项目**：`swiftlint lint --strict`
- **其他项目**：项目对应的 lint / typecheck 命令

- **成功** → 进入 lint 后的测试验证
- **失败** → 修复 lint 错误后重新检查，不得跳过（循环直到通过）

**测试验证部分**（按 test-location-strategy skill 决策测试位置）：

lint 通过后，运行项目测试套件验证整体回归：

1. **检查 CI 已有结果**：`gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1`
   - `conclusion=success` 且 `headSha` 等于当前 HEAD → 复用 CI 结果，跳过本地测试
   - `status=in_progress` → 等待 CI 完成，不重复触发
2. **触发 CI**（无可用结果时）：`gh workflow run macos-ci.yml --ref <当前分支>` + `gh run watch <run-id> --exit-status`
3. **本地测试**（CI 不可用或用户明确要求）：`bash scripts/ci/test-macos.sh`（与 CI 同脚本，基于 xcodebuild test）。禁止用 `swift test` 替代。

- **成功** → 进入 6.2
- **失败** → 修复后重新执行 lint + 测试

### 6.2 Push 到远端

```bash
# 确认远端仓库存在
git remote -v

# 推送分支
# 无 upstream
git push -u origin <当前分支>

# 有 upstream
git push
```

- **成功** → 进入 6.3
- **失败** → **AskUserQuestion 问 1**：
  - 选项 1（推荐）：重试
  - 选项 2：跳过 push 继续
  - 选项 3：停止工作流

**禁止**：
- 使用 `git push --force` / `git push -f`（除非用户明确要求）
- 推送到 main/master（除非用户明确要求）

### 6.2.1 等待 CI 结果（push 后强制执行）

push 完成后必须等待 CI 运行完成，不得直接结束工作流或宣称完成。本步是新流程的核心：让远端 self-hosted runner 验证代码，避免本地环境差异掩盖问题。

```bash
# 等 GitHub 注册新 push
sleep 5

# 查找当前 SHA 对应的最新 run
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_SHA=$(git rev-parse HEAD)

RUN_ID=$(gh run list \
  --workflow "macos-ci.yml" \
  --branch "$CURRENT_BRANCH" \
  --limit 5 \
  --json databaseId,headSha \
  --jq ".[] | select(.headSha == \"${CURRENT_SHA}\") | .databaseId" \
  | head -1)

if [ -n "$RUN_ID" ]; then
  echo "Watching run ${RUN_ID}..."
  gh run watch "$RUN_ID" --exit-status
else
  echo "⚠️ 未找到对应 SHA 的 run，可能 CI 未触发或 workflow 文件不存在"
fi
```

- **成功** → 进入 6.3
- **CI 失败** → **AskUserQuestion 问 X**：
  - 选项 1（推荐）：拉取 CI 日志（`gh run view <run-id> --log-failed`）分析失败原因，回到步骤 2 修复
  - 选项 2：本地复现验证（`bash scripts/ci/test-macos.sh`）确认是代码问题还是 CI 环境问题
  - 选项 3：跳过继续（不推荐，会引入未验证代码到远端）
- **未找到 run** → **AskUserQuestion 问 X**：
  - 选项 1（推荐）：手动触发 `gh workflow run macos-ci.yml --ref <当前分支>` 后重新等待
  - 选项 2：本地测试 `bash scripts/ci/test-macos.sh` 作为替代验证
  - 选项 3：跳过继续

### 6.3 同步 AI-test 测试工作树

push 完成后再次同步 AI-test 工作树，确保其复位到最新修复分支（含远端 push 后的最终状态）。

**AskUserQuestion 问 2**：是否同步 AI-test 工作树
- 选项 1（推荐）：同步（使用 `reset --hard` 复位到最新修复分支）
- 选项 2：不同步，结束 6.3

选择同步时：

```bash
FIX_BRANCH=$(git rev-parse --abbrev-ref HEAD)
bash "$HOME/.trae-cn/skills/shared/scripts/sync-ai-test-worktree.sh" "$FIX_BRANCH" "$worktree_dir"
```

- **返回码 0**（成功）：AI-test 工作树 HEAD 等于当前修复分支最新 commit，工作区干净
- **返回码 2**（未提交变更）：AI-test 工作树存在未提交变更，询问用户处理方式
- **其他失败** → **AskUserQuestion 问 3**：
  - 选项 1（推荐）：重试
  - 选项 2：跳过继续
  - 选项 3：停止工作流

选择不同步 → 直接进入步骤 7

---

## 步骤 7：合并清理

**AskUserQuestion 问 1**：
- 选项 1：合并到原分支
- 选项 2：不合并，仅清理工作树
- 选项 3：还有其他问题（反馈新问题）
- 选项 4：暂不处理，保留工作树

### 7.1 选"合并到原分支"

**先删除状态文件**（在离开工作树前，此时 `git-dir` 指向 worktree 私有目录）：

```bash
git_dir=$(git rev-parse --git-dir)
rm -f "$git_dir/bug-fix-state.json"
```

```bash
# 以下命令必须在主仓库路径执行，不在修复 worktree 内执行
cd "$main_root"

# 变基到原分支最新
git rebase "$BASE_BRANCH" <工作树分支>

# 切回原分支并合并（保留合并记录）
git checkout "$BASE_BRANCH"
git merge --no-ff <工作树分支>
```

**合并后全量回归验证（CI 优先）**：合并产生新的 commit，必须验证合并后代码在 CI 中通过。按 `test-location-strategy` skill 决策测试位置：

1. **本地快速冒烟**（可选，快速检测合并冲突遗留）：仅编译检查（如 `swift build --package-path MacimCore`），**不替代全量测试**
2. **CI 全量验证**（**必需**）：
   - **已 push**：`gh run list --workflow macos-ci.yml --branch "$BASE_BRANCH" --limit 1` 查找对应 SHA 的 run，`gh run watch` 等待结果
   - **未 push**：先 `git push`，再等待 CI 结果（与步骤 6.2.1 相同流程）
3. **本地全量测试**（**仅当** CI 不可用或用户明确要求）

- **CI 通过** → 继续清理工作树
- **CI 失败** → **AskUserQuestion**：
  - 选项 1（推荐）：拉取 CI 日志分析，回到步骤 2 修复
  - 选项 2：`git merge --abort` 撤销合并，回到步骤 2
  - 选项 3：本地复现排查

> **红线**：合并后不得跳过 CI 验证直接清理工作树。合并可能引入基线变更冲突，CI 是唯一的跨环境验证。

清理工作树：删除工作树目录。

工作流结束。

### 7.2 选"不合并，仅清理工作树"

**先删除状态文件**（在离开工作树前）：

```bash
git_dir=$(git rev-parse --git-dir)
rm -f "$git_dir/bug-fix-state.json"
```

- 保留原分支不变
- 清理工作树：删除工作树目录

工作流结束。

### 7.3 选"还有其他问题"

- 接收用户提出的新问题描述
- **重新从步骤 0 开始**（需求确认 → 创建工作树 → TDD 调试修复 → ...）
- **每轮问题不再新建独立工作树**，除非明确要求（在当前工作树中继续）
- 工作流循环执行

### 7.4 选"暂不处理，保留工作树"

- 不合并、不清理
- 工作流结束，工作树保留供后续继续

### 7.5 中途中断处理

用户在任何步骤中断本工作流 → **AskUserQuestion**：
- 选项 1（推荐）：保留工作树（便于后续继续）
- 选项 2：立即清理工作树

### 7.6 步骤 0 选"当前 worktree"时的特殊处理

- 选"合并" → 执行 rebase + merge --no-ff
- 选"不合并"/"暂不处理" → **不删除工作树**（因工作树非本流程创建）
- 选"还有其他问题" → 在当前工作树继续新一轮

---

## 红线 — 停下来重新开始

- 跳过步骤 2 直接写修复代码
- 步骤 6 lint 不通过时强行提交
- 没有失败测试就写修复
- 步骤 5 文档检查失败仍继续
- 未经用户确认修改回归测试
- **在步骤 2 中直接本地跑全量回归**（必须延迟到步骤 3.3.5 走 CI）
- **跳过步骤 3.3.5 提交后全量回归验证**
- **分支未 push 时落到本地测试**（必须先 push 再等 CI，禁止本地测试兜底）
- **以 CI 触发失败为由走本地测试**（应排查 CI 配置或重试，而非降级验证）
- **合并后跳过 CI 验证直接清理工作树**
- **用"本地合并"作为跳过 CI 的理由**（合并方式不影响验证质量）

**以上所有都意味着：回到违规步骤重新执行。**

## 测试位置 — 合理化借口表

| 借口 | 现实 |
|------|------|
| "TDD 循环中代码未提交，无法触发 CI" | **步骤 2 的单测试文件绿灯可本地执行**（快速反馈），但**全量回归必须延迟到步骤 3.3.5**（代码已提交，可触发 CI）。未提交 ≠ 放弃 CI 验证。 |
| "本地跑全量测试更快" | 快不等于可靠。CI 验证本地环境差异（签名、SDK、runner 配置），是工作流核心价值。快速反馈靠步骤 2 单测试文件本地验证，全量靠 CI。 |
| "用户选了本地合并所以跳过 CI" | 合并方式（本地 merge vs PR）不影响验证质量。合并产生新 commit，必须验证。步骤 7.1 明确要求合并后走 CI。 |
| "只是修个小 bug，全量 CI 没必要" | 小 bug 的回归风险不一定小。CI 正是捕获意外回归。 |
| "CI 太慢，影响效率" | 步骤 2 已提供快速本地绿灯反馈。步骤 3.3.5 的 CI 等待可与步骤 3.2 文档编写并行，不阻塞。 |
| "本地测试通过了，CI 肯定也通过" | 本地环境 ≠ CI 环境。签名配置、SDK 版本、runner 权限差异都可能掩盖问题。 |
| "分支未 push，CI 触发不了，只能本地测" | 分支未 push 时必须先 `git push`，再等待远程 CI 结果。push 是 CI 验证的前置条件，不是跳过 CI 的理由。步骤 3.3.5 已明确要求先 push。 |
| "gh workflow run 失败了，CI 不可用" | CI 触发失败应排查配置或重试，而非降级到本地测试。本地测试不能替代 CI 的跨环境验证。 |
| "先本地验证逻辑，等权限好了再补 CI" | 本地测试无论包装成"预验证""逻辑检查"还是"先跑通再说"，都不能作为 3.3.5 的通过条件。3.3.5 必须等 push + CI 完成才能进入 3.4。 |
| "远端仓库故障（500/维护），CI 物理上跑不了" | 远端不可用时停止工作流并等待恢复，不得降级本地测试。基础设施故障不改变验证标准。 |

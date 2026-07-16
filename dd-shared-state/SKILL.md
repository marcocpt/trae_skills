---
name: dd-shared-state
description: dd 系列技能共享的工作流状态持久化规则，涵盖状态文件位置、参数化字段、恢复流程、写入/删除时机和并发检查。被 dd-bug-fix-workflow、dd-feature-development-workflow 引用。触发词：上下文恢复、状态文件、worktree 恢复、bug-fix-state.json、feature-development-state.json。
---

# dd 共享状态持久化

## 概述

会话上下文压缩后可能遗忘 worktree 路径、`BASE_BRANCH`、当前分支、当前步骤等关键状态。通过**状态文件持久化**解决——每个 worktree 拥有独立状态文件，支持多会话并行开发。

## 何时使用

- dd-bug-fix-workflow 或 dd-feature-development-workflow 的步骤开始前，需要恢复工作上下文
- 工作树创建/验证成功后写入状态
- 合并清理前删除状态

## 参数化

调用方按工作流类型选择参数：

| 工作流 | `WORKFLOW_TYPE` | 文件名 | `BRANCH_FIELD` |
|--------|-----------------|--------|----------------|
| bug 修复 | `bug-fix` | `bug-fix-state.json` | `fix_branch` |
| 新特性 | `feature-development` | `feature-development-state.json` | `feature_branch` |

## 状态文件位置

`$(git rev-parse --git-dir)/${WORKFLOW_TYPE}-state.json`

存放在 git dir（worktree 私有目录）下，不被 `git status` 检测。每个 worktree 拥有独立状态文件。

## 状态文件内容

### 通用字段（所有工作流必需）

```json
{
  "workflow_type": "<bug-fix|feature-development>",
  "worktree_path": "/absolute/path/to/worktree",
  "base_branch": "main",
  "<BRANCH_FIELD>": "<当前分支名>",
  "main_root": "/absolute/path/to/main/repo",
  "worktree_dir": "/absolute/path/to/project-worktrees",
  "current_step": "<步骤号>",
  "created_at": "<ISO 时间>"
}
```

### feature-development 特有字段

```json
{
  "feature_name": "<简短特性名>",
  "spec_path": "<设计规范路径>",
  "review_path": "<设计评审摘要路径>",
  "test_case_path": "<测试用例表路径>",
  "plan_dir": "<计划目录路径>",
  "current_phase": "<当前 Phase>",
  "total_phases": "<Phase 总数>",
  "commits": {
    "design_spec": "<commit-sha>",
    "design_review": "<commit-sha>",
    "plans": "<commit-sha>"
  }
}
```

## 恢复流程

每个步骤开始前，若不确定当前工作上下文，执行以下恢复：

```bash
git_dir=$(git rev-parse --git-dir)
state_file="$git_dir/${WORKFLOW_TYPE}-state.json"

if [ -f "$state_file" ]; then
    eval $(python3 -c "
import json
d = json.load(open('$state_file'))
for k in ['worktree_path','base_branch','${BRANCH_FIELD}','main_root','worktree_dir','current_step']:
    print(f'{k.upper()}=\"{d.get(k,\"\")}\"')
")
    cd "$WORKTREE_PATH"
else
    echo "未找到状态文件，可能尚未创建工作树或已清理"
fi
```

## 写入时机

- **写入**：工作树创建/验证成功后（bug-fix 步骤 1，feature-dev 步骤 1）
- **更新 `current_step`**：**每个步骤出口判定成功后必须立即更新**（HARD-GATE）。仅步骤 1 写入一次是不够的，会话压缩后智能体凭此字段恢复进度，停在 1 会让智能体误以为还在步骤 1。
- **更新 `current_phase`**（仅 feature-development）：每完成一个子计划，更新此字段
- **更新 `merge_in_progress`**：合并操作执行前设置为 `true`，merge 成功后清除或直接删除状态文件
- **删除**：合并成功后（**禁止 merge 前删除**），须在 `git merge --no-ff` 成功后执行，此时 `git-dir` 指向 worktree 私有目录

### 写入模板

```bash
git_dir=$(git rev-parse --git-dir)

cat > "$git_dir/${WORKFLOW_TYPE}-state.json" <<EOF
{
  "workflow_type": "${WORKFLOW_TYPE}",
  "worktree_path": "$(pwd)",
  "base_branch": "$BASE_BRANCH",
  "${BRANCH_FIELD}": "$(git rev-parse --abbrev-ref HEAD)",
  "main_root": "$main_root",
  "worktree_dir": "$worktree_dir",
  "current_step": "<当前步骤号>",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
```

feature-development 工作流需追加特有字段（feature_name、spec_path、plan_dir 等）。

### 更新 `current_step` 模板（每个步骤出口执行）

```bash
git_dir=$(git rev-parse --git-dir)
python3 -c "
import json
state_file = '$git_dir/${WORKFLOW_TYPE}-state.json'
with open(state_file) as f:
    state = json.load(f)
state['current_step'] = '<新步骤号或子步骤>'
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"
```

### 合并中状态标记（仅 bug-fix 步骤 7.1 / feature-dev 合并步骤）

执行 `git merge` 前必须先标记合并中状态，merge 成功后才删除状态文件：

```bash
# 1. merge 前更新状态文件
git_dir=$(git rev-parse --git-dir)
python3 -c "
import json
state_file = '$git_dir/${WORKFLOW_TYPE}-state.json'
with open(state_file) as f:
    state = json.load(f)
state['current_step'] = '<合并步骤>-merging'
state['merge_in_progress'] = True
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"

# 2. 执行 git merge（在主仓库路径）
cd "$main_root"
git checkout "$BASE_BRANCH"
git merge --no-ff <工作树分支>

# 3. merge 成功后回到 worktree 删除状态文件
cd "$WORKTREE_PATH"
git_dir=$(git rev-parse --git-dir)
rm -f "$git_dir/${WORKFLOW_TYPE}-state.json"
```

### 状态文件不存在时的恢复策略

会话恢复时若状态文件不存在，**禁止默认从步骤 0 重启**。必须按以下顺序判断：

1. 检查当前目录是否在 worktree 中（`git rev-parse --is-inside-work-tree`）
2. 获取当前分支名（`git rev-parse --abbrev-ref HEAD`）
3. 若分支名匹配 `fix/F<N>-<描述>` 或 `feature/<F编号>-<描述>` 格式，对比 `git log origin/<BASE_BRANCH>..HEAD` 判断是否有已提交的修复
4. 若已有 commit：识别为「合并中」状态，询问用户是否继续合并或开新一轮
5. 若无 commit：识别为「TDD 中」状态，询问用户是否继续修复或重新开始
6. 仅当无法判断进度时，才从步骤 0 重新开始

### 删除模板（merge 成功后执行）

```bash
git_dir=$(git rev-parse --git-dir)
rm -f "$git_dir/${WORKFLOW_TYPE}-state.json"
```

## 并发检查

新工作流开始前（在当前 worktree 验证阶段），禁止同一 worktree 上同时运行多个工作流：

```bash
git_dir=$(git rev-parse --git-dir)
for f in "$git_dir"/bug-fix-state.json "$git_dir"/feature-development-state.json; do
  if [ -f "$f" ]; then
    existing_type=$(python3 -c "import json; print(json.load(open('$f')).get('workflow_type','unknown'))")
    echo "❌ 当前 worktree 已有活跃的 ${existing_type} 工作流，禁止并发"
    exit 1
  fi
done
```

## 被其他 skill 引用方式

各 dd 工作流技能在"上下文恢复机制"章节引用本技能，替换重复的状态文件规则。引用格式：`状态持久化遵循 [dd-shared-state](../dd-shared-state/SKILL.md)，参数 WORKFLOW_TYPE=<bug-fix|feature-development>，BRANCH_FIELD=<fix_branch|feature_branch>`

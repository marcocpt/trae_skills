> 迁移来源：`dd-shared-state/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# dd 共享状态持久化

## 概述

会话上下文压缩后可能遗忘 worktree 路径、`BASE_BRANCH`、当前分支、当前步骤等关键状态。通过**状态文件持久化**解决——每个 worktree 拥有独立状态文件，支持多会话并行开发。

本技能固定为 `invocation_mode=helper`：完成状态读写、恢复或并发检查后返回调用方，不自行 Host Close。宿主结束由顶层 `standalone` 工作流按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 负责。

## 何时使用

- dd-bug-fix-workflow 或 dd-feature-development-workflow 的步骤开始前，需要恢复工作上下文
- 工作树创建/验证成功后写入状态
- 合并后按 `WORKFLOW_TYPE` 分支处置状态：bug-fix 允许合并清理时删除；feature-development 须先完成 Closure（写 Completion Receipt、`in_progress.operation=cleanup`），cleanup 完成或 worktree 删除后才删除/归档活动状态，**不得在 Closure 前删除**

## 参数化

调用方按工作流类型选择参数：

| 工作流 | `WORKFLOW_TYPE` | 文件名 | 进度字段 |
|--------|-----------------|--------|----------|
| bug 修复 | `bug-fix` | `bug-fix-state.json` | `current_step` |
| 新特性 | `feature-development` | `feature-development-state.json` | `current_step` |
| 项目启动 | `project-bootstrap` | `project-bootstrap-state.json` | `current_node` |

## 状态文件位置

`$(git rev-parse --git-dir)/${WORKFLOW_TYPE}-state.json`

存放在 git dir（worktree 私有目录）下，不被 `git status` 检测。每个 worktree 拥有独立状态文件。

## 状态文件内容

### 通用字段（所有工作流必需）

```json
{
  "schema_version": 1,
  "workflow_type": "<bug-fix|feature-development|project-bootstrap>",
  "status": "active",
  "worktree_path": "/absolute/path/to/worktree",
  "base_branch": "main",
  "<BRANCH_FIELD>": "<当前分支名>",
  "main_root": "/absolute/path/to/main/repo",
  "worktree_dir": "/absolute/path/to/project-worktrees",
  "current_step": "<步骤号>",
  "created_at": "<ISO 时间>"
}
```

`<BRANCH_FIELD>` 对 bug-fix / feature-development 分别为 `fix_branch` / `feature_branch`；project-bootstrap 不要求分支专用字段，使用 `worktree_path` 和 `base_branch` 即可。

`status` 使用 `active`、`handoff-ready`、`completed` 或 `paused`。已有调用方未写入 `schema_version` 或 `status` 时，恢复逻辑按 schema 0 / active 兼容读取，不得直接判为损坏。

### feature-development 特有字段

```json
{
  "feature_name": "<简短特性名>",
  "requirements_path": "<需求文档路径>",
  "design_path": "<设计文档路径>",
  "visual_path": "<视觉原型路径>",
  "test_case_path": "<测试用例表路径>",
  "review_path": "<审查结果路径>",
  "plan_dir": "<计划目录路径>",
  "phase_plan_paths": [{"phase_id": 1, "path": "<Phase 子计划文件路径>"}],
  "integration_plan_path": "<跨 Phase 集成计划路径，仅复杂档>",
  "current_phase": "<当前 Phase>",
  "total_phases": "<Phase 总数>",
  "completed_phases": ["<已完成本地验证的 Phase 编号列表>"],
  "smoke_ci_phases": ["<触发过远程 UI Smoke CI 的 Phase 编号列表>"],
  "final_candidate_branch": "<最终合并候选分支名>",
  "candidate_sha": "<冻结候选 SHA>",
  "candidate_review": {"level": "standard", "execution": "auto", "sha": "<candidate_sha>", "review_ref": "<review-ref>"},
  "full_spec_gap": {"sha": "<candidate_sha>", "gap_table_ref": "<gap-table-ref>"},
  "full_ci_run": {"run_id": "<run-id>", "url": "<run-url>", "head_sha": "<candidate_sha>", "conclusion": "success"},
  "full_ci_passed": false,
  "commits": {
    "specs": "<规格文档套件提交 sha>",
    "plans": "<commit-sha>"
  }
}
```

> **三层增量验证约束**：feature-development 工作流采用三层验证。`completed_phases` 记录已通过本地快速验证的 phase 列表，`smoke_ci_phases` 记录触发过远程 UI Smoke CI 的 phase 列表；`final_candidate_branch`、`candidate_sha`、`candidate_review`、`full_spec_gap`、`full_ci_run`、`full_ci_passed` 跟踪最终合并候选，且 `candidate_review.sha == full_spec_gap.sha == full_ci_run.head_sha == candidate_sha`（exact-SHA 不变量）。

### project-bootstrap 特有字段

```json
{
  "project_mode": "brownfield",
  "host": "trae",
  "requested_entry": "roadmap",
  "current_node": "preflight",
  "completed_nodes": ["preflight"],
  "artifacts": {},
  "decisions": [],
  "blocking_gaps": ["brownfield-baseline"],
  "deferred_gaps": [],
  "handoff": {}
}
```

- `project_mode` 只能是 `greenfield` 或 `brownfield`；
- `decisions` 保存用户已批准或由仓库证据确认的事实，子 skill 不得重复询问；
- `artifacts` 记录路径、状态和最后验证时间，不把“路径曾存在”当成当前有效；
- `handoff` 在下游确认接收前保留；
- `status=completed` 的状态文件不阻塞新的工作流。

## 恢复流程

每个步骤或节点开始前，若不确定当前工作上下文，执行恢复。读取状态后必须验证：

1. `worktree_path` 与当前 Git worktree 匹配；
2. 状态中记录的必需产物仍存在；
3. 适用的项目规则没有与已记录决策发生冲突；
4. `current_step` / `current_node` 与完成产物一致；
5. 状态为 `completed` 时只作历史参考，不恢复为 active。

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

Bootstrap 没有状态文件时，先从仓库中的 `docs.md`、Roadmap、Architecture、Standards、`AGENTS.md` 和 Baseline 重建 artifact map；只有无法从事实判断时才重新询问，禁止默认从头 grill。

## 写入时机

- **写入**：工作树创建/验证成功后（bug-fix 步骤 1，feature-dev 步骤 1）
- **更新 `current_step`**：**每个步骤出口判定成功后必须立即更新**（HARD-GATE）。仅步骤 1 写入一次是不够的，会话压缩后智能体凭此字段恢复进度，停在 1 会让智能体误以为还在步骤 1。
- **更新 `current_phase`**（仅 feature-development）：每完成一个子计划，更新此字段
- **更新 `phase_plan_paths` / `integration_plan_path`**（仅 feature-development）：Planning Stage 拆分档位为 `per-phase` 或 `per-phase-with-integration` 时，写入每个 Phase 子计划路径数组；复杂档同时写 `integration_plan_path`。`phase_plan_paths` 长度必须等于 `total_phases`，否则禁止推进到 implementation
- **更新 `completed_phases`**（仅 feature-development）：每完成一个 phase 的本地验证，追加当前 phase 编号到此数组
- **更新 `smoke_ci_phases`**（仅 feature-development）：每触发一次远程 UI Smoke CI，追加当前 phase 编号到此数组
- **更新 `final_candidate_branch`**（仅 feature-development）：创建最终合并候选分支时记录
- **更新候选 exact-SHA 字段**（仅 feature-development）：冻结候选时写 `candidate_sha`、`candidate_review`、`full_spec_gap`；完整远程 CI 通过且 `full_ci_run.head_sha == candidate_sha` 时才写 `full_ci_run={run_id,url,head_sha,conclusion}` 与 `full_ci_passed=true`
- **更新 `in_progress`**：merge/push/cleanup 等不可瞬时动作执行前写 `in_progress: {operation, target, source, started_at}`（见 runtime-contract §4），动作成功后写完成证据再清除；**不另设布尔兼容字段**
- **删除**（按 `WORKFLOW_TYPE` 分支）：**bug-fix** 在 `git merge --no-ff` 成功后、清理前可删除（**禁止 merge 前删除**）；**feature-development** 在 merge 后仍须保留状态直到 Closure 完成——写 Completion Receipt、cleanup 执行并验证后才删除/归档活动状态，**禁止在 Closure 校验与 Receipt 写入前删除**（delivery-and-closure 的 Closure 流程为准）
- **Bootstrap 写入**：Preflight 结束后写入；每个节点 Gate 通过后更新 `current_node`、`completed_nodes`、`artifacts` 和 gaps
- **Bootstrap 完成**：Handoff 准备后设为 `handoff-ready`；下游确认接收且 Exit Gate 通过后、Host Close ASK 前设为 `completed`，不立即删除

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

feature-development 工作流需追加特有字段（feature_name、requirements_path、design_path、visual_path、test_case_path、review_path、plan_dir 等）。

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

### 合并中状态标记（仅 bug-fix 步骤 7.1 / feature-dev Delivery 合并步骤）

执行 `git merge` 前必须先标记合并中状态；merge 成功后按 `WORKFLOW_TYPE` 处置：

```bash
# 1. merge 前更新状态文件
git_dir=$(git rev-parse --git-dir)
python3 -c "
import json
state_file = '$git_dir/${WORKFLOW_TYPE}-state.json'
with open(state_file) as f:
    state = json.load(f)
state['in_progress'] = {'operation': 'merge', 'target': '$BASE_BRANCH', 'source': '<工作树分支>', 'started_at': '<ISO 时间>'}
with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)
"

# 2. 执行 git merge（在主仓库路径）
cd "$main_root"
git checkout "$BASE_BRANCH"
git merge --no-ff <工作树分支>

# 3. merge 成功后处置状态（按 WORKFLOW_TYPE）
#    - bug-fix: 清理时可直接删除
#    - feature-development: 保留直到 Closure 完成（Receipt 写入、cleanup 验证后）才删除
cd "$WORKTREE_PATH"
git_dir=$(git rev-parse --git-dir)
if [ "$WORKFLOW_TYPE" = "bug-fix" ]; then
  rm -f "$git_dir/${WORKFLOW_TYPE}-state.json"
fi
# feature-development: 继续执行 delivery-and-closure 的 Closure 流程，最后才删除/归档
```

### 状态文件不存在时的恢复策略

会话恢复时若状态文件不存在，**禁止默认从步骤 0 重启**。必须按以下顺序判断：

1. 检查当前目录是否在 worktree 中（`git rev-parse --is-inside-work-tree`）
2. 获取当前分支名（`git rev-parse --abbrev-ref HEAD`）
3. 若分支名匹配 `fix/F<N>-<描述>` 或 `feature/<F编号>-<描述>` 格式，对比 `git log origin/<BASE_BRANCH>..HEAD` 判断是否有已提交的修复
4. 若已有 commit：识别为「合并中」或「TDD 中」状态，询问用户是否继续或开新一轮。feature-dev 额外检查是否存在 `ci/F*-final-candidate` 分支判断是否在步骤 5 候选阶段
5. 若无 commit：识别为「TDD 中」状态，询问用户是否继续修复或重新开始
6. 仅当无法判断进度时，才从步骤 0 重新开始

### 删除模板（仅 bug-fix 合并清理时执行）

```bash
git_dir=$(git rev-parse --git-dir)
rm -f "$git_dir/${WORKFLOW_TYPE}-state.json"
```

> feature-development **不适用此模板**：merge 后先完成 Closure（校验 candidate/full_ci/completed_phases、写 Completion Receipt、`in_progress.operation=cleanup` 并执行），cleanup 完成或 worktree 删除后才删除/归档活动状态（见 delivery-and-closure §2/§3）。

## 并发检查

新工作流开始前（在当前 worktree 验证阶段），禁止同一 worktree 上同时运行多个 active/paused/handoff-ready 工作流；`completed` 状态不阻塞：

```bash
git_dir=$(git rev-parse --git-dir)
for f in \
  "$git_dir"/bug-fix-state.json \
  "$git_dir"/feature-development-state.json \
  "$git_dir"/project-bootstrap-state.json; do
  if [ -f "$f" ]; then
    existing=$(python3 -c "
import json
d=json.load(open('$f'))
print(d.get('workflow_type','unknown'), d.get('status','active'))
")
    existing_type="${existing% *}"
    existing_status="${existing##* }"
    if [ "$existing_status" != "completed" ]; then
      echo "当前 worktree 已有 ${existing_status} 的 ${existing_type} 工作流，禁止并发"
      exit 1
    fi
  fi
done
```

## 写入租约（跨宿主唯一写者）

状态文件扫描是 check-then-act，两个宿主同时启动会同时看到"无 active state"。真正的互斥由 git common dir 下的原子租约提供（DD-006、FR-008、NFR-007）——common dir 对同仓库所有 worktree 和宿主共享：

```bash
# 取得租约：先建根目录（幂等），再对最终 lease 目录做原子 mkdir 竞争；
# key 用 worktree 绝对路径的哈希，避免把路径字符直接拼进目录名
lease_root="$(git rev-parse --path-format=absolute --git-common-dir)/dd-workflow-lease"
worktree="$(git rev-parse --path-format=absolute --show-toplevel)"
mkdir -p "$lease_root"
lease="$lease_root/$(printf '%s' "$worktree" | shasum -a 256 | cut -c1-16)"
if mkdir "$lease" 2>/dev/null; then
  printf '{"workflow_id":"%s","host":"%s","worktree":"%s","holder_pid":%s,"acquired_at":"%s","last_validated_at":"%s"}\n' \
    "$WORKFLOW_ID" "$HOST" "$worktree" "$$" \
    "$(date -u +%FT%TZ)" "$(date -u +%FT%TZ)" > "$lease/holder.json"
else
  echo "写入租约被占：$(cat "$lease/holder.json" 2>/dev/null)"; exit 1
fi

# 持有期间每次写状态前刷新 last_validated_at
# 释放时机：仅限任务完成、已阻塞或显式移交（记录接管方）后 rm -rf "$lease"；
# Review PASS 不等于 Workflow 完成，审查期间保留租约但暂停写入
```

约束：

- 同一时刻任一工作环境最多一个实现执行者持有租约；第二个入口必须保持只读、转入隔离 worktree 或明确停止；
- `last_validated_at` 超过 2 小时未刷新只触发**重新核对**，不自动获得接管权：必须核实原 holder 进程是否存活、其状态文件的 `status` 是否仍 active/paused、宿主是否可达；全部证据表明已废弃，才可接管，且必须先把原 holder 信息记入本工作流状态文件；
- 禁止静默覆盖他人租约。

## 被其他 skill 引用方式

各 dd 工作流技能在“上下文恢复机制”章节引用本技能，替换重复的状态文件规则。调用方声明 `WORKFLOW_TYPE`，并使用对应的 `current_step` 或 `current_node` 进度字段。

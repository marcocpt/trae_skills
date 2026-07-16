# 验证测试：特性已实现，状态文件不存在时的恢复

## 场景

用户使用 dd-feature-development-workflow 实现新特性 F5.1，特性代码已实现并 push（commit `abc1234` + `def5678`）。步骤 9.1 执行中：
1. 已更新状态文件标记 `current_step="9.1-merging"` + `merge_in_progress=true`
2. 切回主仓库 develop
3. **此时会话上下文被压缩**

状态文件内容（worktree 私有目录）：
```json
{
  "workflow_type": "feature-development",
  "worktree_path": "/Users/dengdeng/Working/Keyboard/feature-F5.1-visual-toolbar",
  "base_branch": "develop",
  "feature_branch": "feature/F5.1-visual-toolbar",
  "main_root": "/Users/dengdeng/Working/Keyboard/Macim",
  "worktree_dir": "/Users/dengdeng/Working/Keyboard/Macim-worktrees",
  "current_step": "9.1-merging",
  "merge_in_progress": true,
  "feature_name": "visual-toolbar",
  "created_at": "2026-07-16T08:00:00Z"
}
```

## 预期行为（修改后技能）

### 情况 A：状态文件存在（merge_in_progress=true）

1. 智能体读取状态文件，发现 `current_step="9.1-merging"` + `merge_in_progress=true`
2. 识别为「步骤 9.1 合并中」状态
3. 检查当前 git 状态：
   - 若 develop 已有 merge commit → merge 已完成，删除状态文件
   - 若 develop 无 merge commit → merge 未执行，询问用户是否继续
4. **不**从步骤 0 重新开始

### 情况 B：状态文件不存在（已被其他方式删除）

1. 智能体发现状态文件不存在
2. 按「状态文件不存在时的恢复策略」判断：
   - 检查当前目录是否在 worktree 中（`git rev-parse --is-inside-work-tree`）
   - 获取当前分支名（`git rev-parse --abbrev-ref HEAD`）
   - 若分支名匹配 `feature/F<N>-<描述>` 格式，对比 `git log origin/<BASE_BRANCH>..HEAD` 判断是否有已提交的特性实现
3. 若已有实现 commit：识别为「步骤 9.1 合并中」状态，询问用户是否继续合并或开新一轮
4. **不**从步骤 0 重新开始

## 验证步骤

1. 在 worktree 路径执行恢复策略命令：
   ```bash
   git rev-parse --is-inside-work-tree  # 确认在 worktree 中
   git rev-parse --abbrev-ref HEAD      # 获取分支名 feature/F5.1-visual-toolbar
   git log origin/develop..HEAD --oneline  # 查看特性提交
   ```

2. 预期输出：
   - 分支名匹配 `feature/F5.1-*` 格式
   - `git log` 显示已有特性实现 commit（abc1234, def5678）
   - 智能体识别为「步骤 9.1 合并中」

3. 智能体应询问：
   - 选项 1（推荐）：继续合并到 develop
   - 选项 2：开新一轮特性开发
   - 选项 3：重新开始

## 成功标准

- [ ] 智能体不从步骤 0 重新开始
- [ ] 智能体正确识别已有特性实现 commit
- [ ] 智能体询问用户是否继续合并
- [ ] 智能体在 merge 前标记 `merge_in_progress=true`
- [ ] 智能体在 merge 成功后才删除状态文件

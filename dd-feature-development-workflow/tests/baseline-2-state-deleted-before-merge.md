# 基线测试 2：delivery 前删除状态文件导致会话压缩后失忆

## 场景

用户使用 dd-feature-development-workflow 实现新特性 F5.1，工作流已推进到 Delivery Stage（合并到目标分支）。特性代码已实现、已 push、CI 已通过。

智能体执行 Delivery 动作：
1. **先删除状态文件**（"在离开工作树前"）
2. 切回主仓库 `cd "$main_root"`
3. `git checkout "$BASE_BRANCH"`（develop）
4. 准备执行 `git merge --no-ff feature/F5.1-visual-toolbar`

**此时会话上下文被压缩**。状态文件已被删除，merge 尚未执行。

## 预期行为（修改后技能）

1. 智能体发现状态文件不存在
2. 按 evidence-first 恢复策略（见 [state-and-handoff.md](../references/state-and-handoff.md)）判断：
   - 检查当前目录是否在 worktree 中 → 是
   - 获取当前分支名 → `develop`（已切回主仓库）
   - 对比 `git log origin/develop..feature/F5.1-visual-toolbar` → 有已提交的特性实现
3. 识别为「Delivery 合并中」状态（`current_stage=delivery`、`merge_in_progress=true`）
4. 询问用户是否继续合并或开新一轮
5. **不**从 Intake 重新开始（避免重复整个工作流）

## 当前基线行为（修改前预期失败）

1. ❌ 智能体发现状态文件不存在
2. ❌ 技能无「状态文件不存在时的恢复策略」章节
3. ❌ 智能体默认从 Intake 重新开始
4. ❌ 重复需求确认 → 创建工作树 → 设计规范 → 计划编写 → TDD 实现 → ...
5. ❌ 浪费整轮工作流时间，用户不得不手动纠正"特性已经实现完了，只需要 merge"

## 压力因素

- 状态文件已删除，智能体无任何上下文信号
- 当前在主仓库 develop 分支（不在 worktree 中），容易误判为"新工作流开始"
- `git log` 显示 feature 分支已有提交，但智能体不主动检查
- Delivery 的删除时机是"merge 前"，产生窗口期：状态文件已删除但 merge 未完成

## 根因

Delivery 在外部动作前删除状态文件，产生危险的窗口期：状态文件已删除，但 merge 尚未执行。如果此时会话压缩，智能体看到状态文件不存在，会默认从 Intake 重新开始。

**正确做法**：merge 前先更新状态文件标记 `current_stage=delivery` + `merge_in_progress=true`，merge 成功后才删除状态文件。

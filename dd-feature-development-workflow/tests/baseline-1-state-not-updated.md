# 基线测试 1：current_stage 未更新导致会话压缩后重复执行

## 场景

用户使用 dd-feature-development-workflow 实现新特性 F5.1，工作流已推进到 Implementation Stage（TDD 实现），子计划 Phase 2 正在执行。此时会话上下文被压缩。

状态文件 `feature-development-state.json` 内容：
```json
{
  "workflow_type": "feature-development",
  "worktree_path": "/Users/dengdeng/Working/Keyboard/feature-F5.1-visual-toolbar",
  "base_branch": "develop",
  "feature_branch": "feature/F5.1-visual-toolbar",
  "main_root": "/Users/dengdeng/Working/Keyboard/Macim",
  "worktree_dir": "/Users/dengdeng/Working/Keyboard/Macim-worktrees",
  "current_stage": "environment",
  "feature_name": "visual-toolbar",
  "current_phase": "2",
  "total_phases": "3",
  "created_at": "2026-07-16T08:00:00Z"
}
```

**关键问题**：`current_stage` 停在 `environment`（Environment 时写入），后续 Specification/Planning/Implementation 完成后均未更新。但 `current_phase` 已更新到 `"2"`，说明实际进度在 Implementation（Phase 2）。

## 预期行为（修改后技能）

1. 智能体读取状态文件，发现 `current_stage=environment` 但 `current_phase="2"`
2. 识别 `current_stage` 与实际进度不符（environment 不会有 current_phase）
3. 按 evidence-first 恢复：从工作分支提交、规格/计划文件、Phase 证据推断实际在 Implementation（Phase 2）
4. 询问用户是否继续 Implementation Phase 2，或重新开始
5. **不**从 Environment 重新验证 worktree（浪费时间）

## 当前基线行为（修改前预期失败）

1. ❌ 智能体读取 `current_stage=environment`，机械地从 Environment 开始
2. ❌ 重新执行 worktree 验证（工作区干净 + 基线测试）
3. ❌ 忽略 `current_phase="2"` 的信号
4. ❌ 浪费整轮重新验证，甚至可能误判 worktree 状态
5. ❌ 用户不得不手动纠正"我已经在 Implementation 了"

## 压力因素

- `current_stage` 与 `current_phase` 信号冲突，智能体选择机械遵循 `current_stage`
- 技能只说"每完成一个 Stage"更新，无 HARD-GATE 强制要求
- 智能体合理化："状态文件说在 environment，我应该先验证 worktree"
- environment 的验证耗时（基线测试 + worktree 检查），沉没成本让智能体继续错误路径

## 根因

技能顶部「上下文恢复机制」章节（line 58）只说"每完成一个 Stage"更新 `current_stage`，无 HARD-GATE 强制要求；各 Stage 出口判定均无状态文件更新要求。智能体在 environment 写入后，后续 Stage 自然遗忘更新。

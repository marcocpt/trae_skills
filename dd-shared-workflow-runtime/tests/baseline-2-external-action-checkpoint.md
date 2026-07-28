# 基线场景 2：外部动作前保留恢复点

## 背景

工作流即将在主仓库合并工作分支，随后会删除 worktree。当前活动状态是唯一恢复依据。

## 选择

A) 先删状态，再执行 merge
B) 直接 merge，完成后再考虑状态
C) 原子写入 merge in progress 与 next safe action，验证写入后再 merge
D) 把状态写进工作分支的普通提交

## 预期

**C**

外部动作前必须持久化恢复点；动作成功后记录结果。活动状态会随清理消失时，还需先写 Completion Receipt。

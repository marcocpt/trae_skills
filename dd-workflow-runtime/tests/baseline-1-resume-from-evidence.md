# 基线场景 1：状态与仓库证据冲突

## 背景

状态记录 `current_stage=environment`，但工作分支已有已批准规格、计划、两个 Phase commit 和对应验证证据。路径与项目规则均有效。

## 选择

A) 机械回到 Environment 重跑基线
B) 删除状态并从 Intake 重新询问
C) 验证产物和提交，修正状态，从第一个未满足 Gate 的 Phase 继续
D) 因状态冲突直接结束

## 预期

**C**

状态是 checkpoint，仓库证据是真值。修正必须先于继续，已解决事实不得重问。

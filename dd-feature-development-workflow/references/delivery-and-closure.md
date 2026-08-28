# Feature Delivery and Closure

只在 Documentation、Delivery 或 Closure Stage 读取。

## 1. Documentation

Documentation 正文由 [documentation.md](documentation.md) 拥有（候选冻结前完成，AC-07）。本文件只在 Documentation Stage 被主 SKILL 路由到该 reference；Delivery 与 Closure 不复制文档同步正文。

Gate：文档与已验证行为一致，且发生在候选冻结之前；通过后 `current_stage=final-candidate`。

## 2. Delivery

### 2.1 exact-SHA invariant

Delivery 只推进同一个 `candidate_sha`。先检查 confirmation、action-specific `delivery_authorization`，并验证：

```text
review_sha == gap_sha == ci_sha == candidate_sha
```

四个 SHA 任一不等即 `BLOCKED`，不得 promote/push/merge。候选后任何内容变化返回 Documentation/Final Candidate 重新冻结（AC-09）。内容批准、测试 PASS、Reviewer PASS 均不授权 Git 或外部动作。

### 2.2 动作

先按共享运行时解析 `delivery_policy` 和每类动作的授权；内容批准本身不授权 Git。只执行其中明确要求且获准的动作：

1. 检查工作区和准确 diff；
2. lint / typecheck；
3. 必需测试或已存在的同 SHA CI 证据；
4. 策略要求且获准时按逻辑 commit；
5. 策略要求且获准时 push 正确分支；
6. 需要远程 CI 时等待与该 SHA 对应的结果；
7. 按需同步 AI-test。

不得 force push、推错 main/master、暂存无关脏文件或提交秘密。AI-test 同步前先检查目标 worktree 是否有未提交变更；dirty 或同步失败才 ASK。

每个外部动作前写 `in_progress`，完成后记录 SHA、run 和远端状态。未要求的动作记 `not-required`，明确禁止的动作记 `not-authorized`；后续 Gate 依赖被禁止动作时保持 `BLOCKED`，不得假装完成。Gate：项目要求且获准的 Delivery 动作全部有证据，`current_stage=closure`。

## 3. Closure

清理前验证（对齐 exact-SHA 语义）：

- `completed_phases` 数量等于 `total_phases`；
- `candidate_sha` 与 `full_ci_run` 的 SHA 相同，且 `full_ci_passed=true`；
- develop/目标分支包含该 `candidate_sha`；
- Documentation 与 Delivery Gate 已通过；
- 工作区无未解释变更。

先写 `cleanup_in_progress=true` 再执行清理；cleanup 完成或 worktree 删除后状态随之处置（见下）。

### 隔离 worktree

1. 记录 `cleanup` in progress；
2. 删除工作流临时需求摘要；
3. 写 Completion Receipt；
4. 按项目规则删除 worktree、本地工作分支和允许删除的远端分支；
5. 验证清理结果；
6. 保留 Receipt，活动状态可随 worktree 删除。

所有 repo-wide 清理必须在记录的 `main_root` 执行，并使用明确目标。禁止通过未验证变量、宽泛 glob 或仓库根递归删除。

### 用户提供的当前 worktree

不删除 worktree。清理流程拥有的临时文件，原子写 `status=completed`，保留或归档状态。

### 暂停

用户选择保留未完成环境时：

```yaml
status: paused
current_stage: closure
next_safe_action: resume closure decision
```

暂停不是完成，不写 completed Receipt，不触发最终 Host Close。

## 4. Host Close

真正完成后遵循 `dd-workflow-runtime`：

- 先确认活动状态或 Receipt 为 `completed`；
- Trae 使用 ASK，且只提供 `结束本次任务` / `还有其他任务`；
- “还有其他任务”创建新 `workflow_id` 并重新 Preflight；
- “结束本次任务”后输出最终摘要；
- Codex 直接输出最终摘要。

不得把 cleanup 选择与最终 Host Close 混成三到四个选项；前者决定资源处置，后者决定 Trae 会话是否继续。

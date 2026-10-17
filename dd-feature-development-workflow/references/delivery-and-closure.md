# Feature Delivery and Closure

只在 Delivery 或 Closure Stage 读取。Documentation 正文由 [documentation.md](documentation.md) 拥有，本文件不重复。

## 1. Delivery

### 1.1 exact-SHA invariant

Delivery 只推进同一个被验证版本。先复用 Confirmation 已有的 action-specific `delivery_authorization`（无新决定不再泛问"继续交付还是回退"），并对有提交且项目要求CI的交付路径验证：

```text
review_sha == gap_sha == ci_sha == candidate_sha
```

上式只适用于有提交且CI为必需项的路径。项目不要求CI时略去ci_sha比较，仍核对实际适用的提交/审查/缺口身份；未提交的局部验证保持candidate_sha及当前SHA字段为空，通过既有verification_evidence.result.bindings.implementation_digest绑定真实内容（含相关dirty/未跟踪输入），不将摘要塞进SHA字段，也不以空值相等当通过。需要commit/push/merge时只执行已有授权动作；工作树指纹与提交产物须有可核对的内容对应关系，不同内容不得直接继承验证。项目要求的提交级CI仍必须在该真实SHA上满足。内容变化先判影响，只重做失配证据。内容批准、测试PASS、Reviewer PASS均不授权Git或外部动作。

### 1.2 动作

先按共享运行时解析 `delivery_policy` 和每类动作的授权；内容批准本身不授权 Git。只执行其中明确要求且获准的动作：

1. 检查工作区和准确 diff；
2. lint / typecheck；
3. 必需测试或已存在的同 SHA CI 证据；
4. 策略要求且获准时按逻辑 commit；
5. 策略要求且获准时 push 正确分支；
6. 需要远程 CI 时等待与该 SHA 对应的结果；
7. 按需同步 AI-test。

不得 force push、推错 main/master、暂存无关脏文件或提交秘密。AI-test 同步前先检查目标 worktree 是否有未提交变更；dirty 或同步失败才 ASK。

项目要求 CI 但未运行、未绑定被交付版本或未经授权时保持 `BLOCKED`，不得用本地结果放行，也不自行改成本地通过或豁免。

每个外部动作前写 `in_progress: {operation, target, source, started_at}`，完成后记录 SHA、run 和远端状态。未要求的动作记 `not-required`，明确禁止的动作记 `not-authorized`；后续 Gate 依赖被禁止动作时保持 `BLOCKED`，不得假装完成。Gate：项目要求且获准的 Delivery 动作全部有证据，`current_stage=closure`。

## 2. Closure

清理前验证（对齐 exact-SHA 语义）：

- `completed_phases` 数量等于 `total_phases`；
- 对本任务要求的验证核对当前内容身份；有提交且项目要求CI时，`candidate_sha`与`full_ci_run.head_sha`相同，且`full_ci_run.conclusion==success && head_sha==candidate_sha`。项目不要求CI时full_ci_run合法保持null并记not-required依据，不因该null阻塞局部收尾；必需CI未执行/未绑定/非success不得放行要求的交付。未提交路径核对implementation_digest及对应审查、回归和缺口证据，不使用空SHA相等冒充；
- 仅在要求的交付动作包含 merge 时校验 develop/目标分支包含该被验证版本；**未要求 merge 的已授权局部任务按实际范围收尾**，不因目标分支未含候选而阻塞（也据此不宣称已合并／已发布）；
- Documentation 与 Delivery Gate 已通过；
- 工作区无未解释变更。

先写 `in_progress: {operation: cleanup, target: <worktree-or-branch>, source: <main_root>}` 再执行清理；cleanup 完成或 worktree 删除后状态随之处置（见下）。

### 隔离 worktree

1. 记录 `in_progress.operation=cleanup`；
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

## 3. Host Close

真正完成后遵循 `dd-workflow-runtime`：

- 先确认活动状态或 Receipt 为 `completed`；
- Trae 使用 ASK，且只提供 `结束本次任务` / `还有其他任务`；
- “还有其他任务”创建新 `workflow_id` 并重新 Preflight；
- “结束本次任务”后输出最终摘要；
- Codex 直接输出最终摘要。

不得把 cleanup 选择与最终 Host Close 混成三到四个选项；前者决定资源处置，后者决定 Trae 会话是否继续。

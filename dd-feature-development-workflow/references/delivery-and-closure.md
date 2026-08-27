# Feature Delivery and Closure

只在 Documentation、Delivery 或 Closure Stage 读取。

## 1. Documentation

读取项目测试／文档规则，比较已交付 SHA（尚未要求 Commit 时比较冻结 diff／文件指纹）与规格，不只看文件列表。分析：

- 直接行为与依赖；
- 共享模型、协议、配置、持久化；
- 用户流程和高风险路径；
- 新增、更新、执行或暂缓的测试。

检查：

- Requirements 的 AC、范围和约束；
- Design 的职责、数据流、状态和回退；
- Visual 与最终 UI；
- Test Cases 的状态、证据、AC 映射和统计；
- 代码测试名称、断言和替身。

行为未改变时不要为了“同步”篡改需求。修改文档时遵循版本和 history 规则。输出每份文档的“已更新/无需更新/不适用”及原因。

Gate：文档与已验证行为一致，`current_stage=delivery`。

## 2. Delivery

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

清理前验证：

- `completed_phases` 数量等于 `total_phases`；
- `final_candidate_sha` 与完整 CI SHA 相同；
- `final_ci_passed=true`；
- develop/目标分支包含该 SHA；
- Documentation 与 Delivery Gate 已通过；
- 工作区无未解释变更。

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

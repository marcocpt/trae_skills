# Bug Delivery and Closure

只在 Documentation、Delivery 或 Integration and Closure Stage 读取。

## 目录

- [Documentation](#1-documentation)
- [Delivery](#2-delivery)
- [Integration](#3-integration)
- [Closure](#4-closure)
- [Host Close](#5-host-close)

## 1. Documentation

读取当前 worktree 中的测试和文档规则。比较 fix 分支与 base，并沿调用关系、数据流、共享模型、配置、持久化和用户流程分析影响。

检查：

- Requirements：Bug 修复是否改变 AC、范围或约束；
- Design：职责、状态、数据流、错误和回退是否变化；
- Test Cases：新增 C 系列或项目约定用例、状态、证据和 AC 映射；
- Code tests：断言、名称、fixture、Stub/Mock/Spy；
- History/版本：按项目规则更新。

文档同步按 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3.3 裁决，输出每份文档的 `updated | no-update | stale | not-applicable | retired` 及原因；状态和证据不回填合同，`closed-change` 不回写。Bug 修复必须覆盖 bug 恢复、行为变化、纯重构、test-only 四类适用变更，具体 disposition 取共享合同。

不得为了让测试通过改写旧预期。若行为没有改变，只修复实现偏差，明确记录 `no-update` 原因。

输出：

- 变更影响；
- 每份文档“已更新/无需更新/不存在”；
- 必须新增、更新、执行或暂缓的测试；
- 风险和证据。

Gate：文档与修复一致，状态写入路径和结论，`current_stage=delivery`。

## 2. Delivery

按共享运行时 Delivery policy：

1. 检查准确 diff 与工作区；
2. lint / typecheck；
3. 执行项目要求的验证或确认同 SHA CI；
4. commit 尚未交付的文档/测试变更；
5. push 正确 fix 分支；
6. 等待同 SHA CI；
7. 按需安全同步 AI-test。

禁止 force push、推错 main/master、暂存无关文件、提交秘密或使用 `--no-verify`。外部动作前写 `in_progress`，成功后记录远端证据。

Gate：必需动作完成，`current_stage=integration-and-closure`。

## 3. Integration

ASK 资源处置/集成决策时一次只问一个：

- 合并到原 base；
- 放弃合并并清理；
- 暂停并保留环境。

### 合并

1. 在 fix worktree 原子写：

```yaml
in_progress:
  operation: merge
  source: fix/F0-example
  target: develop
next_safe_action: verify merge commit before retry
```

2. 在记录的 `main_root` fetch 并验证 base；
3. 使用项目批准的 merge-only 策略合并；
4. 记录 merge SHA；
5. push 目标分支；
6. 对 merge SHA 执行合并后 CI；
7. CI 通过后写 `status=completed`。

base 在验证期间变化时重新生成并验证合并结果。merge 失败或冲突时保留状态，按 `dd-git-workflow/conflict` 处理；不得删除 worktree 或状态掩盖失败。

### 放弃

记录用户决定和未合并提交，设置 `status=abandoned`，再执行明确目标的清理。不得把 abandoned 宣称为修复已交付。

### 暂停

```yaml
status: paused
current_stage: integration-and-closure
next_safe_action: resume integration decision
```

不删除状态、worktree 或分支，不触发最终完成 ASK。

## 4. Closure

合并且 post-merge CI 通过后：

1. 验证 base 包含 merge SHA；
2. 验证工作区无未解释变更；
3. 写 Completion Receipt；
4. 清理明确的 worktree、本地 fix 分支和允许删除的远端 fix 分支；
5. 验证清理结果；
6. 保留 Receipt，活动状态可随 worktree 删除。

用户最初选择当前 worktree 时不得删除它；只清理流程拥有的临时状态，保留 completed 状态或 Receipt。

所有 repo-wide merge/cleanup 必须在记录的 `main_root` 运行，目标使用经过验证的绝对路径和精确分支名。禁止宽泛 glob、未解析变量或仓库根递归删除。

## 5. Host Close

真正完成并持久化 completed 后遵循 `dd-workflow-runtime`：

- Trae 必须 ASK，且只提供 `结束本次任务` / `还有其他任务`；
- “还有其他任务”创建新的 `workflow_id`，从新 Intake/Preflight 开始；
- “结束本次任务”后输出最终摘要；
- Codex 直接输出最终摘要。

集成选择与 Host Close 不得合并。前者决定修复是否交付，后者只决定 Trae 会话是否继续。
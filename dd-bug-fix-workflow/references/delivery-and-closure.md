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

### 1.1 先判定行为是否变化

- **纯恢复既定行为**（修复实现偏差，约定行为不变）：**不默认补齐 Requirements／Design／Test Matrix**；只处理受影响的当前合同与使用说明（按需），可以给出可验证的"本次无需修改合同"结论（附影响判定与理由），不强制制造新文档或等待批量同步；
- **修复实际上改变约定行为**（新增/删除/调整需求语义、范围、约束或公开接口）：必须标出决策/范围变化并请求用户裁决后才可继续；不得当成普通修 bug 直接放行，也不得为了让测试通过改写旧预期。

### 1.2 按需检查（仅受影响项）

- 受影响的当前合同（Requirements/Design 等当前有效文档）是否仍与修复后行为一致；
- 受影响的使用说明，以及配置、持久化、共享模型说明；
- Code tests：断言、名称、fixture、Stub/Mock/Spy 是否仍成立；
- 必须新增、更新、执行或暂缓的测试；
- History/版本：按项目规则更新。

文档同步按 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3.3 裁决，输出每份文档的 `updated | no-update | stale | not-applicable | retired` 及原因；状态和证据不回填合同，`closed-change` 不回写。Bug 修复必须覆盖 bug 恢复、行为变化、纯重构、test-only 四类适用变更，具体 disposition 取共享合同。行为变化必须更新受影响的当前 canonical 合同，不得以"历史保留"为由逃避更新。

### 1.3 证据与入口

修复证据（failing test、根因、绿灯 diff、CI run）与下一步（`next_safe_action`）归持久任务入口（看板与交接）与 runtime state、tracking Issue 入口（各自属主，tracking 见 [task-tracking](../../dd-workflow-runtime/references/task-tracking.md)），不维护独立进度镜像。

Gate：文档/合同与修复一致，或已给可验证的无需修改结论；行为变化已裁决；状态写入路径和结论，`current_stage=delivery`。

## 2. Delivery

按共享运行时 Delivery policy，**复用已有动作级授权**；只有缺少必要授权或出现新决定才 ASK：

1. 检查准确 diff 与工作区；
2. lint / typecheck；
3. 执行项目要求的验证或确认同版本 CI（必需但未运行／未绑定被交付版本 → 记明确缺口，不得放行）；
4. commit 尚未交付的文档/测试变更；
5. push 正确 fix 分支；
6. 等待同版本 CI；
7. 按需安全同步 AI-test。

未要求的动作记 `not-required`，未获授权的动作记 `not-authorized` 并停在该动作边界；conditional／no-op 阶段写清实际结论，**不伪造 CI／merge 完成**。用户已确认"修复效果"不等于 Git 交付批准，反之亦然；不因精简交付移除项目要求的人工复验。

禁止 force push、推错 main/master、暂存无关文件、提交秘密或使用 `--no-verify`。外部动作前写 `in_progress`，成功后记录远端证据。

Gate：仅当本任务要求的动作已完成并有真实证据，或动作明确不适用于本任务范围时，才进入`current_stage=integration-and-closure`。要求但缺授权/必需CI的动作停在当前边界并记录缺口，不能把“已记录阻塞”当“交付完成”。

## 3. Integration

ASK 资源处置/集成决策时一次只问一个：

- 合并到原 base；
- 放弃合并并清理；
- 暂停并保留环境。

### 合并

仅当本任务要求且已获合并授权时执行；没有新决定不重复请求已有授权。未要求合并的局部任务按已完成的实际范围收尾，不检查目标分支必须含候选，不宣称已合并或发布。

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

真正完成并持久化 completed 后，Host Close 协议以 [dd-workflow-runtime 宿主结束合同](../../dd-workflow-runtime/SKILL.md) 为唯一属主，不在此复述。

集成选择与 Host Close 不得合并。前者决定修复是否交付，后者只决定 Trae 会话是否继续。

# Shared Workflow Runtime Contract

按需读取。Preflight/恢复只读对应章节；最终完成时再读 Completion Receipt 与 Host Close。

## 目录

- [Runtime Input](#1-runtime-input)
- [Host and Capability Detection](#2-host-and-capability-detection)
- [State Schema](#3-state-schema)
- [Atomic Persistence](#4-atomic-persistence)
- [Recovery](#5-recovery)
- [Gap Scan](#6-gap-scan)
- [Stage Contract](#7-stage-contract)
- [Review Budget](#8-review-budget)
- [Completion Receipt](#9-completion-receipt)
- [Host Close](#10-host-close)

## 1. Runtime Input

```yaml
workflow_type: bug-fix
host: auto
invocation_mode: standalone
requested_entry: diagnosis
state_file: /absolute/path/bug-fix-state.json
worktree_path: null
stage_graph: {}
required_exit_stages: []
artifact_hints: {}
resolved_decisions: []
delivery_policy: project-rules
```

调用方可增加领域字段，但不得改变 `status`、Stage Gate 和 Host Close 的含义。

`invocation_mode` 只能是：

- `standalone`：直接承接用户目标的会话所有者；
- `child`：有父编排器，继承 worktree、状态事实和交付边界；
- `helper`：无独立阶段生命周期的原子能力。

父工作流调用子 Skill 时必须显式传入 `child` 或 `helper`。子 Skill 返回结果给父工作流，由父工作流决定后续 Stage 和最终 Host Close。

## 2. Host and Capability Detection

检测并记录：

- `host`：`trae`、`codex` 或 `other`；
- `structured_ask`；
- `subagents`；
- `git_write`；
- `network`；
- `ui_automation`。

判定优先级：调用参数中的明确值 → 当前宿主事实 → 项目规则 → `other`。不要仅为记录 host 询问用户；只有无法识别会改变阻塞行为时才 ASK。

能力缺失改变执行方式，不改变 Gate。例如没有子 Agent 时改为主线程多视角复核；没有结构化 ASK 时改用同义短文本；不能因此跳过复核或决定。

## 3. State Schema

```yaml
schema_version: 1
workflow_id: feature-development-20260728T090000Z-f31
workflow_type: feature-development
status: active
host: codex
requested_entry: implementation
worktree_path: /absolute/path
main_root: /absolute/path
base_branch: develop
working_branch: feature/F3.1-example
current_stage: implementation
completed_stages:
  - intake
  - environment
  - specification
  - planning
artifacts: {}
decisions: []
blocking_gaps: []
deferred_gaps: []
in_progress: {}
last_verified_at: 2026-07-28T09:00:00Z
next_safe_action: run phase-2 local gate
```

调用方可保留 `current_step`、`current_node`、`current_phase` 等兼容字段，但必须与 `current_stage` 一致。字段冲突时先根据产物和仓库证据修正，再继续。

状态值：

- `active`：正在执行；
- `paused`：保留环境，等待恢复；
- `handoff-ready`：等待明确下游接收；
- `completed`：所有必需 Gate 已通过；
- `abandoned`：用户明确放弃，已记录处置。

## 4. Atomic Persistence

写状态时：

1. 在同目录创建临时文件；
2. 写入完整 JSON/YAML 并刷新；
3. 原子替换正式文件；
4. 重新读取并验证关键字段；
5. 成功后才执行下一外部动作。

更新失败先重试一次；仍失败则停止并 ASK。不得带着未持久化的进度继续。

在 merge、push、cleanup、迁移等不可瞬时完成的动作前写：

```yaml
in_progress:
  operation: merge
  target: develop
  source: feature/F3.1-example
  started_at: 2026-07-28T09:00:00Z
next_safe_action: verify whether merge commit exists
```

动作成功后写完成证据，再清除 `in_progress`。

## 5. Recovery

恢复顺序：

1. 定位活动状态或最近 Completion Receipt；
2. 验证 worktree、分支和 base；
3. 验证记录产物、提交、CI run 和外部动作结果；
4. 对比 `current_stage`、兼容字段和证据；
5. 修正过期状态；
6. 从第一个未满足 Gate 的 Stage 继续；
7. 只询问证据无法回答的 blocker。

状态不存在时按调用方 `recovery_evidence` 重建，至少检查：

- 当前/目标分支；
- `git status`；
- base 与工作分支的提交差异；
- merge/candidate commit；
- 已有文档、测试和证据；
- 可查询的 CI 结果。

只有证据也无法判断时才从入口 Stage 开始。不得把简短的“继续”解释为重新开始。

## 6. Gap Scan

分类：

- `blocking`：requested entry 或 Exit Gate 的依赖；
- `deferred`：不阻塞当前出口，且有负责人或触发条件；
- `conflicting`：当前来源对同一事实冲突，始终 blocking。

先解决 blocking dependency，再进入 requested entry。`deferred` 不得伪装成遗漏，也不得阻止已满足的出口。

## 7. Stage Contract

```yaml
requires:
  - specification.valid
produces:
  - implementation.commit
gate:
  - related tests pass
  - evidence saved
next:
  - verification
recovery_evidence:
  - branch commits
  - test result
```

Stage Gate 与 Delivery Gate 分离：

- Stage Gate：领域产物和质量证据；
- Delivery Gate：commit、push、merge、PR、cleanup；
- 调用方可要求 commit 作为 Stage 产物，但必须明确声明，不能默认等同。

## 8. Review Budget

建议等级：

- `low`：机械迁移、格式和确定性校验；
- `standard`：普通计划、代码和文档；
- `high`：兼容性、持久化、并发、安全、公共 API、高风险 UI。

等级改变执行者数量和验证范围，不改变检查问题本身。复核发现必须修复项时自动修复并复核；重大产品或架构变化才 ASK。

## 9. Completion Receipt

若活动状态会因 worktree 删除而消失，完成前写入：

```text
$(git rev-parse --git-common-dir)/dd-workflow-receipts/<workflow-id>.json
```

Receipt 最少包含：

```yaml
schema_version: 1
workflow_id: ""
workflow_type: ""
status: completed
host: trae
completed_at: ""
worktree_path: ""
base_branch: ""
working_branch: ""
final_commit: ""
delivery_evidence: []
artifacts: {}
open_non_blocking_items: []
```

Receipt 使用原子写入，成功后才允许删除活动状态或 worktree。Receipt 是完成证明，不阻塞下一工作流。

## 10. Host Close

仅 `invocation_mode=standalone` 执行。`child/helper` 在产物验证后返回调用方，禁止触发最终 ASK。

顺序固定：

1. 验证 Workflow Gate；
2. 完成调用方要求的 Delivery Gate；
3. 原子写 `status=completed`；必要时写 Completion Receipt；
4. `host=trae` 时 ASK `结束本次任务` / `还有其他任务`；
5. 选择“还有其他任务”后接收新任务并创建新的 `workflow_id`；
6. 选择“结束本次任务”后输出最终摘要；
7. `host=codex` 时直接输出最终摘要。

Trae ASK 前可以给一句简短状态提示，但不得先给最终摘要或使用结束语。null、取消或空输入必须重复同一 ASK。

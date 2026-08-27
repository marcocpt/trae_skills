---
name: dd-workflow-runtime
description: 当 dd 系列长流程需要状态恢复、Gap Scan、Stage Gate、结构化询问、CI/UI 证据或测试位置规则时使用；通常由 Feature、Bug、Refactor、Bootstrap、Specs 工作流按需调用。
---

# DD 共享工作流运行时

## 目标

为长流程提供统一的 Preflight、状态、恢复、Gate、询问和宿主结束合同。调用方负责领域流程和质量标准；本 Skill 不编写需求、代码或测试，也不改变调用方的业务语义。

## 核心原则

1. Flexible entry, strict exit；
2. State is a checkpoint, repository evidence is truth；
3. Resolved facts are inherited, never re-asked；
4. Stage Gate is not Git Delivery Gate；
5. Review semantics stay fixed; execution cost follows risk；
6. Persist before transition；
7. Trae completion always ends with an explicit ASK；
8. No fresh evidence, no PASS/fixed/completed claim；
9. Canonical facts have one owner; derived views expire with their sources。

## 调用合同

调用方至少传递：

```yaml
workflow_type: feature-development
host: auto
invocation_mode: standalone
requested_entry: implementation
state_file: /absolute/or/resolvable/path
worktree_path: null
stage_graph: {}
required_exit_stages: []
artifact_hints: {}
resolved_decisions: []
delivery_policy: project-rules
```

`host=auto` 时按运行环境识别 Trae、Codex 或 other。只有宿主差异会阻塞执行且无法识别时才询问。

`invocation_mode` 决定会话所有权：

- `standalone`：本工作流拥有状态、最终摘要与 Host Close；
- `child`：复用父工作流环境和已解决事实，完成后返回结果，不执行 Host Close；
- `helper`：完成原子动作后立即返回调用方，不创建独立会话结束流程。

未显式传入时，只有直接响应用户目标的顶层编排器可推断为 `standalone`；被其他 Skill 调用时必须是 `child` 或 `helper`。禁止嵌套工作流重复 ASK “是否结束”。

首次进入或恢复时读取 [runtime-contract.md](references/runtime-contract.md) 的 Preflight、State、Recovery 和 Stage Contract。进入最终完成 Gate 时再读取其中的 Completion Receipt 与 Host Close；不要为普通阶段预加载整份 reference。

Stage 创建或消费规范文档、人审视图、弱模型执行包或验证证据时，读取 [artifact-contract.md](references/artifact-contract.md)；调用方只补领域检查，不复制通用字段和语义。

## Preflight

任何入口都先做轻量 Preflight：

1. 读取当前用户请求、适用的 `AGENTS.md` 和项目规则；
2. 检测 Git/worktree、宿主和可用能力；
3. 恢复状态；状态缺失或可疑时从仓库事实重建；
4. 记录 `requested_entry`，但不把它当成无条件跳步的起点；
5. 只扫描调用方声明的最小产物集合；
6. 标记产物为 `missing`、`partial`、`valid`、`stale` 或 `conflicting`；
7. 生成 `blocking_gaps`、`deferred_gaps` 和下一 Stage；
8. 只询问无法由状态、仓库或已批准文档回答的 blocker；
9. 首次写文件前确定并持久化工作环境，并按 [state](references/state.md) 的写入租约取得跨宿主唯一写者租约；取不到时保持只读或停止，不得静默并行写入。

纯查询或只读审查不创建工作流状态，也不询问 worktree。

## 状态与恢复

状态必须包含 `schema_version`、`workflow_id`、`workflow_type`、`status`、`host`、路径、当前 Stage、已完成 Stage、产物、决策和 gaps。

每个 Stage Gate 通过后立即原子写入。恢复时验证：

- 当前 worktree 与记录路径一致；
- 产物仍存在且状态未过期；
- 当前项目规则未与既有决策冲突；
- 当前 Stage 与提交、分支、CI、产物证据一致；
- `completed` 只作历史参考，不恢复为 active。

状态冲突时以仓库事实和已批准文档为准，修正状态后继续；不得机械相信过期字段，也不得因状态缺失默认从头开始。

## Stage Contract

调用方的每个 Stage 声明：

```yaml
requires: []
produces: []
gate: []
next: []
recovery_evidence: []
```

通用 Stage Gate：

1. 必需输入有效；
2. 产物存在且已验证；
3. blocking decisions 已解决；
4. 质量检查达到调用方标准；
5. 状态已持久化；
6. blocking issues 为零。

执行顺序由依赖与 Gap Scan 决定。新任务通常从入口 Stage 开始；恢复任务从第一个未满足 Gate 的 Stage 继续。不得为保持数字顺序重复已验证工作。

## 询问与执行预算

- 优先使用宿主可用的结构化 ASK；不可用时使用同义的简短选项；
- 一次只问一个阻塞决策；
- happy path 自动推进；
- 歧义、失败、冲突、破坏性分支或重大产品/架构变化才 ASK；
- null、取消或空输入视为未回答，必须重问；
- 子 Agent 不可用时在主线程完成相同检查，不降低检查语义；
- 审查按 [dd-workflow-runtime/review-gate](../dd-workflow-runtime/references/review-gate.md) 的 A/B/C 语义自检；命中高风险触发器时追加对应检查并按审查等级参数升级；检查范围和 CI 证据成本随之调整，但不删除验收条件或确定性验证；
- 升级到独立强审时，执行路径、角色合同与宿主能力按 [dd-workflow-runtime/model-routing](references/model-routing.md) 路由。
- Codex 解析到 `native-agent` 前，必须从本 Skill 的实际根目录运行 `agents/check-review-route.py`；守卫默认以 `CODEX_THREAD_ID` 只读查询 Codex thread 元数据，不接受调用方自报安全状态作为生产证据。只有退出 0 且 `native_spawn_allowed=true` 才能派生原生 `strong-reviewer`。除已证明的 `read-only` 外，`workspace-write`、`danger-full-access`、`--dangerously-bypass-approvals-and-sandbox` 或未知父 sandbox 均不得进入原生 Reviewer Gate：转已授权且可用的 `external`，否则 `BLOCKED`。
- Generic Review Backend Router v1 使用 `agents/review-backends.yaml` 与 `agents/routing-policy.yaml`；调用 `agents/dispatch-review.py` 前必须有冻结 baseline、确定性验证和外部授权/只读证据。它只执行一个最终 adapter；`max_hops=1`、`dispatch_chain` 和 `dispatch_boundary=single-backend` 禁止 backend 再次路由。Generic Router 不直接选择 `codex-native`；该 handoff 只能由已证明 current-parent provenance 的 host-native dispatcher 在 route guard 后接管。MCP 是单次 review access mechanism，不是 workflow orchestrator；adapter 不得写工作树、提交、修复或关闭 finding。

## Workflow Gate 与 Delivery Gate

Workflow Gate 判断领域工作是否完成。Delivery Gate 处理 lint、test、commit、push、PR、merge 和 cleanup，优先级为：

1. 用户当前明确要求；
2. 项目规则；
3. 调用方 Git/CI Skill；
4. 安全默认。

Delivery 失败必须记录和处理，但不得倒推为已经验证的领域产物不存在。

内容批准只通过 Workflow Gate，不授权 Git 或外部动作。只有用户当前明确授权，或工作流开始时已明确采用的项目交付策略，才能执行相应动作；禁止时记录 `not-authorized`，未要求时记录 `not-required`。后续 Stage 确实依赖该动作时才在该边界阻塞，不能反向撤销已验证的内容批准。

## 中断与暂停

中断前原子记录当前 Stage、未完成动作、最近证据和下一安全动作。

- 保留环境：设置 `status=paused`，不得删除状态；
- 放弃或清理：先记录意图和清理目标，再执行可恢复检查；
- 外部操作进行中：先写 `*_in_progress=true`，成功后再清除或归档；
- 不得在 merge、push、cleanup 等动作成功前删除唯一恢复状态。

## 宿主结束合同

只有 `invocation_mode=standalone` 的会话所有者执行本节。`child/helper` 完成后向调用方返回 `status`、产物、证据、blocker 与下一建议动作，不输出宿主最终摘要、不执行 Host Close。

会话所有者完成所有 Workflow 与必需 Delivery Gate 后，先持久化 `status=completed`。若活动状态会随 worktree 清理而消失，必须先写 Completion Receipt。

Trae：

1. 禁止先输出最终摘要并直接结束；
2. 必须使用结构化 ASK，且只提供 `结束本次任务` / `还有其他任务`；
3. “还有其他任务”接收新任务，从新 Preflight 开始，不篡改已完成记录；
4. “结束本次任务”后输出最终摘要；
5. null 必须重问。

Codex：

- 正常交付最终摘要；
- 只有用户或项目规则明确要求时才追加结束确认。

未达到完成 Gate、处于 paused 或仍有 blocker 时，不得伪装成最终完成 ASK。

## 红线

- 状态不存在就默认从头执行；
- 重问已解决事实；
- 未持久化就跨 Stage；
- 用“最新 commit 不是当前产物”否定已通过的 Workflow Gate；
- 为省 token 删除质量检查或用户可见证据；
- child/helper 抢占父工作流的 Host Close；
- 在 Trae 完成后直接结束；
- 在外部动作成功前删除唯一状态。

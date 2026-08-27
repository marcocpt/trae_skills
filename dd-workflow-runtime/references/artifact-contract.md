> 唯一属主：规范事实、派生视图、执行包和验证证据的通用语义只在本文件维护；调用方只补领域检查。

# Artifact Contract

仅在创建或消费这些产物时读取。

## 1. 事实与视图

- Requirements、Architecture／Design、测试策略各有唯一属主；事实用稳定 ID，其他产物只引用。
- 规范有效需同时可核对版本、实际内容指纹和 `approval`；文件存在不等于批准。指纹用 Git blob ID 或文件 SHA-256，分支、路径、日期、仓库 HEAD 均不能替代。
- 人审视图只含改什么、为什么、不改什么、主要风险、待裁决项和依据，不增加规范事实。
- 派生视图不得独立维护；来源变化后失效并重新派生，规范修改必须回到属主。

## 2. 弱模型执行包

每个任务单独派生：

| 字段 | 必需内容 |
|---|---|
| `task_id` | 稳定 ID、目标、依赖 |
| `sources` | 逐项路径、稳定 ID、版本、内容指纹、`approval` |
| `constraints` | 相关约束、失败路径、跨功能约束、授权边界 |
| `consumes` / `produces` | 精确输入、输出、下游接口 |
| `write_scope` | 可创建／修改／删除的文件；未列路径禁止写 |
| `steps` | 按依赖排序的可执行步骤，无 TODO／“类似任务” |
| `verification` | 精确命令／人工步骤、预期、通过条件、证据位置 |
| `stop_conditions` | `BLOCKED`／`STOP` 条件和下一安全动作 |
| `delivery_authorization` | Git／外部动作状态、范围和证据 |

- `approval={status, authority, decided_at, evidence_ref}`，只有与当前指纹绑定的 `approved` 有效。
- `delivery_authorization={status, actions, scope, authority, decided_at, evidence_ref}`；`status` 只取 `authorized | not-required | not-authorized | pending`。仅可执行 `authorized` 中明确列出的动作和范围；`pending`／缺字段在动作边界 `BLOCKED`。内容批准不授权动作。
- 组包方重读已批准原文；摘要只定位来源。只展开本任务所需冻结事实一次，使执行方无需拼接关键事实；禁止自行补齐缺失来源、权限、接口或通过条件。
- 执行前核对每个来源可定位、指纹与批准有效、依赖包与当前 worktree 一致。缺字段或不一致即 `stale`／`BLOCKED`：停止、回上游重读并重新派生，禁止手改旧包继续。

## 3. 验证证据

| 字段 | 记录 | 不能推出 |
|---|---|---|
| `verification_plan` | 计划检查、oracle、预期 | 已覆盖或已通过 |
| `existing_coverage` | 指定来源版本的 AC／路径覆盖 | 本次运行通过 |
| `run_result` | 本次命令／步骤、环境、实现／构建指纹、时间、`PASS | FAIL | NOT_RUN` | 后续版本仍有效 |
| `evidence_validity` | 与当前来源、实现／构建、环境、AC 的匹配：`valid | stale | unreadable | unverified` | 未运行也可 PASS |

`existing_coverage` 只取 `COVERED`（完整）、`PARTIAL`（部分）、`MISSING`（缺失）、`DEFERRED`（已批准延后，含负责人／触发条件）、`UNVERIFIED`（无法核对，设 blocker）。测试存在或 `COVERED` 都不等于运行通过。只有必需 `run_result=PASS`、`evidence_validity=valid`、AC／失败路径无缺口且 blocker 为零，Gate 才能 `PASS`。

计划写规范；覆盖快照、运行结果、审查发现和进度写既有状态／证据记录，不回填冻结合同。

## 4. 最小化

- 按耦合和可独立验证性拆任务；不用固定字数、token 或分钟阈值裁内容。
- 删除重复背景和解释，不删除 AC、失败／回滚路径、通过条件、来源指纹或授权边界。
- 不要求新顶层 Skill、状态系统或生成器；复用现有计划、状态和证据产物。

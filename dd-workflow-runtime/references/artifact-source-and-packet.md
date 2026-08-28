> 拆分来源：`artifact-contract.md` §1/§2/§2.1/§5。唯一属主：事实、source_manifest、执行包与最小化语义只在此维护。

# Artifact Source and Packet

仅在创建或消费来源、执行包时读取。生命周期、验证证据见对应分文件。

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
| `source_manifest` | 每个被引用来源的完整 metadata **唯一一次**定义（见 §2.1） |
| `sources` | Task 级引用：`{ref, anchors}`，不复制 path/version/digest/approval |
| `constraints` | 相关约束、失败路径、跨功能约束、授权边界 |
| `consumes` / `produces` | 精确输入、输出、下游接口 |
| `write_scope` | 可创建／修改／删除的文件；未列路径禁止写 |
| `steps` | 按依赖排序的可执行步骤，无 TODO／“类似任务” |
| `verification` | 精确命令／人工步骤、预期、通过条件、证据位置 |
| `stop_conditions` | `BLOCKED`／`STOP` 条件和下一安全动作 |
| `delivery_authorization` | Git／外部动作状态、范围和证据 |

### 2.1 Source Manifest（唯一属主）

完整 source metadata 在一个 Phase plan 中**只出现一次**；Task 只写 `sources: [{ref, anchors}]`。字段名不得另造同义词：

```yaml
source_manifest:
  SPEC-REQ:
    stable_id: SPEC-REQ
    path: docs/specs/feature/requirements.md
    digest: sha256:current-content
    approval:
      status: approved
      authority: user-or-project-role
      decided_at: 2026-08-28
      evidence_ref: repository-or-thread-reference
    version_label: v1.0  # optional, not a stale Gate input

task:
  sources:
    - ref: SPEC-REQ
      anchors: [FR-001, AC-001]
```

规则：执行前同时验证 manifest digest、source digest 与 approval→digest 绑定。`version_label` 只作可选人类标签，不作为 stale Gate 输入。缺任一绑定或不一致即 `stale`／`BLOCKED`。

- `approval={status, authority, decided_at, evidence_ref}`，只有与当前指纹绑定的 `approved` 有效。
- `delivery_authorization={status, actions, scope, authority, decided_at, evidence_ref}`；`status` 只取 `authorized | not-required | not-authorized | pending`。仅可执行 `authorized` 中明确列出的动作和范围；`pending`／缺字段在动作边界 `BLOCKED`。内容批准不授权动作。
- 组包方重读已批准原文；摘要只定位来源。只展开本任务所需冻结事实一次，使执行方无需拼接关键事实；禁止自行补齐缺失来源、权限、接口或通过条件。
- 执行前核对每个来源可定位、指纹与批准有效、依赖包与当前 worktree 一致。缺字段或不一致即 `stale`／`BLOCKED`：停止、回上游重读并重新派生，禁止手改旧包继续。

## 5. 最小化

- 按耦合和可独立验证性拆任务；不用固定字数、token 或分钟阈值裁内容。
- 删除重复背景和解释，不删除 AC、失败／回滚路径、通过条件、来源指纹或授权边界。
- 不要求新顶层 Skill、状态系统或生成器；复用现有计划、状态和证据产物。
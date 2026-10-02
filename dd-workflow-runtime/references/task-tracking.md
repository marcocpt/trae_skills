# 外部任务绑定与投影

本文件唯一拥有"工作流 ↔ 外部任务系统"的绑定、投影与写回语义，以及 `tracking` 子对象的字段形状与枚举词表。`runtime-contract.md` 只出现 `tracking` 字段名与属主链接，不复制本文件规则。

按需读取：绑定任务、写 checkpoint、跨机器恢复、同步看板时读取。

## 1. 定位

外部任务系统（当前只支持 GitHub Issue）是**跨设备任务索引、人类看板卡片和恢复定位入口**。

它不是：

- 不是工作流状态；
- 不是 Gate、CI、Git 或 artifact 证据；
- 不是跨机器互斥锁（§9.3 只做接管冲突检测）。

事实源仍是 Git、已批准文档和 CI 结果。

### 1.1 两类数据的边界

| 类别 | 内容 | Issue → runtime |
|---|---|---|
| 定位元数据 | `repository`、`issue_number`、`workflow_id`、branch、source checkpoint ref | **允许**，只作定位输入 |
| 工作流事实 | Stage、Gate 结论、`candidate_sha`、CI 结论、产物有效性、完成结论 | **禁止**，只能由仓库证据重建 |

**Issue 可以告诉你去哪找，不可以告诉你已经 PASS 了什么。**

## 2. 状态字段

`tracking` 是可选字段，写在共享 runtime state 中。字段形状与枚举词表由本文件拥有：

```yaml
tracking:
  provider: github              # 受支持 provider；扩展新 provider 必须在本文件登记
  repository: owner/repo        # provider=github 时必填
  issue_number: 286             # provider=github 时必填
  sync: synced                  # synced | not-synced | not-authorized | disabled
  sync_reason: null             # 最近一次非 synced 的最小原因，供恢复判断是否重试
  pending_checkpoint: null      # {checkpoint_id, digest, prepared_at}；远端动作前先落盘
  last_checkpoint_ref: null     # 已确认投递的远端评论标识
```

约束：

- `tracking` 缺失或 `null` 表示未绑定，**不得阻塞任何 Workflow Gate**，也不得因此 ASK；存在该对象时 `provider` 必须是受支持值；
- `sync` 四种语义互不混用：

| 取值 | 含义 | 后续 |
|---|---|---|
| `synced` | 最近一次写回成功 | 正常 |
| `not-synced` | 绑定存在，最近一次写回失败或校验失败（含远端不可达、Issue 不存在、remote 无法解析） | 继续推进，下一写回时机重试 |
| `not-authorized` | 项目未授权该远端动作 | 跳过该远端动作并继续，不重试到用户授权 |
| `disabled` | 用户明确关闭投影 | 不再尝试写回 |

- `sync_reason` 只记最小原因（如 `remote-unreachable` / `issue-missing` / `no-policy`），不是 Gate 证据；
- `pending_checkpoint` 用于 crash-safe 防重（见 §6.3），`last_checkpoint_ref` 只记已确认投递的评论，两者都不是 Gate 证据；
- 派生视图（看板列名、当前执行者、Issue 里的"当前阶段"）**一律不写入 state**。

## 3. 绑定规则

- 绑定时机：Environment Stage，worktree 与分支确定之后、Environment Gate 之前；
- 已存在 `tracking` 时复用并校验 `repository` / `issue_number`，不重建；
- `repository` 由当前仓库 remote 推导，不由模型猜测；推不出来时记 `sync=not-synced` + `sync_reason=remote-unresolvable`，继续推进；
- 一张 Issue 对应一个可独立调度的工作单元：一个分支、一个 worktree、一个 workflow；
- 同一 branch/worktree 上连续开发的多个 Phase **不拆成多张 Issue**；
- 需要独立 worktree、独立 Agent、独立 branch、独立完成或阻塞时，才用 Sub-Issue。

## 4. 绑定失败矩阵

| 情形 | `sync` | `sync_reason` | 是否重试 | 是否 ASK | 是否允许 workflow 继续 |
|---|---|---|---|---|---|
| 绑定有效 | `synced` | — | — | 否 | 是 |
| 远端不可达 / remote 无法解析 | `not-synced` | `remote-unresolvable` | 下一写回时机重试 | 否 | 是 |
| Issue 不存在或已转移 | `not-synced` | `issue-missing` | 否（需重新绑定） | 否 | 是 |
| 项目未授权 | `not-authorized` | `no-policy` | 否 | 否 | 是 |
| 用户明确禁用 | `disabled` | — | 否 | 否 | 是 |

**任何一行都不得阻塞 Workflow Gate。**

## 5. Issue 正文只放稳定信息

正文变化频率低，不随进度重写：

```markdown
## Goal

<一段话>

## Workflow

Type: feature-development
Feature: F3.3

## Workspace

Branch: feature/F3.3-visual-region-split

## References

Requirements: ...
Design: ...
Plan: ...
```

**禁止写入 worktree 绝对路径。** Issue 是跨机器的，路径换电脑即失效。worktree 路径由 branch 按 [dd-git-workflow/worktree](../../dd-git-workflow/references/worktree.md) 的布局推导。

## 6. 进度用 checkpoint 评论

不重写正文，只在关键时机追加评论。

格式：

```text
<!-- dd-checkpoint:v1 -->

workflow_id: feature-development-20261002T000000Z-f31
workflow_type: feature-development
checkpoint_id: cp-20261002T093000Z-a1b2
host: codex
executor: Trae CN
stage: implementation
phase: 3
state_status: handoff-ready
remote: sha-reachable

Current:
Phase 3 实现已完成，Local Gate PASS，外审 R2 有 1 项 finding。

Next:
修复 R2-F-01 → targeted test → R3 review。

Branch:
feature/F3.3-visual-region-split

SHA:
abc12345

Blocker:
none

Taken over from:
none
```

字段规则：

- `host` 原样消费 [runtime-contract.md](runtime-contract.md) §2 的 canonical 取值，**本文件不重列词表**；
- `state_status` 原样消费 [runtime-contract.md](runtime-contract.md) §3 的 canonical status 取值，**本文件不重列词表**；
- `executor` 是**非 canonical 显示标签**（如 `Trae CN` / `WorkBuddy` / `OpenCode`）：只用于人读"这是哪个 App 做的"；**不参与 Gate 与恢复判定，不写入 runtime state**；恢复与判定的宿主依据仍是 canonical `host`；
- `phase` 只对 `feature-development` 有意义，其他工作流省略；
- `checkpoint_id` 本地生成、稳定，用于 crash-safe 防重与接管溯源；
- `remote` 取值 `sha-reachable` / `local-only`，由本文件拥有：`sha-reachable` 表示该 SHA 已在允许的远端 ref 上可达，`local-only` 表示工作内容仅在本机（未 push 或有未提交修改）；
- `SHA` 是本轮 checkpoint 对应的提交，不是 candidate SHA，也不等于 CI 证据；
- `Taken over from` 填上游宿主标识与**来源 checkpoint_id**，首轮填 `none`；
- `<!-- dd-checkpoint:v1 -->` 标记固定，供机械定位。

### 6.1 如何选最新 checkpoint（待取证，尚未冻结）

不得只按"全文最后一次 marker"。至少按 **marker + `workflow_id`** 过滤，并保存具体 comment ref。过滤规则（含同一 Issue 上其他 workflow、伪造 marker、重复 checkpoint、分页与排序）尚未冻结：需先在真实 GitHub 仓库完成最小探针取证，取证通过前不得声称可机械选取最新 checkpoint。

### 6.2 写回时机（只有这五个）

1. 创建或接管任务；
2. Stage 跨越（每个 Stage Gate 通过后）；
3. `blocking_gaps` 非空，即 BLOCKED；
4. `paused` / `handoff-ready` / 换 Agent / 换机器——**在释放写入租约之前**；
5. `status=completed`。

### 6.3 写回顺序（crash-safe）

```text
1. 原子持久化 checkpoint 源字段 + pending_checkpoint{checkpoint_id, digest, prepared_at}
2. 执行远端写回
3. 成功后保存 last_checkpoint_ref，清除 pending_checkpoint
4. 释放写入租约
5. 下游接管
```

恢复时若 `pending_checkpoint` 仍存在：先按 `checkpoint_id` / `digest` 查询远端是否已投递——已投递则只补 `last_checkpoint_ref` 并清除 pending；确认未投递才重试。**重复评论次数为零。**

该顺序镜像 runtime 对外部审查用 `client_request_id` 的"先准备、后提交、再确认"。

### 6.4 失败边界

- 普通写回失败：记 `sync=not-synced`，**Workflow 继续**，不回滚已通过 Gate；
- 跨 Agent / 跨机器 handoff 的 checkpoint 失败：**handoff 动作保持 pending**，不得宣称已移交；
- 二者不互相替代：写回失败绝不回滚 Gate，也绝不伪造成功移交。

## 7. checkpoint 不是证据

Issue 评论里写 `CI PASS` 不等于 `full_ci_run=PASS`。接管方必须按调用方合同重新核对 Run ID、Head SHA、Conclusion 与 `candidate_sha`。

[dd-feature-development-workflow](../../dd-feature-development-workflow/SKILL.md) 的候选不变量（`candidate_review.sha == full_spec_gap.sha == full_ci_run.head_sha == candidate_sha`）语义仍由其属主拥有，本文件不复制，也不因 Issue 内容放松。

仅 §1.1 的定位元数据可从 Issue 取用。

## 8. 授权

写 Issue 评论、改看板状态是远端外部动作，按 [runtime-contract.md](runtime-contract.md) §7，内容批准不构成外部动作授权。

因此由**目标项目的 `AGENTS.md` 一次性授权**，避免在每次 checkpoint 时反复 ASK。项目 `AGENTS.md` 增加：

```markdown
## GitHub task tracking policy

对于已绑定 tracking 的 Feature / Bug 工作流，允许 Agent 更新对应 GitHub Issue、
追加工作流 checkpoint 评论、同步看板状态列。

这些操作仅用于工作流状态投影，不构成 commit、push、PR、merge、CI 或发布授权。
```

额外约束：

- 项目 `AGENTS.md` 未写上述授权时，**只停止该远端 tracking 动作**，记 `sync=not-authorized`，**后续 Workflow Stage 继续**，不得静默执行，也不得停止工作流；
- 只有用户正在请求"完成跨机 handoff"这类本身依赖 checkpoint 的动作时，才可阻断"handoff 完成声明"；
- **创建 Issue 属于新建远端对象**：仅在当前用户授权或项目 tracking policy 已明确覆盖创建 Issue 时才允许；允许执行时必须在 checkpoint 或本轮摘要中报告 Issue 号；
- 不存在 `tracking` 绑定时，不主动创建 Issue。

## 9. 跨机器恢复与接管

### 9.1 恢复流程

```text
读 Issue
  → 按 marker + workflow_id 定位最新 checkpoint
  → 只取定位元数据：repository / branch / workflow_id / source checkpoint ref
  → 判断 remote 字段：sha-reachable 才可能跨机恢复工作内容
  → git fetch
  → 按 dd-git-workflow 创建或定位 worktree
  → 从 Git / 文档 / CI 重建并验证 runtime state
  → 取得写入租约
  → 从仓库证据推出 next_safe_action 并继续
```

### 9.2 工作内容可达性（任务可发现 ≠ 工作内容可恢复）

- checkpoint 的 `remote=local-only` 时，该 checkpoint 明确为**仅定位，不可跨机恢复**，不得宣称 handoff-ready；
- 只有 `remote=sha-reachable` 且必要修改均已持久化，才可声明跨机 handoff ready；
- push 是否发生仍由原 delivery 授权边界决定，**tracking 不得扩大 push 授权**；
- Issue 只提供 branch locator。分支的私有 / 共享可见性与同步方式仍完全由 [dd-git-workflow/branch](../../dd-git-workflow/references/branch.md) 重判（`branch.<分支名>.agentShared` 未知即未知），不得因 Issue 上有该分支就推定为 shared。

### 9.3 接管规则（碰撞检测，不是互斥）

本文件**没有原子 compare-and-set 原语**，因此下述规则只能提供接管冲突检测，不提供互斥。文档不得宣称已解决跨机器互斥。

1. 正常接管只接受最新 checkpoint 的 `state_status=handoff-ready`；`active` 不得静默接管；
2. 接管声明必须绑定具体来源 `checkpoint_id`；
3. 同一来源 `checkpoint_id` 出现两个接管声明 → 判冲突并 BLOCKED，交用户裁决；
4. 旧宿主恢复后先检查是否出现更新的接管声明，若已被接管则**停止写入**；
5. 找不到上游 checkpoint，却发现其他宿主持有同一 workflow 痕迹 → BLOCKED 并询问，不得静默接管。

若将来要做真正的弱锁，必须先选定并验证具有原子条件更新能力的后端，再单独设计 lease / fencing token。

## 10. 看板投影

投影方向：runtime state → 看板（工作流事实）。禁止反向回写。

列：

| 列 | 含义 |
|---|---|
| 待处理 | **external-only backlog state**：Issue 已建但尚未进入 workflow，此时 runtime 不存在，它不是任何 workflow stage 的投影 |
| 开发中 | 内容生产阶段 |
| 待验证 | 候选冻结与确认阶段 |
| 待收尾 | 交付与收尾阶段 |
| 完成 | runtime `status=completed` |

阶段映射（本表是本仓库唯一映射表）：

```text
feature-development
  intake / environment / specification / planning / implementation / documentation → 开发中
  final-candidate / confirmation                                                   → 待验证
  delivery / closure                                                              → 待收尾

bug-fix
  intake / environment / diagnosis-and-repair                → 开发中
  sync-and-ci / user-verification / documentation            → 待验证
  delivery / integration-and-closure                         → 待收尾

两者
  status=completed → 完成（优先于阶段映射）
```

**覆盖完备性要求**：Feature 与 Bug 的 canonical Stage 列表中，每个适用 Stage 必须恰好映射一次；新增 Stage 而映射未更新即视为合同违约（由合同测试机械校验）。

阻塞表达：用 GitHub label `blocked`，因为阻塞与工作阶段正交，占用状态列会丢失被阻塞前所在 Stage；看板配置一个 `label:blocked` 过滤视图补足视觉显著性。`status=paused` **不等于阻塞**。

## 11. 传输层

核心语义不依赖具体传输方式。

```text
优先：项目已配置的 GitHub connector / MCP
否则：gh CLI
```

不得把"必须支持某个 MCP"写进合同——那会让部分 Agent App 直接不可用。

## 12. 与相邻 Skill 的边界

| Skill | 拥有什么 | 本文件不做什么 |
|---|---|---|
| `dd-workflow-runtime` | state schema、Stage Gate、Recovery、Host Close、`host` 与 `status` 的 canonical 取值 | 不改其语义，只加可选字段；不重列其枚举 |
| `dd-git-workflow` | 分支模型、worktree 布局、私有/共享可见性与清理 | 不复制路径推导，不在 Issue 里存绝对路径，不推定分支可见性 |
| `dd-project-bootstrap-workflow` | 项目治理与基础环境 | **第一阶段不自动创建、不自动绑定、不自动投影**；runtime schema 容忍 `tracking` 不等于默认覆盖 |
| `multi-agent-branch-integration` | 多 Agent 分支可见性、同步与集成门禁 | 不管分支集成，只管任务索引与恢复定位 |
| `dd-later-tracking` | LATER 项的文件即 ID 体系 | **不改 LATER**。LATER 提升为开发任务时，Issue 正文引用 LATER 文件路径，不搬运内容 |

## 13. 红线

- 把 Issue 或 checkpoint 当作 Gate、CI、Git 或 artifact 证据；
- 把工作流事实从 Issue 反向回写进 runtime state（定位元数据除外）；
- 用 Issue 承载 Stage / Gate / candidate SHA 的完整状态，制造第二事实源；
- 在 Issue 里写 worktree 绝对路径；
- 因 `tracking` 缺失、绑定失败、写回失败或未授权而阻塞 Workflow Gate；
- 未写 checkpoint 就释放写入租约并宣称已移交；写回失败却宣称 handoff 完成；
- 从 `state_status=active` 的 checkpoint 静默接管；
- 把接管冲突检测描述成"互斥锁"或"弱锁"；
- 把 `paused` 当成阻塞；
- 因 Issue 上存在某分支就推定其可见性或同步方式；
- 重列 runtime 已有的 `host` 或 `status` 枚举；
- 把看板投影授权解释成 commit、push、PR、merge、CI 或发布授权。

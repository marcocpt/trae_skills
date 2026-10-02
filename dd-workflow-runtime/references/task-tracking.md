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

- 对 `feature-development` 与 `bug-fix`：`tracking` 缺失或 `null` 表示**从未尝试**；对象存在但 `issue_number` 为 `null` 表示**已完成绑定尝试但未形成绑定**（授权条件不满足、创建失败或对账失败，见 §3.1 与 §4）。**本合同生效前**持久化的 state 里的缺失/`null` 属第三种含义——历史未分类，按 §3.2 迁移，**不得直接当作从未尝试**。三者都**不得阻塞任何 Workflow Gate**，也不得因此 ASK；
- **上述两类工作流的新旧 null 机械判别式**：以 state 的 `schema_version` 判定——`>= 2` 的 `null` 是"从未尝试"（本合同语义）；`< 2`（含缺失、按 schema 0 兼容读取）的 `null` 是历史未分类，走 §3.2。恢复器不得靠推断工作流阶段来猜版本；
- `dd-project-bootstrap-workflow` **不使用上述三态判别**，其 `tracking` 语义按 §12 与 [state.md](state.md) 保持不变（缺失或 `null` 仍按未绑定读取，不走 §3.2 迁移）；上面的"已尝试未绑定"变体同样只适用于上述两类工作流；
- 已尝试未绑定时必须写出该对象：填 `sync` 与 `sync_reason`（必要时 `provider` / `repository`，无法推导时允许为 `null`），`issue_number` / `last_checkpoint_ref` 保持 `null`；对象存在时 `provider` 若非 `null` 必须是受支持值。这样"尝试并记录"在状态层可表示，不依赖把失败塞进 `tracking: null`；
- 对 `feature-development` 与 `bug-fix` 工作流，Environment Gate **必须已完成一次 tracking 绑定尝试并把结果落盘**：已绑定一张 Issue，或已按 §4 记 `sync` 与 `sync_reason`；**未尝试且未记录就通过 Gate 属违规**（§13）。这里的硬约束是"必须尝试并记录"，不是"绑定必须成功"。默认动作是新建 Issue（§3、§3.1）。`dd-project-bootstrap-workflow` **第一阶段**不在此约束内（见 §12）；
- `sync` 四种语义互不混用：

| 取值 | 含义 | 后续 |
|---|---|---|
| `synced` | 最近一次写回成功 | 正常 |
| `not-synced` | 最近一次**尝试或写回**失败（**可能尚未绑定**：含远端不可达、创建结果不确定、多匹配歧义、Issue 不存在、remote 无法解析、provider 不可用） | 继续推进；**是否重试及允许重试的动作以 §4 对应 `sync_reason` 为准** |
| `not-authorized` | 当前动作没有有效授权（项目未授权该远端动作，或用户明确拒绝该动作） | 跳过该远端动作并继续，授权条件发生变化前不重试 |
| `disabled` | 用户明确关闭投影 | 不再尝试写回 |

- `sync_reason` 只记最小原因（如 `remote-unresolvable` / `issue-missing` / `no-policy` / `no-issue-capable-remote` / `provider-unavailable` / `user-declined` / `binding-ambiguous` / `create-outcome-unknown` / `legacy-tracking-unknown`），不是 Gate 证据；
- `pending_checkpoint` 用于 crash-safe 防重（见 §6.3），`last_checkpoint_ref` 只记已确认投递的评论，两者都不是 Gate 证据；
- 派生视图（看板列名、当前执行者、Issue 里的"当前阶段"）**一律不写入 state**。

## 3. 绑定规则

- 绑定时机：Environment Stage，worktree 与分支确定之后、Environment Gate 之前；
- **默认动作是新建**：`feature-development` 与 `bug-fix` 工作流在没有既有绑定 Issue 时，必须在 Environment Gate 前创建一张并绑定；创建前先按 §3.1 对账，新建属窄范围常设授权（范围与禁止项见 §8.1）；
- 新建时按 §5 骨架填写标题与稳定信息正文（含 `Workflow ID` 行），**禁止写入 worktree 绝对路径**；创建后必须在本轮摘要或 checkpoint 中报告 Issue 号；
- **只有已绑定**（`issue_number` 非 `null`）的 `tracking` 才复用并校验 `repository` / `issue_number`，不重建；对象存在但 `issue_number` 为 `null` 属已尝试未绑定（§2），按 §3.1 与 §4 的对应原因恢复，**不得当成既有绑定而跳过对账**；
- `repository` 由当前仓库 remote 推导，不由模型猜测；推不出来时记 `sync=not-synced` + `sync_reason=remote-unresolvable`，继续推进；
- 一张 Issue 对应一个可独立调度的工作单元：一个分支、一个 worktree、一个 workflow；
- 同一 branch/worktree 上连续开发的多个 Phase **不拆成多张 Issue**；
- 需要独立 worktree、独立 Agent、独立 branch、独立完成或阻塞时，才用 Sub-Issue；
- 绑定后在 Issue 正文 Workflow 节写入 `Workflow ID`——它是关闭防线（§6.5）与远端选取（§6.1 第 3 条）识别绑定的唯一远端来源；合同前旧卡缺失该行时，防线 fail-safe 跳过。

### 3.1 创建的幂等与崩溃恢复

创建 Issue 是自动尝试的远端副作用，崩溃或响应丢失会让本地 state 可能尚未记录有效绑定。为避免同一 workflow 出现第二张 Issue，恢复时按固定顺序处理：

1. **先对账再创建**：创建前按 `Workflow ID`（§3 末条）检索本仓库已有 Issue；命中**唯一且可信**的匹配即直接绑定，不新建。可信判定沿用 §6.1 的来源信任原则——`Workflow ID` 与本 workflow 完全一致、该 Issue 未被其他 workflow 绑定，且作者关联在 §6.1 的 association 信任边界内（公开仓库里第三方预先创建的同号 Issue 因此不被自动绑定）。
2. **结果不确定时先查找、不盲目重试**：创建调用超时、响应丢失或进程崩溃后，恢复必须先按 `Workflow ID` 查证；**禁止跳过查证直接重试创建**。
3. **不确定后的零命中不等于未创建**：查证为零命中时，只有 provider 的**权威对账机制**或 provider 原生幂等键能证明首次创建未发生，才允许再次创建；否则记 `not-synced` + `sync_reason=create-outcome-unknown` 并继续工作流，**不得把普通搜索的零结果当作"远端没有创建"**。
4. **多匹配 fail-safe**：同一 `Workflow ID` 命中多张 Issue 时不自动选择、不删除任何一张，记 `not-synced` + `sync_reason=binding-ambiguous`（§4），继续工作流；不把裁决当作 Environment Gate 的前置条件。
5. **先持久化再后续写**：取得 Issue 号后先原子写入 `tracking`，再进行 §6 checkpoint、§6.5 关闭与 §10 投影。

### 3.2 旧 state 中 `tracking` 缺失或 `null` 的迁移

本合同把 `tracking: null` 的含义从"未绑定"收窄为"从未尝试"。收窄只对**本合同生效后**写入的 state 成立；历史 state 的 `null` 可能是"当年未强制、未授权、被用户拒绝、或创建失败但旧 schema 无法表达"，**不得反向解释成更强的事实**。

迁移规则：

1. **适用范围（机械判别）**：`schema_version` 缺失或 `< 2`、且恢复时 `tracking` 缺失或为 `null` 的 Feature / Bug 工作流（含已越过 Environment Gate 的）。判别只依据 `schema_version`，不依据 `current_stage` 或其他字段推断。
2. **不解释为从未尝试**：把该情形分类为历史未分类，并按 §4 记 `not-synced` + `sync_reason=legacy-tracking-unknown`（`legacy-tracking-unknown` 只是 `sync_reason` 取值，不是新增状态字段或枚举）。
3. **只读对账优先**：恢复时**仅执行 §3.1 规则 1 中的只读检索与可信匹配部分**（按 `Workflow ID` 检索），**不得进入 §3.1 的创建动作**，也**不得仅凭旧 `tracking=null` 自动创建 Issue**。
4. **零命中后仍不得创建**：对账零命中时保持 `legacy-tracking-unknown` 并继续 Workflow（零命中不证明未创建，见 §3.1 规则 3）。**§8.1 的常设授权与 §3 的"默认动作是新建"都不足以从该状态触发创建**——历史 `null` 可能正是"用户当年拒绝创建"，常设授权无法消除这份不确定性。解除条件只能是新的显式事实：当前用户明确要求创建，或项目政策明确解除该状态；满足其一后才按 §8.1 进入创建流程。
5. **迁移后按当前模型持久化并升版**：对账完成后把结果按当前 §2 / §4 重新落盘（绑定成功记 Issue 号，否则记对应 `sync` / `sync_reason`），并把 `schema_version` 升为 `2`——否则实现可能只写新的 `tracking` 对象却保留旧版本号，让下一次恢复继续按 legacy 分支判断。使后续恢复不再依赖本节。

## 4. 绑定失败矩阵

| 情形 | `sync` | `sync_reason` | 是否重试 | 是否 ASK | 是否允许 workflow 继续 |
|---|---|---|---|---|---|
| 绑定有效 | `synced` | — | — | 否 | 是 |
| 远端不可达 / remote 无法解析 | `not-synced` | `remote-unresolvable` | 下一写回时机重试 | 否 | 是 |
| Issue 不存在或已转移 | `not-synced` | `issue-missing` | 否（需重新绑定） | 否 | 是 |
| 项目未授权 | `not-authorized` | `no-policy` | 否（授权条件变化后重新评估） | 否 | 是 |
| 用户明确要求不创建 Issue | `not-authorized` | `user-declined` | 否（授权条件变化后重新评估） | 否 | 是 |
| 同一 `Workflow ID` 命中多张 Issue | `not-synced` | `binding-ambiguous` | 否（需人工裁决绑定哪一张） | 否 | 是 |
| 创建结果不确定且无权威对账结论 | `not-synced` | `create-outcome-unknown` | 仅重试权威对账/确认；在权威证明首次创建未发生前**不得重试 create** | 否 | 是 |
| 旧 state 的 `tracking` 缺失或 `null`（历史未分类，见 §3.2） | `not-synced` | `legacy-tracking-unknown` | 否（仅只读对账；不得据旧 `null` 自动创建） | 否 | 是 |
| 无 Issue 能力的远端（remote 指向未登记的 provider） | `not-synced` | `no-issue-capable-remote` | 否（需改用既有绑定或换 provider） | 否 | 是 |
| 认证/权限不足或 provider 不可用 | `not-synced` | `provider-unavailable` | 下一写回时机重试 | 否 | 是 |
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
Workflow ID: feature-development-20261002T000000Z-f31

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

### 6.1 如何选最新 checkpoint（2026-10-02 真实 GitHub 探针冻结）

不得只按"全文最后一次 marker"。选取算法（探针证据与完整脚本：
`docs/AI/task-tracking-projection-evidence/L02-checkpoint-probe.md`）：

> 机械实现（canonical）：[checkpoint_select.py](../scripts/checkpoint_select.py)——本节文字拥有语义，该脚本是其唯一运行时实现，须与本节一致并由合同测试固定；探针脚本仅作取证证据。

1. `GET /repos/{owner}/{repo}/issues/{n}/comments?per_page=100` 全量翻页（跟随 `Link: rel="next"`）。**禁用** `sort`/`direction` 与 `since`：该端点没有 sort/direction 参数（GitHub REST 合同：单 Issue 评论按 comment id 升序返回），`since` 按 `updated_at` 过滤（探针实测：会把早于游标创建但被编辑过的评论重新纳入）。
2. **完整必填字段校验**：body 以固定 marker `<!-- dd-checkpoint:v1 -->` 开头，且能解析出全部**恢复实际消费**的字段：`workflow_id`、`workflow_type`、`checkpoint_id`、`host`、`state_status`、`remote`、`Branch`、`SHA`。缺任一判 **malformed**（伪造/损坏），整条丢弃——只有 marker + workflow_id + checkpoint_id 的最小伪造不够格。
3. 按 `workflow_id == 当前工作流` 过滤；同一 Issue 上其他工作流的 checkpoint 不参与。
4. 同一 `checkpoint_id` 出现多条评论：取 comment id 最小者（首次投递）参与选取，其余按重复计数记录（与 §6.3 crash-safe 防重互补，不改变其先查重再投递的次序）。
5. 剩余评论取 **comment id 最大**者为最新 checkpoint（GitHub 合同：单 Issue 评论按 id 升序返回、comment id 全局唯一；探针实测 5/5 单调一致，id 序即创建序，`created_at` 秒级并列不作排序键）。保存该评论的 comment ref（comment id、html_url、created_at、updated_at）。
6. **编辑策略**：编辑不改 comment id 与 created_at（探针实测），故**排序键**稳定；但编辑可改变**评论资格**——改掉 marker 或任一必填字段 → malformed 丢弃，改 `checkpoint_id` → 视为新 checkpoint（交由步骤 4 防重）。checkpoint 评论约定 **append-only**：正文更正只允许追加，不得改写既有字段；恢复方每次抓取按上述规则**重新评估资格**，不缓存资格结论。
7. **机械可核计数**：每次选取必须输出 `fetched_total / marker_candidates / malformed / untrusted / after_workflow_filter / duplicates` 六个计数，防止解析失败被静默吞掉（探针当日曾因 jq 正则旗标误用出现 `parsed=0` 假象而无所察觉）。
8. **来源真实性（防线场景必选）**：checkpoint 评论作者采用 GitHub author association 白名单（`author_association` ∈ OWNER / COLLABORATOR / MEMBER）作为信任边界——该边界是**关联身份 allowlist，不等价于仓库写权限判定**；不可信来源（NONE / CONTRIBUTOR 等）整条丢弃并计 `untrusted`。guard 场景必选启用；工作流正常 checkpoint 由 owner 令牌发布，天然满足。迁入组织仓库或需真实权限判定时，须另行升级选取实现并重新取证。

### 6.2 写回时机（只有这六个）

1. 创建或接管任务；
2. Stage 跨越（每个 Stage Gate 通过后）；
3. `blocking_gaps` 非空，即 BLOCKED；
4. `paused` / `handoff-ready` / 换 Agent / 换机器——**在释放写入租约之前**；
5. `status=completed`；
6. `status=abandoned` 处置（放弃任务）——写 `state_status=abandoned` 的 checkpoint，并按 §6.5 同步看板与关闭 Issue。

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

### 6.5 Issue 关闭规则

关闭已绑定 Issue 只有**两个合法入口**：

1. Closure：`status=completed` 后，顺序固定——写最终 checkpoint（写回时机 5）→ 同步看板「完成」→ close；
2. `abandoned` 处置：写 `state_status=abandoned` 的 checkpoint（写回时机 6）→ 把对应卡片从看板移出（archive item）→ close。

除以上两个入口外不存在第三种合法关闭路径。工作流处于 `active` / `paused` / `handoff-ready` 期间**禁止关闭已绑定 Issue**；确需中途放弃，先走 `abandoned` 处置。外部（非本工作流会话）直接关闭已绑定 Issue 不产生任何投影语义——看板与恢复结论仍以最新 checkpoint 和 runtime state 为准（见 §1.1、§10）。恢复时若 runtime 已为 terminal 状态（completed / abandoned）而 Issue 仍 open，按最新 checkpoint 幂等补 close。

可选机械防线：目标项目安装**两个文件**——本模板复制到 `.github/workflows/dd-checkpoint-close-guard.yml`，canonical 选取脚本 [checkpoint_select.py](../scripts/checkpoint_select.py) 复制到目标仓库 `scripts/dd/checkpoint_select.py`（模板不含选取逻辑，避免第二套实现）。防线只做一件事：Issue 被关闭时，按 Issue 正文 `Workflow ID` 调用 §6.1 选取最新合法 checkpoint，其 `state_status` 非 completed / abandoned 则自动评论提醒并 reopen；正文缺失 `Workflow ID`（合同前旧卡）时 fail-safe 跳过，不做跨 workflow 判定。安装与否不改变任何 Gate。

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
追加工作流 checkpoint 评论、同步看板状态列；关闭对应 Issue 仅限 §6.5 两个合法入口。

这些操作仅用于工作流状态投影，不构成 commit、push、PR、merge、CI 或发布授权。
```

额外约束：

- 项目 `AGENTS.md` 未写上述授权时，**只停止该远端 tracking 动作**，记 `sync=not-authorized`，**后续 Workflow Stage 继续**，不得静默执行，也不得停止工作流；
- 只有用户正在请求"完成跨机 handoff"这类本身依赖 checkpoint 的动作时，才可阻断"handoff 完成声明"。

### 8.1 创建 tracking Issue 的常设授权（窄范围）

`feature-development` 与 `bug-fix` 工作流**首次创建本工作流自己的那一张** tracking Issue，属本合同授予的窄范围常设授权；其授权来源与上限见 [runtime-contract.md](runtime-contract.md) §7，无需逐次 ASK。

授权范围**仅限**：

- 创建 1 张 Issue：标题 + §5 的稳定信息正文（含 `Workflow ID` 行）。

**不包含**，继续按上文项目政策或用户当前要求单独授权：

- checkpoint 评论、§6.5 关闭、§10 看板投影——这三类写操作沿用 §8 既有的项目 `AGENTS.md` 授权路径，本节不为它们授权；
- labels、milestone、assignees、创建后的标题或正文二次修改、open/reopen、关闭他人 Issue、对多 Issue 的批量变更；
- commit、push、PR、merge、force-push、发布等 Git 动作。

本节只授权"首次创建"这一个动作：重试创建（须先走 §3.1 对账）、复用既有绑定、评论、关闭与投影各自回到 §8 的既有授权路径。用户明确要求不创建 Issue 时按 §4 记 `not-authorized` + `user-declined`（授权条件变化后可重新评估）；只有用户明确关闭**全部** tracking 投影时才是 `disabled`。

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

看板与 checkpoint 跟随 runtime state，**不跟随 Issue 的 open/closed 状态**：外部直接关闭已绑定 Issue 属于投影脱节，恢复时仍按 §6.1 选取最新 checkpoint 并以仓库证据为准；close 的合法时机见 §6.5。

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

`status=abandoned` 的唯一看板处置：把对应卡片**从看板移出**（archive item），不得进入「完成」列，也不得留在原列。

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
| `dd-project-bootstrap-workflow` | 项目治理与基础环境 | **第一阶段不自动创建、不自动绑定、不自动投影**；runtime schema 容忍 `tracking` 不等于默认覆盖；§2 的强制尝试约束与 §8.1 常设授权均不适用于 project-bootstrap 整个工作流；其第一阶段另明确不自动创建/绑定/投影 |
| `multi-agent-branch-integration` | 多 Agent 分支可见性、同步与集成门禁 | 不管分支集成，只管任务索引与恢复定位 |
| `dd-later-tracking` | LATER 项的文件即 ID 体系 | **不改 LATER**。LATER 提升为开发任务时，Issue 正文引用 LATER 文件路径，不搬运内容 |

## 13. 红线

- 把 Issue 或 checkpoint 当作 Gate、CI、Git 或 artifact 证据；
- 把工作流事实从 Issue 反向回写进 runtime state（定位元数据除外）；
- 用 Issue 承载 Stage / Gate / candidate SHA 的完整状态，制造第二事实源；
- 在 Issue 里写 worktree 绝对路径；
- 因 `tracking` 缺失、绑定失败、写回失败或未授权而阻塞 Workflow Gate；
- 对 `feature-development` / `bug-fix` 工作流，既未尝试创建或绑定 tracking Issue、也未按 §4 记录 `sync` 与 `sync_reason`，就通过 Environment Gate（硬约束是"必须尝试并记录"，不是"绑定必须成功"）；
- 未写 checkpoint 就释放写入租约并宣称已移交；写回失败却宣称 handoff 完成；
- 从 `state_status=active` 的 checkpoint 静默接管；
- 把接管冲突检测描述成"互斥锁"或"弱锁"；
- 在工作流 `active` / `paused` / `handoff-ready` 期间关闭已绑定 Issue，而不写 completed 或 abandoned checkpoint；
- 把外部关闭 Issue 当作工作流完成或完成依据；
- 把 `paused` 当成阻塞；
- 因 Issue 上存在某分支就推定其可见性或同步方式；
- 重列 runtime 已有的 `host` 或 `status` 枚举；
- 把看板投影授权或 §8.1 的 Issue 首次创建常设授权解释成 checkpoint、关闭、labels、commit、push、PR、merge、CI 或发布授权。

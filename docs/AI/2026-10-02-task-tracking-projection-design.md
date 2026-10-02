# Task Tracking 投影改造设计

状态：v3（第二轮针对性复查 NEW-M-01/02、NEW-L-01/02 与 H-02 残留已修订；DP-1/DP-2/DP-4/DP-5/M-05 均已用户裁决；待第三轮复查闭环）。
工作流：`feature-development-20261002T000000Z-task-tracking-projection`
分支：`docs/task-tracking-projection`
修订依据：ChatGPT 首轮外审（会话句柄 `6abeea9c-dc38-83ea-9708-14e4a4174e23`），19 条 FINDING 已逐条本地核对属实后写入本节。

---

## 1. 目标与非目标

### 目标

1. 同一任务在 Codex / Trae / Trae CN / WorkBuddy / OpenCode 之间可接续，不依赖任何单个 App 的聊天记录；
2. 同一任务在 Mac A / Mac B 之间**可发现、可定位**；工作内容是否可跨机取得由合同正文 §9.2 的可达性判定单独声明，不由本设计默认保证；
3. 人能看到：有几个坑、在哪个仓库、哪个分支、做到哪、下一步、是否被阻塞。**（DP-2 已裁决：方案 A——本条降为第二阶段验收条件；第一阶段验收改为"跨设备可发现、可定位、条件式可恢复"——可恢复仅当 `remote=sha-reachable` 且必要修改已持久化，见合同正文 §9.2）**

### 非目标

- 不把 GitHub Issue 变成第二套工作流状态；
- 不复制 runtime state 的 Stage / Gate / CI / candidate SHA 语义；
- 不实现跨机器互斥（§5.9 只做接管冲突检测，明确不是互斥）；
- 不改动 `dd-later-tracking`；
- 不新建顶层 Skill（遵守 `AGENTS.md` §2、§11）；
- 第一阶段不创建 GitHub Project 视图（DP-2 已裁决：方案 A），映射规则先落合同。

---

## 2. 架构定位

三层，投影方向按数据类别区分，不再笼统说"单向"。

### 2.1 工作流事实：单向 runtime → Issue

```text
Git / 已批准文档 / CI
        ↓  验证与重建
runtime state（Stage / Gate / CI / candidate SHA）
        ↓  派生投影
GitHub Issue（卡片 + checkpoint 评论 + 看板列）
```

**工作流事实只允许这个方向。** Issue 里写的 Stage、Current、Next、CI 结论都只是投影，禁止反向回写为 runtime 事实，也禁止作为 Gate、CI、Git 或 artifact 证据。

### 2.2 定位元数据：唯一的窄反向通道

跨机器时，新机器上没有 runtime state，而 `workflow_id` 等身份信息无法从 Git / 文档 / CI 独立重建。因此允许一条**窄反向通道**，且只允许承载定位元数据：

```text
GitHub Issue
        ↓  仅定位元数据
找到 repository / branch / workflow_id / source checkpoint ref
        ↓
在新机器上重新从 Git / 文档 / CI 建立 workflow facts
```

两类数据的边界（写死）：

| 类别 | 内容 | 允许 Issue → runtime？ |
|---|---|---|
| 定位元数据 | `repository`、`issue_number`、`workflow_id`、branch、source checkpoint ref | **允许**，只作定位输入 |
| 工作流事实 | `current_stage`、Gate 结论、`candidate_sha`、CI 结论、产物有效性、完成结论 | **禁止**，只能由仓库证据重建 |

一句话边界：**Issue 可以告诉你去哪找，不可以告诉你已经 PASS 了什么。**

`dd-workflow-runtime` 核心原则第 9 条（Canonical facts have one owner; derived views expire with their sources）已覆盖本设计的定性，不新增原则。

---

## 3. 档位判定

`change_tier: full`（默认档，不是 small）。

理由（写入 `tier_rationale`）：命中 `small-change-track.md` §4 两条升级触发器——

1. **持久化格式变化**：runtime state schema 新增可选字段 `tracking`；
2. **权限 / 外部动作影响**：引入 GitHub Issue 评论与看板状态写入这类远端外部动作，需要一次性授权语义。

### 3.1 审查等级（DP-3 已定，非自由决策）

按现有合同，本改动**不得降为纯主 Agent A/B/C 自检**：

- 本设计已判 `change_tier=full`，`small-change-track.md` §5 的 full 档包含独立强审；
- `review-gate` 把"持久化数据"列为升级触发器，"安全或权限"升到 high；
- 本改动同时修改 runtime 持久化 schema，并引入远端动作授权语义。

执行方式不硬编码为某个具体 skill，按 `model-routing` 选择独立 reviewer / backend。本轮已走 ChatGPT 外审，修复后须送同一会话针对性复查（见 §9）。

### 3.2 full 档在本仓库的等价物（明确写出，不静默降级）

本仓库是文档 + 合同测试仓库，没有应用代码与 UI。因此：

| full 档要求 | 本仓库等价物 |
|---|---|
| 规格套件（Requirements / Design / Test Matrix） | 本文档（目标/非目标 + 合同全文 + 改动清单 + 测试矩阵），其中 §5 为合同，§6 为测试矩阵 |
| Phase 拆分 | 单 Phase：新增 reference → 路由接线 → 合同测试 |
| 冻结 `candidate_sha` + 同 SHA 完整 CI | 冻结本次改动提交 SHA，跑 `dd-workflow-runtime/tests/` 与 `dd-feature-development-workflow/tests/` 全部合同测试 + `git diff --check` |
| 独立强审 | 按 §3.1，走独立强审，不降级 |
| 动作授权 | commit / push 仍需用户当前明确授权，本设计不授权任何 Git 或远端动作 |
| Host Close | 按宿主合同执行 |

---

## 4. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `dd-workflow-runtime/references/task-tracking.md` | 新增 | §5 合同全文 |
| 2 | `dd-workflow-runtime/references/runtime-contract.md` | §3 State Schema，`next_safe_action`（第 121 行）之后 | 只追加 `tracking: null` 一行 + 一句"子对象语义由 task-tracking.md 拥有"（借鉴第 126 行 `routing`/`review`/`external_review` 的语义属主分离原则；tracking 进一步把嵌套字段形状与枚举也统一下沉至 task-tracking.md）。**不在此定义嵌套字段** |
| 3 | 同上 | §5 Recovery（第 181-190 段之后） | 追加一条：tracking 指向的 Issue checkpoint 仅作定位与恢复提示，工作流事实必须重新验证仓库证据 |
| 4 | `dd-workflow-runtime/SKILL.md` | 调用合同代码块（第 28-40 行） | 追加可选入参 `tracking: null` |
| 5 | 同上 | Preflight 第 3 步（第 62 行） | 追加一句：存在 `tracking` 时按 task-tracking 取定位元数据，工作流事实仍以仓库证据为准 |
| 6 | `dd-workflow-runtime/references/state.md` | 写入时机表 | 只追加一行"绑定 `tracking` 后按 task-tracking 写 checkpoint"，**不复制字段定义** |
| 7 | `dd-feature-development-workflow/SKILL.md` | 按需读取清单（第 119-125 行） | 追加一行路由到 `task-tracking.md` |
| 8 | `dd-feature-development-workflow/references/intake-and-environment.md` | §2 Environment「选定后」清单，第 64 行之后 | 追加一条：Environment Gate 前绑定或确认 `tracking`，绑定失败按 §5.4 失败矩阵处置，不阻塞本 Stage |
| 9 | `dd-feature-development-workflow/references/state-and-handoff.md` | — | **不改**。不加 `tracking` 字段（属 runtime），最多加一句指向 |
| 10 | `dd-bug-fix-workflow/SKILL.md` | 状态字段段（第 94 行）之后 | 追加一句：`bug_id` 不重载为 Issue 号，绑定用共享 `tracking` 字段 |
| 11 | `dd-bug-fix-workflow/references/diagnosis-and-verification.md` | §2 Environment 记录块（第 58-63 行）之后 | 追加与第 8 条同一绑定规则：worktree 与分支确定后、Environment Gate 之前。**Bug 必须有与 Feature 对等的绑定 hook** |
| 12 | `dd-bug-fix-workflow/references/state.md` | — | **不改字段** |
| 13 | `dd-project-bootstrap-workflow`（`SKILL.md` 或 `references/execution-contract.md`） | 适当位置 | 追加一句声明：runtime 通用 schema 容忍 `tracking`；**第一阶段 Bootstrap 不自动创建、不自动绑定、不自动投影** |
| 14 | 目标项目 `AGENTS.md`（Macim / CPDF / CNote 等） | 新增段落 | §5.8 授权模板；**不在本仓库** |

测试改动见 §6。

不改：`dd-git-workflow`（worktree 路径与 branch 推导规则不变）、`dd-later-tracking`、`multi-agent-branch-integration`（边界见 §5.11）。

---

## 5. `task-tracking.md` 合同全文

> 以下为待落盘全文，路径 `dd-workflow-runtime/references/task-tracking.md`。

---

# 外部任务绑定与投影

本文件唯一拥有"工作流 ↔ 外部任务系统"的绑定、投影与写回语义，以及 `tracking` 子对象的字段形状与枚举词表。`runtime-contract.md` 只出现 `tracking` 字段名与属主链接，不复制本文件规则。

按需读取：绑定任务、写 checkpoint、跨机器恢复、同步看板时读取。

## 1. 定位

外部任务系统（当前只支持 GitHub Issue）是**跨设备任务索引、人类看板卡片和恢复定位入口**。

它不是：

- 不是工作流状态；
- 不是 Gate、CI、Git 或 artifact 证据；
- 不是跨机器互斥锁（§9 只做接管冲突检测）。

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
- `pending_checkpoint` 用于 crash-safe 防重（见 §5），`last_checkpoint_ref` 只记已确认投递的评论，两者都不是 Gate 证据；
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

**禁止写入 worktree 绝对路径。** Issue 是跨机器的，路径换电脑即失效。worktree 路径由 branch 按 `dd-git-workflow` 的布局推导。

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

- `host` 原样消费 `runtime-contract.md` §2 的 canonical 取值，**本文件不重列词表**；
- `executor` 是**非 canonical 显示标签**（如 `Trae CN` / `WorkBuddy` / `OpenCode`，M-05 已裁决引入）：只用于人读"这是哪个 App 做的"；**不参与 Gate 与恢复判定，不写入 runtime state**；恢复与判定的宿主依据仍是 canonical `host`；
- `state_status` 原样消费 `runtime-contract.md` §3 的 canonical status 取值，**本文件不重列词表**；
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

`dd-feature-development-workflow` 的候选不变量（`candidate_review.sha == full_spec_gap.sha == full_ci_run.head_sha == candidate_sha`）语义仍由其属主拥有，本文件不复制，也不因 Issue 内容放松。

仅 §1.1 的定位元数据可从 Issue 取用。

## 8. 授权

写 Issue 评论、改看板状态是远端外部动作，按 `runtime-contract.md` §7，内容批准不构成外部动作授权。

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
- Issue 只提供 branch locator。分支的私有 / 共享可见性与同步方式仍完全由 `dd-git-workflow/references/branch.md` 重判（`branch.<分支名>.agentShared` 未知即未知），不得因 Issue 上有该分支就推定为 shared。

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

**覆盖完备性要求**：Feature 与 Bug 的 canonical Stage 列表中，每个适用 Stage 必须恰好映射一次；新增 Stage 而映射未更新即视为合同违约（由 §11 测试机械校验）。

阻塞表达（DP-1 已裁决：方案 A）：用 GitHub label `blocked`，因为阻塞与工作阶段正交，占用状态列会丢失被阻塞前所在 Stage；看板配置一个 `label:blocked` 过滤视图补足视觉显著性。`status=paused` **不等于阻塞**。

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

---

（合同全文结束）

---

## 6. 测试矩阵

新增 `dd-workflow-runtime/tests/test_task_tracking.py`，沿用 `test_ci_contracts.py` 的 `unittest` 风格，但**不得停留在"关键词存在即绿"**。实施顺序：先写测试（红），再落文档（绿）。

### 6.1 属主与结构断言

| # | 用例 | 断言方式 |
|---|---|---|
| 1 | `test_task_tracking_linked_from_runtime_skill` | `dd-workflow-runtime/SKILL.md` 直接链接 `references/task-tracking.md` |
| 2 | `test_tracking_nested_schema_single_owner` | 解析 `runtime-contract.md` §3 的 State Schema fenced block：只允许出现 `tracking: null` 与属主链接，**不得**出现嵌套字段；`references/state.md`、两份 workflow `state.md` / `state-and-handoff.md` 同样不得出现嵌套定义 |
| 3 | `test_no_duplicated_runtime_enums` | `task-tracking.md` 不得硬编码 `host` 或 `status` 取值词表；改为断言其引用 `runtime-contract.md` §2 / §3 的属主 |

### 6.2 行为断言（section-scoped，非全文关键词）

| # | 用例 | 断言方式 |
|---|---|---|
| 4 | `test_locator_vs_fact_boundary` | 解析 §1.1 表格：定位元数据集合与工作流事实集合互斥且完整；且事实行的 Issue → runtime 列必须为"禁止" |
| 5 | `test_tracking_never_blocks_gate` | 遍历 §4 失败矩阵每一行："是否允许 workflow 继续"必须为是；且全仓不得出现"tracking 缺失即 BLOCKED" |
| 6 | `test_not_authorized_is_action_scoped` | 合同 §8 授权节必须写明"只停止该远端动作，不停止 Workflow Stage"，且不得出现"未授权即停止工作流" |
| 7 | `test_checkpoint_is_not_evidence` | 合同 §7 必须声明 checkpoint 不是 Gate/CI/Git/artifact 证据；反向断言：不得出现把评论当 PASS 的写法 |
| 8 | `test_writeback_order_is_crash_safe` | 解析 §6.3 顺序块：持久化 pending → 远端写回 → 保存 ref → 释放租约；`pending_checkpoint` 必须排在远端动作之前 |
| 9 | `test_checkpoint_template_fields` | 模板含 `workflow_id` / `checkpoint_id` / `host` / `executor` / `stage` / `state_status` / `remote` / `Branch` / `SHA` / `Next` / `Blocker` / `Taken over from`；且 `executor` 必须标注仅显示、不参与判定、不写入 state |
| 10 | `test_no_absolute_paths_in_issue_fields` | Issue 字段与模板不得出现 `/Users/` 形式的示例路径 |
| 11 | `test_transport_agnostic` | 不得要求特定 MCP；必须显式允许 `gh` CLI 作为等价传输 |

### 6.3 跨机器接管断言

| # | 用例 | 断言方式 |
|---|---|---|
| 12 | `test_takeover_requires_handoff_ready` | 接管规则中 `active` 不得允许静默接管 |
| 13 | `test_takeover_conflict_detected` | 同一来源 `checkpoint_id` 的两个接管声明必须判冲突并 BLOCKED |
| 14 | `test_old_holder_stops_after_takeover` | 旧宿主恢复后必须检查更新接管声明并停止写入 |
| 15 | `test_no_mutual_exclusion_claim` | 合同不得把冲突检测描述为"锁"；反向断言：不得出现"互斥"字样作为能力承诺 |
| 16 | `test_local_only_not_handoff_ready` | `remote=local-only` 不得宣称 handoff-ready |
| 17 | `test_branch_visibility_not_inferred` | 恢复节必须写明分支可见性由 `dd-git-workflow` 重判 |

### 6.4 投影与路由断言

| # | 用例 | 断言方式 |
|---|---|---|
| 18 | `test_stage_projection_covers_all_stages` | 机械提取 Feature / Bug 的 canonical Stage 列表，与合同 §10 映射表做集合比对：每个适用 Stage 恰好映射一次，无遗漏、无未知项 |
| 19 | `test_projection_table_single_owner` | 阶段 → 看板列映射表在本仓库只出现一份 |
| 20 | `test_feature_and_bug_both_have_binding_hook` | **分别**解析 `intake-and-environment.md` 与 `diagnosis-and-verification.md` 的 Environment 节：绑定规则必须位于 worktree/branch 记录之后、Environment Gate 之前。只检查"文件含链接"视为假绿，必须按节区间断言 |
| 21 | `test_bootstrap_opt_out_declared` | `dd-project-bootstrap-workflow` 必须声明第一阶段不自动绑定/投影 |

### 6.5 Feature 侧追加（`test_feature_workflow_contracts.py`）

| # | 用例 | 断言 |
|---|---|---|
| 22 | `TestTrackingMissingDoesNotBlock` | `intake-and-environment.md` 的 Environment Gate 不因 `tracking` 缺失或绑定失败而阻塞 |
| 23 | `TestNoTrackingFieldDuplicationInFeatureState` | Feature state 字段清单不含 `tracking` 嵌套定义（属 runtime + task-tracking） |

### 6.6 mutation 反向测试（防假绿）

对 §1.1 边界表、§4 失败矩阵、§6.3 顺序块各加一条 mutation 用例：把受检文件的关键行做最小学术化篡改（如把事实行的"禁止"改成"允许"、把顺序块两行对调），断言测试**必须转红**。未转红即说明断言是字符串存在检查。

### 6.7 手工检查（AGENTS.md §9）

- 所有 active reference 路径仍有效；
- `git diff --check`；
- 两个 Skill 的既有合同测试全绿，没有通过删除或弱化断言让测试变绿。

---

## 7. 开放决策（需用户逐条裁决）

| ID | 决策点 | 强审建议 | 状态 |
|---|---|---|---|
| DP-2 | "打开一页看到做到哪"是否为第一阶段硬验收条件 | 若不建 GitHub Project，则本条目标必须延后；二者选一 | **已裁决：方案 A**——不建 Project，目标 3 延后，第一阶段验收为"跨设备可发现、可定位、条件式可恢复"（条件见合同正文 §9.2） |
| DP-1 | 阻塞用 label `blocked` 还是占用状态列 | label，理由是与阶段正交 | **已裁决：方案 A**——label `blocked`，不占状态列，配 Blocked 过滤视图 |
| M-05 | 是否引入非 canonical 执行者显示标签（区分 Trae CN / WorkBuddy / OpenCode） | 不扩 runtime `host` 枚举；如需区分，只在 Issue 派生视图加仅用于显示的标签，明确不参与 Gate 与恢复判定 | **已裁决：方案 A**——checkpoint 引入非 canonical `executor` 显示标签，仅显示用，不参与判定、不写入 state |

已由用户逐条裁决（2026-10-02）：DP-4=方案 A（Bootstrap 第一阶段不自动创建/绑定/投影，已写入改动清单第 13 条与合同 §12）、DP-5=方案 A（v1 只做接管碰撞检测、不做弱锁，已并入合同 §9.3，文档明确不得称互斥）。DP-3 保持合同推导结论（见 §3.1）：必须独立强审，不降级。

## 8. 待取证（VERIFICATION_REQUIRED）

- **L-02**：如何可靠选出"最新 checkpoint"（过滤其他 workflow、伪造 marker、重复 checkpoint、分页与排序）。需在真实 GitHub 仓库做一次最小探针后冻结规则，再补进合同 §6.1。当前登记 VERIFICATION_PENDING，取得证据前不实施该段。

## 9. 闭环状态

首轮外审 19 条 FINDING（H-01..H-08、M-01..M-10、L-01）已全部本地核对属实并修订。第二轮针对性复审判 18 条 RESOLVED、H-02 残留（本轮已按条件式可恢复收口）；L-02 是独立的取证项，不属于该 19 条，保持 VERIFICATION_PENDING。第二轮另引入 NEW-M-01 / NEW-M-02 / NEW-L-01 / NEW-L-02，均已修订：DP-4 / DP-5 已经用户逐条裁决（2026-10-02），越权固化已消除；闭环状态与 Git 事实已对齐；章节引用与"既有先例"措辞已修正。

候选身份：第二轮候选 HEAD=`2e1d540b69bfea566912529af99be074749b6b4a`（受审文件 sha256 `eced204d…b22e`）；本轮修订后将 commit 形成第三轮候选，sha256 见下一轮送审记录。第三轮针对性复查（同一会话 `6abeea9c-dc38-83ea-9708-14e4a4174e23`）归一为 `PASS` 后，按 CLOSED 判据四项逐条落地。

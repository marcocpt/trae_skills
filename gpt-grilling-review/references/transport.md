> 迁移来源：`gpt-review-loop/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。
> 依据：[多后端强审 Grilling 闭环需求与草案设计](../../docs/AI/2026-09-02-multi-backend-grilling-requirements-design.md)（v0.15-DRAFT）。backend 的调用命令、能力、只读模式与候选顺序由 `dd-workflow-runtime` 的 registry 与 policy 拥有；本文件只引用，不复制（FR-MB-006）。

# 强审传输合同（后端中立）

## 概述

弱模型完成实现与确定性验证后，向**强审后端**发起审核，逐条处置返回的 finding 形成闭环。后端可替换，但闭环语义（finding 生命周期、三字段、CLOSED 判据、DISPUTED、HARD-GATE、关闭权）对所有后端一致，定义在 [SKILL.md](../SKILL.md)。

本文件只拥有两件事：

1. **多轮编排**：何时再叫同一个 reviewer 一次、句柄如何复用与校验、降级与阻塞；
2. **`chatgpt-tunnel` 后端自管的传输细节**（DEC-MB-04）。

其他后端的调用命令、参数与只读证据一律引用 runtime，不在本文件重述。

**违反规则的字面意思就是违反规则的精神。**

## 后端选择（FR-MB-001）

- `backend` 取值必须是 `dd-workflow-runtime/agents/review-backends.yaml` 中的 canonical backend ID；别名与 canonical ID 的映射只在 runtime 侧有一处定义。
- **存在于 registry 不等于可用于 grilling**。可选后端必须同时满足三项能力条件：
  1. 有状态续接能力（adapter 提供 `resume` 调用形态，FR-MB-015）；
  2. 结构化会话标识输出合同（FR-MB-016）；
  3. 与本次调用形态匹配的有效只读证明（FR-MB-012、FR-MB-004 第 3 条）。
- **缺省** → 使用默认后端 `chatgpt-tunnel`。
- **显式给出但无法识别或不满足上述三项条件** → 判 `configuration_invalid` 并 BLOCKED，**不得静默回退**到默认后端（typo 变成默认后端是 fail-open）。
- **本文件不登记"当前哪些后端可选"的状态快照**。资格状态、续接形态与续接只读取证的属主是 `review-backends.yaml` 及 backend-bound evidence；`stateful` 候选序列的属主是 `routing-policy.yaml` 的 `stateful_roles`。本文件只按上方三项条件做规范性判定——**不满足即不可选**，无需也不得在此处维护第二份状态清单（否则证据或版本一变就立刻产生第二套 active 事实源）。
- `chatgpt-tunnel` 不受 runtime stateful 序列约束：其会话身份与只读规则由本文件自管（DEC-MB-04），始终作为默认后端可选。

候选顺序的 canonical 属主是 `routing-policy.yaml` 的 `stateful_roles`；本文件不自行排序（FR-MB-018）。

## 编排合同（本 skill 自有）

以下规则对所有后端一致生效。

### 续接句柄与身份校验（FR-MB-003、FR-MB-011）

**不变式（所有后端一致）**：针对性复查必须回到**同一强审身份**与**同一 active review session**，且身份连续性必须有**机械可验证依据**。**不得把进程退出码 0、或"复用同一个字符串"当作续接成功的证据。**

句柄的取值类型、获取方式与续接调用形态**按后端分两类**实现，不得互相套用：

1. **runtime-managed backend**（`opencode-cli`、`codex-cli` 等）：调用形态与会话标识由 runtime adapter 合同定义，grilling 只编排轮次、不拼装 provider 命令行（FR-MB-015）；每次续接后从 canonical 结构化 `session` 字段提取实际标识，校验 `actual_session_id == review_session_handle`，无法提取或不相等 → `session_resume_mismatch` → BLOCKED。
2. **`chatgpt-tunnel`**：会话身份由本传输合同自管（DEC-MB-04），映射与连续性规则见本文件下方 `chatgpt-tunnel` 分节。要点是**句柄取回读到的实际 `conversation_id`，不取送审时传入的别名**——两者并不相同。

其余不变式：

- 句柄唯一绑定一个 workflow + backend + reviewer 身份，**不得跨 workflow 复用**；同一 active session 同时只允许一个 in-flight 轮次，并发续接必须机械串行化。
- 派生类调用（如 `--fork` 形态）生成新句柄并保存 parent 关系，**旧句柄不自动转移关闭权**。
- 崩溃后只从 runtime 持久状态恢复，不从 stdout、临时文件或 provider 私有文件重建。
- 句柄缺失或身份校验失败时，针对性复查与 CLOSED 关闭权不可执行，必须 fail-closed。

**可恢复自动化只认可显式传入句柄的 canonical 续接形态**；依赖"最近会话"的隐式续接存在被其他任务改写的歧义，不得作为合同（FR-MB-014）。

### 只读（FR-MB-004）

各 backend 的 `readonly_mode`、参数与 backend-bound 只读证据属主是 `review-backends.yaml` 及其证据文件，本文件不复制该表。grilling 侧只守三条：

1. 任何后端无法机械强制只读时，该后端本次不可用。
2. 绕过沙箱或审批的危险模式一律 fail-closed。
3. **续接属于新的调用形态**：只有现有 backend-bound 只读证据明确覆盖该续接形态时才能沿用，否则必须重新取证。

### 受审候选身份与基线复验（FR-MB-019）

只读强制只保证"reviewer 不改东西"，**不保证"reviewer 看到的东西在两轮之间没被第三方改过"**。本地 CLI 后端读的是**活的**工作树：主 Agent 的修复提交、其他进程或并发任务都可能在第 N 轮与第 N+1 轮之间改变受审内容，使后一轮 verdict 不再对应前一轮的修复结果，CLOSED 判据因此失去所指对象。此约束适用于**所有 grilling 后端**，包括 `chatgpt-tunnel`——审核方经授权通道自读时，本地同样无法保证其读取的远端状态在多轮之间不变。

1. 每个 authoritative review turn 必须绑定一个**受审候选标识**（candidate identity），至少能区分仓库/工作区身份与内容状态。该标识的字段名与持久化方式由 runtime 状态属主定义，本文件**不自行造字段**（FR-MB-006 单向引用纪律）。
2. **捕获与复核时机（MUST，方案 A）**：每轮送审前先 commit 当轮修复（WIP commit 可接受），以该 commit 的 HEAD SHA 作为本轮 candidate identity，工作树必须干净；在 verdict 进入 CLOSED 判据**之前**重新校验 HEAD 仍等于该 SHA 且工作树仍干净。
3. 校验不通过 → 按既有 runtime canonical 状态 `baseline_mismatch` 处理（**不新造状态名**）；本轮 verdict **不得用于 CLOSED 任何 finding**，并 fail-closed（FR-MB-007 第 4 条，不得降级）。
4. **与只读强制正交**：基线标识防"受审内容被第三方改变"，只读强制防"reviewer 自身产生副作用"。**满足只读 ≠ 满足基线一致**，两者不得互相替代或合并取证；两份证据分别持久化、分别失效、分别重新取证，任一份失效只使它自身失效。
5. 多轮语境**复用** runtime 既有冻结基线校验机制（`_verify_frozen_baseline`）：由"每轮先 commit"化解"工作树必须干净"与多轮语义的冲突。**不新增多轮专用机制，不新造第二个状态名**——那正是 FR-MB-020 要防的第二套规则。
6. 在 candidate identity 可机械校验前，多轮 verdict **不得视为可 CLOSED 的证据**（fail-closed）。

### 结果双层分离（FR-MB-013）

1. **传输层**：后端一轮只返回 `dd-review-result/1`（`PASS` / `FINDINGS` / `BLOCKED`），属主是 runtime。
2. **关闭层**：`CLOSED` / `REOPEN` / `VERIFICATION_REQUIRED` / `HUMAN_DECISION_REQUIRED` 由 [SKILL.md](../SKILL.md) 的状态机定义，属主是本 skill。
3. 转换规则：`BLOCKED` **永不得** CLOSED；`FINDINGS` 必须逐条分流处置，不得整体视为 CLOSED；`PASS` 仅作为 targeted review 的 CLOSED 候选，仍须满足 CLOSED 判据四项。
4. **不得把 `dd-review-result/1` 的 `PASS` 与 finding 的 `CLOSED` 等同。**

#### 统一结果路径（MUST）

**只有一个结论入口**：无论哪个后端，reviewer 一轮的输出都先归一为 `dd-review-result/1`，再交给关闭层状态机。**不得存在"某后端直接产出关闭层结论"的第二条路径。**

`chatgpt-tunnel` 的 `STATUS:` 首行是**线上格式，不是关闭层结论**，必须先归一：

| reviewer 返回 | 归一为 | 后续 |
|---|---|---|
| `STATUS: CLOSED` | `PASS` | 仅作为 CLOSED 候选，仍须满足 CLOSED 判据四项 |
| `STATUS: REOPEN` | `FINDINGS` | 原 finding 保持 `OPEN` 并回分流；新问题新建 ID + `introduced_by` |
| `STATUS: VERIFICATION_REQUIRED` | `FINDINGS`，其 finding 的 `classification=VERIFICATION_REQUIRED` | 由关闭层按 [SKILL.md](../SKILL.md) 登记 `VERIFICATION_PENDING` |
| `STATUS: HUMAN_DECISION_REQUIRED` | `FINDINGS`，其 finding 的 `classification=HUMAN_DECISION_REQUIRED` | 由关闭层按 [SKILL.md](../SKILL.md) 走逐条裁决 |

**四种 `STATUS:` 都必须先形成合法的 `dd-review-result/1`**，不存在 `wire STATUS → 关闭层` 的旁路；`VERIFICATION_REQUIRED` / `HUMAN_DECISION_REQUIRED` 是 finding 的 `classification` 取值，不是绕过三态的独立通道。

归一完成前，reviewer 返回的 `STATUS:` **不得**直接写入 finding 的 lifecycle。

### 能力探测与失效触发器（FR-MB-012）

每次 `initial` 前、每次 `resume` 前、以及从中断状态恢复后，都必须检查是否存在与当前 backend / 版本 / 调用形态 / 只读模式 / agent-profile / 续接方式 / 结果格式**完全匹配**的有效能力证据；缺失或指纹不匹配时先重新取证，取证未通过则该调用形态本次不可用。

失效触发器：CLI 或 provider 版本变化、agent / profile 变化、只读配置变化、adapter 调用形态变化、续接参数变化。任一触发后旧证据失效，须重新取证。

### 降级与阻塞（FR-MB-007）

分两个语义阶段，规则不同：

1. **首次审查尚未发生（PRE_INITIAL_REVIEW）**：后端不可用时按 `routing-policy.yaml` 的 stateful 候选顺序降级。**读到空序列必须按 `backend_unavailable` 阻塞，不得自行排序**（FR-MB-018 第 4 条）。
2. **已产生 finding 之后（ACTIVE_GRILLING_SESSION）**：原 reviewer / 会话不可恢复 → `BLOCKED: reviewer_continuity_lost`，**默认不得切换 reviewer**。若未来支持 reviewer 转移，必须作为独立协议，要求完整原 finding、原审核证据、全部修复 diff、当前源码与 baseline，且新 reviewer 完整重新验证，不得称之为"继续原会话"。
3. 任一后端返回 FINDINGS / schema 非法 / 基线漂移 / 只读违例 / 续接违例：**不得降级**（fail-closed）。
4. 后端可用性降级**不增加**返工计数，也**不清零**已有计数（返工上限引用 `routing.max_rework_cycles`）。

### 幂等与恢复（FR-MB-009）

复用 runtime 的供应商中立外部审核防重合同（`runtime-contract.md`），字段、状态名与状态机由 runtime 拥有，本文件不复制。grilling 侧不变式：

1. 提交不确定状态恢复后，必须先用幂等键与后端对账，确认无在途任务才允许重新提交——**重复提交次数为零**。
2. `resume` 重试与 `submit` 重试不得共用重试语义。

## 禁忌（跨后端通用）

各后端自有的禁忌见其分节；以下为所有后端共用的禁忌。

- 绕过 scope 清单让审核方拿到未授权文件；审核方所需的读取范围必须在请求内显式给出
- 敏感文件（密钥/凭据/.env）进入请求
- 用 `opencode-cli` 时套用 Tunnel repo 名或 `work/<相对路径>` 形式
- 未经身份校验就宣称续接成功，并据此进入针对性复查或 CLOSED
- 在续接形态只读证据缺失时复用首轮只读证据

## 后端分节

### `chatgpt-tunnel`（默认后端，本文件自管）

按 DEC-MB-04，该后端的会话身份（`conversation_id`）与 Tunnel 只读规则均属本传输合同，不进 registry 的 stateful 名册。

#### 基线失败（无本技能时的真实错误）

| 真实失败 | 技能对策 |
|---|---|
| 传 timeout_seconds 超过上限 → 参数校验报错 | 固定 600（参数上限 3600） |
| 轮询连接 ECONNRESET → 脚本崩溃放弃（任务其实还在跑） | 每次轮询新建连接 + 重试 |
| 用了已删除的 worktree 名 → 白跑一轮 | 送审前 `git worktree list` 确认 |
| content 指令含糊 → 审核方等待粘贴代码 | 用本技能模板 + 逃逸句 |
| 给 Tunnel 未映射或非 git 的新目录送审 → 回复「无法读取指定文件」，白跑一轮（2026-09-04 实测） | repo 必须是映射表内**且本身是 git 仓库**的目录；不要为送审临时复制文件副本，直接找真实路径 |

#### 三步法

**1. 提交 chatgpt_send**

- `conversation_id`：**首轮**传稳定别名 `"<app 名>-<仓库名>-<分支名>-<月日时分>"`；拿到结果头部回读的**实际** `conversation_id` 后，以该回读值作为 `review_session_handle`，**后续轮次一律使用实际 ID**。别名与实际 ID 不同，不可互相替代（见下方「会话句柄与连续性」）
- `instruction`：传 `""`（不加默认前缀）
- `timeout_seconds`：`600`（单轮审核等待上限；MCP 参数上限 3600，传更大直接报参数错误）
- `content`：按下方模板。只写业务要求 + 仓库名 + 范围；**禁止粘贴代码/diff**

**2. 取结果 chatgpt_get_result（长轮询）**

- 直接调用 `chatgpt_get_result`，不必传 `wait_seconds`：服务端默认挂起最长 55 秒等待，完成立即返回；返回 `[RUNNING]` 则循环再调，审核通常 5-10 分钟
- 无需客户端自定节奏（旧的“隔 20/40 秒再调”已废弃）；仅当所在客户端单次工具调用超时小于 55 秒时显式传更小的 `wait_seconds`（传 0 = 立即返回不等待）
- **禁止重复提交**；`[FAILED]` 检查原因后最多重试 1 次
- 连接异常（ECONNRESET 等）：任务仍在 daemon，**新建客户端连接并继续携带原实际 `conversation_id`** 重试轮询，不要放弃，**不要生成新 ID**
- 满 10 分钟仍未完成：报告用户等待中，不得无限阻塞

**3. 处置意见**

- 逐条：采纳 → 修改并注明依据哪条意见；不采纳 → 说明理由（审核方可能掌握你没看到的事实）
- 重大修改后复用同一实际 `conversation_id` 复审（见下节，非别名）

#### 会话句柄与连续性（DEC-MB-04 自管）

按 DEC-MB-04，本后端的会话身份不进入 runtime stateful 会话合同，映射与连续性规则由本节定义。

- **句柄取回读值，不取传入值**：首轮 `chatgpt_send` 传入的 `conversation_id` 是**别名**（形如 `<app 名>-<仓库名>-<分支名>-<月日时分>`）；`review_session_handle` 取**结果头部回读到的实际 `conversation_id`**。两者不同——2026-09-05 实测：传入别名 `codebuddy-AGENT-skills-refactor-gpt-grilling-transport-09051906`，结果头部回读实际 ID `6a9bf7dd-cc3c-83ee-b017-e8c3abaaa1b9`。
- **续接校验**：后续每轮续发携带该实际 ID；取得结果后校验头部回读 ID 仍等于句柄，不相等 → `session_resume_mismatch` → BLOCKED。
- **重连不改句柄**：连接异常重连时**继续携带原 `conversation_id`**，不得生成新 ID（三步法第 2 步的"新建连接"指新建客户端连接，不是换 ID）。
- **续接连续性实测（2026-09-05）**：首轮传别名 `codebuddy-AGENT-skills-refactor-gpt-grilling-transport-09051906` → 结果头部回读实际 ID `6a9bf7dd-cc3c-83ee-b017-e8c3abaaa1b9`；第二轮以该实际 ID 续发 → 回读仍为 `6a9bf7dd-cc3c-83ee-b017-e8c3abaaa1b9`。满足「initial 回读 X → resume 携带 X → resume 回读 X」的连续性验证。

#### 仓库命名

| 目标 | repo 名 |
|---|---|
| develop 主目录 | `cpdf` |
| CPDF worktree | `cpdf-wt/<分组>/<分支名>`，如 `cpdf-wt/test/S5-Governance-review` |
| 其他项目（~/Working 下全部，含未来新增） | `work/<相对路径>`，如 `work/Keyboard/Macim-worktrees/F-3.3` |
| dd-* 工作流技能库（`~/.workbuddy/skills/dd-*` 均为其软链） | `work/AGENT/skills`（git 仓库，develop 分支） |

worktree 动态变化，送审前先确认仍存在：`git -C /Users/dengdeng/Working/PDF/CPDF worktree list`。

> ⚠️ 「~/Working 下全部」的前提是该目录本身是 git 仓库：2026-09-04 实测，给新建的非 git 目录（临时副本工作区）送审直接得到「无法读取指定文件」。送审前确认目标在映射表内且为 git 仓库；技能文件不要复制副本送审，直接用 `work/AGENT/skills`。

##### Tunnel 解析规则（强制）

ChatGPT 只能通过 **Tunnel 工具按 repo 名解析**到本地真实目录，映射固定：

- `work/<相对路径>` → `~/Working/<相对路径>`
- `cpdf` / `cpdf-wt/<分组>/<分支名>` → CPDF 仓库对应位置

**content 中的 repo 必须是上表的名字形式，严禁使用任何绝对路径（如 `/Users/dengdeng/Working/...`）或项目真实目录名。** 弱模型送审前必须把本地绝对路径按此表换算成 `work/<相对路径>` 形式（例：`/Users/dengdeng/Working/Keyboard/Macim-worktrees/F-3.3` → `work/Keyboard/Macim-worktrees/F-3.3`）。文件清单也必须是 repo 内相对路径，不得写绝对路径。

#### content 模板

**分支整体审（最常用）：**

```
请使用 Tunnel 工具按仓库名读取 "<repo>" 的代码（不要依赖我提供内容，也不要猜绝对路径——"<repo>" 即本地 work 下的相对路径，Tunnel 会解析到真实目录）：
1. 查看 git 状态与当前分支；
2. 查看该分支相对 develop 的全部改动；
3. 审核这些改动的代码质量、正确性与潜在风险。
输出：先确认你读到的分支名，再按 高/中/低 给结构化意见，每条含 问题、位置（文件:行号）、建议。
如果无法读取该仓库，直接回复一行：无法读取该仓库。
```

**复审（同 conversation_id 续发）：**

```
我已按你上一轮意见修改，请通过 Tunnel 工具重新读取仓库 "<repo>" 相对 develop 的最新改动（repo 名=work 下相对路径，不要猜绝对路径），
重点复查上次问题 <编号> 是否修复，并检查是否引入新问题。输出格式同上。
```

**针对性审：**

```
请通过 Tunnel 工具读取仓库 "<repo>"（repo 名=work 下相对路径）的 <目录/文件> 及其测试，专门审核 <关注点>。
输出结构化意见（问题、位置、建议）。
```

#### 禁忌（本后端）

- content 透漏 MCP/浏览器/插件等底层实现细节；repo 必须以 `work/<相对路径>` 形式给出，并明确让 ChatGPT 用 Tunnel 工具按 repo 名读取（不得写绝对路径，也不得写项目真实目录名）
- 粘贴代码/diff 进 content → 审核方自行读取
- 敏感文件（密钥/凭据/.env）进入请求
- `timeout_seconds` 超过 3600（参数上限）
- `[RUNNING]` 期间重复提交
- 省略模板末尾的逃逸句
- 在 content 中写本地绝对路径（如 `/Users/dengdeng/Working/...`）或项目真实目录名代替 `work/<相对路径>` 形式的 repo 名

### `opencode-cli`

**资格**：已于 2026-09-03 取得续接形态的 backend-bound 只读取证，并在 runtime 的 stateful 候选序列内。其调用命令、参数与 `readonly_mode` 的属主是 `review-backends.yaml`，本文件不重述。

**续接**：走 adapter 的 `resume` 调用形态，显式传入 `review_session_handle`（FR-MB-015）。每次续接后按「续接句柄与身份校验」从结构化 `session` 字段提取实际会话标识并比对；不得依赖"最近会话"隐式续接，不得以退出码 0 判定续接成功。

**读取方式（FR-MB-005）**：**不使用 Tunnel，不要求 `work/<相对路径>` repo 名**。给定工作区 cwd 与相对 `scope` 列表，审核方直接 Read / Grep / Glob。因此：

- content 里写**仓库内相对路径清单**与关注点，不写 Tunnel repo 名，也不写绝对路径；
- 本后端不适用上面「仓库命名」与「Tunnel 解析规则」两节，那两节只属于 `chatgpt-tunnel`。

**只读**：属 agent 权限合同（默认拒绝 + 只读工具白名单），机制与证据属主是 registry 的 `readonly_mode` 及 backend-bound 证据文件。

**取证边界**：本后端续接形态的只读证据属主是 `dd-workflow-runtime/tests/evidence/opencode-resume-readonly-evidence.yaml`（4 份原始事件流），其中记录了该次取证的确切 backend / agent / CLI 版本 / 调用形态与事件级结论。该证据**版本与形态绑定**——CLI 版本、agent、调用形态任一变化即失效，须重新取证（FR-MB-012）。**本文件不复制其事件级结论**。

**结果**：一轮只返回 `dd-review-result/1`；finding 的 `severity` / `classification` / `change_risk` 三字段已由 runtime 机械校验对齐 canonical 枚举（FR-MB-017），F/V/H 分流仍按 [SKILL.md](../SKILL.md) 的语义执行，不得由 provider 定义另一套枚举含义。

## 红线 - 出现即停下纠正

| 借口 | 现实 |
|---|---|
| "改动很小跳过审核" | 小改动也会错；审核是强制步骤 |
| "轮询太慢再提交一次" | 重复提交浪费 5-10 分钟并污染会话 |
| "直接把 diff 粘过去更快" | 粘贴 = 失去审核方主动探索上下文的能力 |
| "连接断了任务肯定没了" | 任务在 daemon，重连继续轮询 |
| "审核意见只是建议" | 必须逐条处置（采纳或说明理由），不得忽略 |
| "后端退出了换个后端接着审就行" | 已产生 finding 后换后端 = 换 reviewer，判 `reviewer_continuity_lost` 并 BLOCKED，不得称之为继续原会话 |
| "首轮证明只读了，续接沿用就行" | 续接是新调用形态，须有覆盖该形态的 backend-bound 证据，否则重新取证 |
| "退出码 0 说明续接成功了" | 必须做结构化会话标识比对，不等即 `session_resume_mismatch` |
| "这个后端在 registry 里，所以能用于多轮" | registry 只登记能力，多轮还须满足续接、会话标识、续接只读取证三项条件 |

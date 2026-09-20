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

1. **传输层**：问题闭环审查的权威审查轮次（authoritative review turn）只返回 `dd-review-result/1`（`PASS` / `FINDINGS` / `BLOCKED`），属主是 runtime。
2. **关闭层**：`CLOSED` / `REOPEN` / `VERIFICATION_REQUIRED` / `HUMAN_DECISION_REQUIRED` 由 [SKILL.md](../SKILL.md) 的状态机定义，属主是本 skill。
3. 转换规则：`BLOCKED` **永不得** CLOSED；`FINDINGS` 必须逐条分流处置，不得整体视为 CLOSED；`PASS` 仅作为 targeted review 的 CLOSED 候选，仍须满足 CLOSED 判据四项。
4. **不得把 `dd-review-result/1` 的 `PASS` 与 finding 的 `CLOSED` 等同。**

#### 统一结果路径（MUST）

**只有一个结论入口**：无论哪个后端，**问题闭环审查的权威审查轮次**（authoritative review turn）的输出都先归一为 `dd-review-result/1`，再交给关闭层状态机。**不得存在"某后端直接产出关闭层结论"的第二条路径。**

**边界（决策建议审查）**：决策建议审查轮次（advisory turn）是**非关闭型的信息建议轮次**——不进入 `dd-review-result/1`，不进入关闭层，不产生 `PASS` / `CLOSED` 或任何关闭权。`chatgpt-tunnel` 的 advisory 输出由 [advisory-review.md](advisory-review.md) 的决策点模型处理（自由文本）；声明了 `advisory` capability 与 `advisory_result_schema: dd-advisory-result/1` 的 CLI 后端则经 dispatch 的 advisory 路径产出 `dd-advisory-result/1`（`status ∈ {ADVISORY, BLOCKED}`），同样非关闭型。advisory 结果中的 `base_sha` / `head_sha` / `scope` 仅用于冻结建议上下文与结果可重复性，属于 **context identity**：它不取得 FR-MB-019 的 finding CLOSED candidate identity 语义，advisory 也不存在进入 CLOSED 前的二次候选复验。除此之外的后端轮次仍受本节全部约束。

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

#### 本机插件名解析（MUST，每次送审前执行）

不同机器登录的 ChatGPT 账号可能装不同的仓库读取插件（如 `Tunnel`、`CodeReview_YL`）。**送审 content 与开场模板里"怎么称呼该工具"，必须先用下文规则解析成本机实际插件名，并全程只写该名字**；写错或写通用词都会导致审核方拿不到仓库。

**机器相关传输参数是机器本地事实，不入共享仓库**，统一由机器本地配置文件承载（唯一机器事实源，schema_version 1）：

```
位置（按顺序取第一个存在的）：$GPT_GRILLING_CONFIG
                                   ${XDG_CONFIG_HOME:-~/.config}/gpt-grilling-review/local.yaml

字段：
  chatgpt_tunnel.repo_reader_plugin  本机 ChatGPT 账号的仓库读取插件名（MUST）
  repo_roots.work                    work/<相对路径> 换算的仓库根（可选，缺省 ~/Working）

环境变量 GPT_GRILLING_REPO_READER_PLUGIN 仅作显式临时 override，不是 canonical source。
```

解析步骤：

1. 按上述位置读取机器本地配置；文件缺失、YAML 非法或 `repo_reader_plugin` 缺失/为空 → **fail-closed**：向用户询问本机插件名（弱模型不得自行猜测，也不得按 `Tunnel` 默认白跑），确认后写入配置文件；
2. 解析出的插件名替换下方所有模板中的 `<插件名>` 占位符；不得把占位符原样留在 content 里；
3. 插件名是稳定标识，不随会话改写或中文化；**本文件不复制任何机器名单**，名单只存在于各机器自己的配置文件中。

#### 基线失败（无本技能时的真实错误）

| 真实失败 | 技能对策 |
|---|---|
| 传 timeout_seconds 超过上限 → 参数校验报错 | 固定 600（参数上限 3600） |
| 轮询连接 ECONNRESET → 脚本崩溃放弃（任务其实还在跑） | 每次轮询新建连接 + 重试 |
| 用了已删除的 worktree 名 → 白跑一轮 | 送审前 `git worktree list` 确认 |
| content 指令含糊 → 审核方等待粘贴代码 | 用本技能模板 + 逃逸句 |
| 给插件未映射或非 git 的新目录送审 → 回复「无法读取指定文件」，白跑一轮（2026-09-04 实测） | repo 必须是映射表内**且本身是 git 仓库**的目录；不要为送审临时复制文件副本，直接找真实路径 |

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
| 其他项目（仓库根下全部，含未来新增） | `work/<相对路径>`，如 `work/Keyboard/Macim-worktrees/F-3.3` |
| dd-* 工作流技能库（`~/.workbuddy/skills/dd-*` 均为其软链） | `work/AGENT/skills`（git 仓库，develop 分支） |

worktree 动态变化，送审前先确认仍存在（以机器本地配置 `repo_roots` 定位仓库）：`git -C <仓库根>/PDF/CPDF worktree list`。

> ⚠️ 「仓库根下全部」的前提是该目录本身是 git 仓库：2026-09-04 实测，给新建的非 git 目录（临时副本工作区）送审直接得到「无法读取指定文件」。送审前确认目标在映射表内且为 git 仓库；技能文件不要复制副本送审，直接用 `work/AGENT/skills`。

##### repo 名解析规则（强制）

ChatGPT 只能通过**本机解析的读取插件**（`<插件名>`，见上方「本机插件名解析」）按 repo 名解析到本地真实目录，映射固定：

- `work/<相对路径>` → `<repo_roots.work>/<相对路径>`（仓库根由上方「本机插件名解析」的机器本地配置 `repo_roots.work` 决定，缺省 `~/Working`）
- `cpdf` / `cpdf-wt/<分组>/<分支名>` → CPDF 仓库对应位置

**content 中的 repo 必须是上表的名字形式，严禁使用任何绝对路径或项目真实目录名。** 弱模型送审前必须把本地绝对路径按此表换算成 `work/<相对路径>` 形式（例：`~/Working/Keyboard/Macim-worktrees/F-3.3` → `work/Keyboard/Macim-worktrees/F-3.3`；本机根不是 `~/Working` 时按 `repo_roots.work` 换算）。文件清单也必须是 repo 内相对路径，不得写绝对路径。

##### 插件名路由锁定（提示词措辞，强制）

多轮强审里最高频的翻车是"审核方不调用 `<插件名>`——找不到工具、回退去猜绝对路径、或基于对话里我贴的上下文直接推断结论"。根因**不是仓库路径描述不清，而是工具发现与调用路径没有被锁死**。以下三规则用于任何需要 ChatGPT 读取本地仓库的请求（仓库整体审 / 复审 / 针对性审 / 决策建议审通用）。

1. **用"调用 `<插件名>` 工具"，不要只写"`<插件名>` 插件"**。`<插件名>` 由上文「本机插件名解析」解析得出（如本机为 `CodeReview_YL` 即以 `CodeReview_YL` 替换）——**送审前未先解析即写死任意名字都会翻车**。"插件"不是稳定触发词；模型对工具名的联想可能是 `<插件名>`、`<插件名>.git_status`、`<插件名>.collect_review_evidence` 等变体。因此不要把某个具体子工具名当作**唯一**触发词；需要显式给出"第一步做什么"保证先调用工具时，可以在开场模板里写明具体调用（如下方固定模板中的 `<插件名>.git_status(...)`），但不要假设模型只认识某一个名字。
2. **先要求"按 repo 名解析"，同时明确禁止绝对路径与真实目录名**。模型失败后容易退化成去猜 `/Users/xxx/...` 或用 `work/...` 之外的绝对路径；必须显式禁止。
3. **要求"先调用工具，再回答结论"**。比单纯"请读取……"更可能真正触发工具调用；防止基于上下文推断就给出结论。

多轮强审会话建议固定以下开场，把路由锁死：

```
【<插件名> 审查模式】
本任务必须先调用 <插件名> 工具。
目标仓库：
repo: <repo（work 下相对路径，见上方仓库命名表）>
禁止：
- 不允许基于上下文推断仓库内容；
- 不允许引用我提供的摘录代替读取；
- 不允许猜绝对路径。
第一步只做：
<插件名>.git_status(repo="<repo>")
成功后继续读取文件并审查。
```

若当前会话没有可调用的 <插件名> 能力，或无法解析 repo，只回复一行：无法读取该仓库。

`<插件名>` 照着上方占位符原样替换为本机解析结果（如 `CodeReview_YL`），**不得把 `<插件名>` 字样留在发给审核方的 content 中**。

#### content 模板

**分支整体审（最常用）：**

```
请使用 <插件名> 工具按仓库名读取 "<repo>" 的代码（不要依赖我提供内容，也不要猜绝对路径——"<repo>" 即本地 work 下的相对路径，<插件名> 会解析到真实目录）：
1. 查看 git 状态与当前分支；
2. 查看该分支相对 develop 的全部改动；
3. 审核这些改动的代码质量、正确性与潜在风险。
输出：先确认你读到的分支名，再按 高/中/低 给结构化意见，每条含 问题、位置（文件:行号）、建议。
如果无法读取该仓库，直接回复一行：无法读取该仓库。
```

**复审（同 conversation_id 续发）：**

```
我已按你上一轮意见修改，请通过 <插件名> 工具重新读取仓库 "<repo>" 相对 develop 的最新改动（repo 名=work 下相对路径，不要猜绝对路径），
重点复查上次问题 <编号> 是否修复，并检查是否引入新问题。输出格式同上。
```

**针对性审：**

```
请通过 <插件名> 工具读取仓库 "<repo>"（repo 名=work 下相对路径）的 <目录/文件> 及其测试，专门审核 <关注点>。
输出结构化意见（问题、位置、建议）。
```

**决策建议审（开放决策点求建议）：**

```
请通过 <插件名> 工具按仓库名读取 "<repo>"（repo 名=work 下相对路径）的相关代码与文档，针对下列开放决策点逐条给出建议。
每个决策点输出：推荐选项、理由、主要反对意见/风险、信息是否充足（缺什么材料）。只给建议与理由，不修改任何文件；如顺带发现疑似代码/文档缺陷，作为"待问题闭环审查的候选问题"单独附在末尾，不要输出为本轮 finding 或关闭结论。
决策点清单：<DP-1、DP-2…每条含问题、背景约束、已知选项>
权威依据：<可选>
冻结 baseline：<HEAD 或明确的参考基线>
最后声明实际已读范围 reviewed 与无法读取范围 unreadable；未完整读取不得宣称建议审查完成。
```

#### 针对性复查模板（本后端线上格式）

`SKILL.md` 只规定后端中立的请求字段；本节的 `STATUS:` 文本格式是**本后端专属的线上格式**，不进 SKILL.md。

字段含义要点：`实际 diff` 与 `当前相关源码` 由强审者按 repo 名**自读**，本地不粘贴代码内容（见下方禁忌）；`baseline` 与 `验证结果` 由本地给出。

```
请复查以下修复。重点不是重新做完整代码审查，而是验证：
1. 原 finding 是否被真正解决；
2. 修复是否改变了未授权的行为（对照授权范围/裁决记录）；
3. 是否引入新的逻辑、并发、兼容性或测试问题；
4. 当前证据是否足以关闭 finding。

finding ID: <ID>
原 finding: <SEVERITY/问题描述/位置>
授权范围: <用户批准的修复事项>
人工裁决: <如有，用户最终选择的方案>
允许修改文件: <范围>
不得改变: <兼容性/API/行为约束>
修改前 baseline: <HEAD/已知失败>
实际 diff: <真实 diff，或指明强审者应自读的 commit 区间>
当前相关源码: <修改后相关代码，或指明强审者应自读的路径>
验证结果: <测试命令/退出码/日志>

第一行必须且只能是以下状态之一：
STATUS: CLOSED
STATUS: REOPEN
STATUS: VERIFICATION_REQUIRED
STATUS: HUMAN_DECISION_REQUIRED

第二行起：若不是 CLOSED，说明最小原因和下一步。REOPEN 须指明是原问题未解决还是引入新问题（新问题须建新 finding ID + introduced_by）。
```

返回的 `STATUS:` 先按上文「统一结果路径」归一为 `dd-review-result/1`，再交给关闭层；归一前**不得**直接写入 finding 的 lifecycle。

#### 禁忌（本后端）

- content 透漏**本地 agent 侧**的 MCP/浏览器/插件等实现细节（违规的是暴露我方底层机制）；但**审核方侧必须暴露**的读取插件名不在此列——按「本机插件名解析」写出 `<插件名>` 是必须项。repo 必须以 `work/<相对路径>` 形式给出，并明确让 ChatGPT 用本机解析的 `<插件名>` 工具按 repo 名读取（不得写绝对路径，也不得写项目真实目录名）
- 粘贴代码/diff 进 content → 审核方自行读取
- 敏感文件（密钥/凭据/.env）进入请求
- `timeout_seconds` 超过 3600（参数上限）
- `[RUNNING]` 期间重复提交
- 省略模板末尾的逃逸句
- 在 content 中写本地绝对路径（如 `/Users/dengdeng/Working/...`）或项目真实目录名代替 `work/<相对路径>` 形式的 repo 名
- 措辞未锁死插件名路由：未按「本机插件名解析」替换 `<插件名>`（如仍写"Tunnel 插件"或写非本机插件名）、未要求"先调用工具再回答"、或未禁止基于上下文推断/猜绝对路径——三者任一缺失都可能让审核方拿不到仓库

### `opencode-cli`

**资格**：由 `review-backends.yaml` 的续接形态、会话标识与 backend-bound 只读取证，以及 `routing-policy.yaml` 的 stateful 候选序列共同决定；**本节不记录当前资格状态**。其调用命令、参数与 `readonly_mode` 的属主是 `review-backends.yaml`，本文件不重述。

**指定模型**：先按 [model-routing.md 的 OpenCode 模型改选](../../dd-workflow-runtime/references/model-routing.md#opencode-模型改选) 核对模型 ID、绑定与授权；不得把默认模型当成不可更换的架构约束，也不得把本次模型选择当作修改共享配置的授权。版本或配置漂移须按本文件「能力探测与失效触发器」重新取证，不能只报告“证据过期”便建议换后端；说明所需取证及授权缺口，已获授权则执行取证，未通过仍 BLOCKED。已有 finding 时优先检查原 reviewer 连续性，换模型不继承关闭权。

**单次覆盖用法**：派发请求的顶层 `model` 即本次 reviewer 模型（完整 ID），只影响本轮；canonical 与默认不动。pin 必须配同模型 proof（`model` 一致），proof 的 `source` 指向该模型的 L6 证据文件。

**无证新模型自动重测（须用户预授权）**：在隔离临时仓库执行，不得接触真实代码：建仓并写保护文件记 sha；以 pin 模型 + reviewer profile 跑一次小范围只读审查并尝试写入/创建；父侧验证 sha 不变、无新增文件、工作树干净、审查方拒绝写入；通过后落盘 `tests/evidence/opencode-cli-l6-evidence.<slug>.yaml`（slug 为模型 ID 的 `/` 换 `-`，含 model、opencode 版本、profile、调用形态与验证结论），proof 引用它。需多轮复审时续接形态同样取证，否则复审 BLOCKED。

**续接**：走 adapter 的 `resume` 调用形态，显式传入 `review_session_handle`（FR-MB-015）。每次续接后按「续接句柄与身份校验」从结构化 `session` 字段提取实际会话标识并比对；不得依赖"最近会话"隐式续接，不得以退出码 0 判定续接成功。

**读取方式（FR-MB-005）**：**不使用仓库读取插件，不要求 `work/<相对路径>` repo 名**。给定工作区 cwd 与相对 `scope` 列表，审核方直接 Read / Grep / Glob。因此：

- content 里写**仓库内相对路径清单**与关注点，不写 `work/<相对路径>` repo 名，也不写绝对路径；
- 本后端不适用上面「仓库命名」与「repo 名解析规则」两节，那两节只属于 `chatgpt-tunnel`。

**只读**：属 agent 权限合同（默认拒绝 + 只读工具白名单），机制与证据属主是 registry 的 `readonly_mode` 及 backend-bound 证据文件。

**取证边界**：本后端续接形态的只读证据属主是 `dd-workflow-runtime/tests/evidence/opencode-resume-readonly-evidence.yaml`（4 份原始事件流），其中记录了该次取证的确切 backend / agent / CLI 版本 / 调用形态与事件级结论。该证据**版本与形态绑定**——CLI 版本、agent、调用形态任一变化即失效，须重新取证（FR-MB-012）。**本文件不复制其事件级结论**。

**结果**：按请求 mode 返回——finding 轮返回 `dd-review-result/1`，advisory 轮返回 `dd-advisory-result/1`（均由 runtime schema/validator 属主机械保证，FR-MB-017），本文件只引用，F/V/H 分流仍按 [SKILL.md](../SKILL.md) 的语义执行，advisory 的决策点模型按 [advisory-review.md](advisory-review.md) 执行，不得由 provider 定义另一套枚举含义。

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

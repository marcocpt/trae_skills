# 多后端强审 Grilling 闭环：需求与草案设计

> 起草：2026-09-02 | 版本：v0.14-DRAFT（六轮 ChatGPT 复核 + 九次 targeted 复核；MB-GRILL-001~033 **全部 CLOSED**，见 §11.1~§11.14；剩余：codex-cli 续接形态只读取证 VERIFICATION_REQUIRED、chatgpt-tunnel 跨 owner 会话合同待裁决）
> 适用范围：让 `gpt-grilling-review` 的强审闭环支持多个复审后端可选，而不复制 finding 生命周期与关闭权规则。
> 修订说明：
> - v0.1 复核返回 14 个 finding（8 HIGH / 5 MEDIUM / 1 LOW）；3 条架构项经用户裁决落地（DEC-MB-01~03），11 条 FINDING 在 v0.2 处置，并回填真机实测。
> - v0.2 复审返回 `STATUS: REOPEN`——5 条原 finding 未真正解决（001 / 004 / 008 / 011 / 012），另新增 4 个 finding（015、016 HIGH；017、018 MEDIUM）。v0.3 处置全部 9 项。
> - v0.3 复审：上述 9 项全部 CLOSED，但暴露 2 个跨属主接口缺口（新增 MB-GRILL-019 HIGH、020 MEDIUM）与 2 处文案歧义。本版 v0.4 新增 FR-MB-017 / FR-MB-018，补齐 §7.2 的 runtime 改动项，并修正两处措辞。
> - v0.4 之后补登 v0.1 阶段的本地审核意见（MB-REVIEW-001~013）：该命名空间**此前从未进入任何复核台账**，v0.2~v0.4 只处置了 MB-GRILL 命名空间，属静默遗漏。逐条核对后：10 条已在 v0.2~v0.4 落地，3 条（005 / 011 / 012）未处置。本版 v0.5 新增 FR-MB-019 / FR-MB-020、改写 NFR-MB-001、§10 补 2 条红线，并在 §11.5 登记核对结论与新增阻塞项。
> - 版本状态：v0.9-DRAFT。v0.6 第六轮 PASS（§11.8）；v0.7 方案 A 落地 CLOSED（§11.9）；v0.8 落地 021/020（§11.10）经**第七轮 targeted 复核返回 `REOPEN`**：MB-GRILL-021 CLOSED、MB-GRILL-020 修复不完整（chatgpt-tunnel 不满足 FR-MB-001 三项资格即入序列，validator 无资格校验）、**新增 MB-GRILL-028**（router_selectable: false 对 external 无通用禁令，introduced_by=021）。v0.9 处置经**第八轮确认（§11.12）**：**MB-GRILL-028 CLOSED、MB-GRILL-021 维持 CLOSED、MB-GRILL-020 维持 REOPEN（空序列过渡态合规，无额外缺口）**，零新 finding。MB-GRILL-019 与文档已 commit（`ec8844f` / `f6a8f11`）并推送；028 修复与 020 过渡态经主审确认后 commit。**批准仍阻塞于**：MB-GRILL-020 完全闭合（FR-MB-015/016 runtime 会话标识合同 + adapter initial/resume 形态 + 续接形态只读取证）与 §8 两处 VERIFICATION_REQUIRED 取证。
> - v0.5 第五轮复审返回 `STATUS: REOPEN`：1 HIGH（022，§0 表述与 worktree 状态矛盾）+ 4 MEDIUM。v0.6 处置全部 5 项；**本地核对另发现 2 项主审未识别的问题**（027 HIGH / 024 补充）：runtime 已存在 `_verify_frozen_baseline` 与 `baseline_mismatch`（`dispatch-review.py:567`），FR-MB-019 的"现状无此机制"陈述有误、新造的 `baseline_drift` 与既有状态名冲突、且既有机制要求工作树干净与 grilling 多轮语义冲突；FR-MB-020 的阻塞状态清单漏列 12 个 runtime 既有 `failure_category`。详见 §11.7。

---

## 0. 已裁决的架构决定

| 编号 | 决定 | 影响 |
|---|---|---|
| DEC-MB-01 | **续接能力由 canonical adapter 提供**：扩展 `codex-review` / `opencode-review`（及 ChatGPT 通道）使其具备 `initial` 与 `resume` 两种调用形态；grilling 只编排轮次，不自行拼装 provider 命令行 | FR-MB-015、§7.1 |
| DEC-MB-02 | **两个 ChatGPT 通道拆名各归其位**：grilling 使用 `chatgpt-tunnel`（审核方经 Tunnel 自读 + 多轮续接），Router 单跳使用 `mcp-review`（快照发送、无读取能力）。行为不变，只对齐名字与事实 | FR-MB-001、FR-MB-004、FR-MB-005 |
| DEC-MB-03 | **结果合同双层分离**：后端一轮只返回 `dd-review-result/1`；grilling 在其上定义从属的 closure 合同，并写死转换规则；关闭权仍归 grilling | FR-MB-013 |

---

## 1. Background（背景）

`gpt-grilling-review` 当前把"强审闭环协议"与"ChatGPT 传输"写在同一 skill 内：

- 协议层（backend 中立，可复用）：finding 生命周期、SEVERITY / CLASSIFICATION / CHANGE_RISK 三字段、CLOSED 判据、DISPUTED 反证、HARD-GATE 逐条裁决、关闭权。
- 传输层（当前硬绑定 ChatGPT）：`references/transport.md` 的 `chatgpt_send` / `chatgpt_get_result`、`conversation_id` 复用、Tunnel `work/<相对路径>` 命名。

用户希望在保持同一套 grilling 协议的前提下，把复审后端换成 OpenCode 或 Codex 等其他 agent app，并要求"多后端可选"。

现有 `dd-workflow-runtime` 的 Generic Review Backend Router v1（`2026-08-25-review-backend-router-v1-design.md`）只做**单跳、无状态、一次性**派发（`max_hops=1`、`dispatch_boundary=single-backend`），明确**不关闭 finding、不持有会话**。本方案不要求 Router 承担多轮闭环，但仍受其 backend 调用、只读与结果合同的约束。

## 2. Problem Statement（问题定义）

1. `gpt-grilling-review` 的传输层写死 ChatGPT，换后端需改协议层或另起炉灶，易产生第二套 finding 规则。
2. grilling 闭环依赖"多轮续接句柄"，而各后端的续接机制不同（`conversation_id` / `--session` / `exec resume`），现有 transport 没有抽象。
3. 现有 canonical adapter（`codex-review`、`opencode-review`）只有一次性调用形态，**不含续接参数**（本地 grep 零命中），无法直接承载多轮闭环。
4. ChatGPT 通道是"审核方经 Tunnel 自读、本地不发送代码内容"；换成可触工作树的本地 CLI 后，只读约束必须由权限/沙箱机械强制。
5. 审核结果的合同未分层：`dd-review-result/1`（PASS / FINDINGS / BLOCKED）与 grilling 的关闭决策（CLOSED / REOPEN / …）是两件事，混同会把关闭权交给 adapter。
6. "有哪些可选后端、各怎么调、失败怎么分类"若同时在 grilling skill 与 runtime registry 各写一份，会漂移成两个事实源。

## 3. Goals（目标）

1. 保持 `gpt-grilling-review` 作为"外部 finding 生命周期与多轮编排"的唯一属主（`AGENTS.md` §8），多后端只是传输层变体。
2. 同一套 grilling 协议对用户可见的所有后端一致生效。
3. 复审后端可配置、可选，默认仍走 ChatGPT 通道以兼容现状。
4. 任何后端必须提供可**校验**的续接句柄——拿到句柄还不够，必须证明恢复的确实是那个会话。
5. 任何后端必须机械强制只读边界；无法强制时该后端不可用（fail-closed）。
6. backend 调用、只读模式、退出码分类、结果 schema **单向引用** runtime registry；候选顺序与降级分类**单向引用** `routing-policy.yaml`；不在本 skill 复制。

## 4. Scope（范围）

包含：

- `gpt-grilling-review/SKILL.md` 增加"后端选择"输入项与后端中立化约束；
- `transport.md` 重构为后端中立传输合同（编排合同 + 各后端分节）；
- 续接句柄抽象与身份校验；
- 只读强制矩阵（按 canonical backend ID）；
- 代码读取方式分支；
- 结果合同分层与转换规则；
- 降级、阻塞与 reviewer 连续性规则。

不包含（本次）：

- 不在 Router 内实现多轮闭环，不改 `max_hops=1`；
- 不在本 skill 定义 backend 调用命令、退出码分类、候选顺序或只读证据本身（引用 runtime）；
- 不为每个后端造独立 finding 语义；
- 不下沉或删除 ChatGPT 默认路径。

## 5. Functional Requirements（功能需求）

### FR-MB-001：后端选择参数与 ID 纪律

1. `gpt-grilling-review` 接受 `backend` 输入项，取值必须是 `review-backends.yaml` 中的 canonical backend ID，**且该 backend 必须同时满足 grilling 的三项能力条件**：
   - 具备有状态续接能力（adapter 提供 `resume` 调用形态，见 FR-MB-015）；
   - 具备结构化会话标识输出合同（见 FR-MB-016）；
   - 具备与本次调用形态匹配的有效只读证明（见 FR-MB-012）。
   **存在于 registry 不等于可用于 grilling**：只支持单跳的 `mcp-review`、未定义续接合同或缺失只读证据的 backend 一律不可选。
2. **缺省**（未指定）→ 使用默认后端 `chatgpt-tunnel`（向后兼容）。
3. **显式给出但无法识别或不满足上述能力条件** → 判为 `configuration_invalid` 并 BLOCKED，**不得静默回退**到默认后端（typo 变成默认后端是 fail-open）。
4. 用户可输入的别名与 canonical ID 的映射只有一处定义（runtime registry 侧）；本 skill 不定义第二套别名表。

对应 finding：MB-GRILL-003、MB-GRILL-015。

### FR-MB-002：协议层后端中立

SKILL.md 的 finding 生命周期、三字段、CLOSED 判据、DISPUTED、HARD-GATE、关闭权规则**不得**包含任何后端专有术语；后端差异只出现在传输层。

### FR-MB-003：续接句柄抽象与身份校验

1. 每个可用于 grilling 的后端必须产出并复用 `review_session_handle`。**句柄取值类型、获取方式与续接调用形态由 runtime 拥有的 adapter 合同定义（FR-MB-015），本文不复制任何 provider 命令。** grilling 侧只依赖以下不变式：
   - `initial` 调用必须返回可持久化的会话标识；
   - `resume` 调用必须接受该标识并回到同一会话上下文；
   - 同一 workflow 内、同一后端同时只存在一个 active 句柄（FR-MB-011）。
2. **身份校验（MUST）**：每次续接后必须从后端**结构化**输出提取实际会话标识，并校验 `actual_session_id == 请求的 review_session_handle`。无法提取或不相等 → `session_resume_mismatch` → BLOCKED。
3. **不得把进程退出码 0 当作续接成功的证据。**
4. 缺省句柄或身份校验失败时，针对性复查与 CLOSED 关闭权不可执行，必须 fail-closed。

对应 finding：MB-GRILL-006。

### FR-MB-004：只读强制（按 canonical backend ID 分别写）

| 后端 | 只读机制类别 | 事实与证据属主 |
|---|---|---|
| `chatgpt-tunnel` | 审核方经授权通道自读；本地**不发送绝对仓库路径或文件内容**，仅发送 Tunnel repo 名与相对清单 | `review-backends.yaml` 的 `readonly_mode` 及 backend-bound 只读证据 |
| `mcp-review` | 快照发送（Router 单跳形态，grilling 不用于多轮） | 同上 |
| `opencode-cli` | agent 权限合同：默认拒绝 + 只读工具白名单 | 同上 |
| `codex-cli` | CLI 沙箱参数（首轮调用形态） | 同上 |
| `codex-native` | 派生前须经 Codex 原生守卫（`native_guard` 字段所指脚本） | 同上 |
| `opencode-native` | 按 registry 中该 backend 自身声明的只读模式与守卫 | 同上 |

各 backend 的 `readonly_mode`、具体参数与只读证据仍在 registry 及其 backend-bound 证据文件中，**本文不复制命令与参数**。

1. Codex 原生派生守卫只适用于 `codex-native`（registry 中该 backend 声明了 `native_guard`），**不得**套用到 `opencode-native`，也**不得**写成 `codex-cli` 的通用要求。
2. 绕过沙箱或审批的危险模式一律 fail-closed。
3. **续接属于新的调用形态**：只有现有 backend-bound 只读证据明确覆盖该续接形态时才能沿用旧证据，否则必须重新取证（FR-MB-012、第 8 节）。
4. 任何后端无法机械强制只读时，该后端本次不可用。

对应 finding：MB-GRILL-008。

### FR-MB-005：代码读取方式分支

- `chatgpt-tunnel`：维持 Tunnel `work/<相对路径>` repo 名 + 逃逸句，禁止绝对路径；审核方自行读取，本地不发送代码内容。
- `mcp-review`：快照发送，不传仓库路径（Router 单跳语义，grilling 不使用该形态做多轮）。
- `opencode-cli` / `codex-cli`：给定工作区 cwd 与相对 `scope` 列表，审核方直接 Read/Grep/Glob；不使用 Tunnel。

### FR-MB-006：事实源单向引用（不复制）

| 事实 | canonical 属主 | grilling 的角色 |
|---|---|---|
| backend 调用命令、能力、只读模式、可用性/临时退出码分类、`result_schema` | `dd-workflow-runtime/agents/review-backends.yaml` | 引用 |
| 候选顺序、允许降级的失败分类 | `dd-workflow-runtime/agents/routing-policy.yaml` | 引用 |
| 幂等键、提交状态机、返工计数 | `dd-workflow-runtime/references/runtime-contract.md` | 复用其合同 |
| finding 三字段的枚举语义 | `gpt-grilling-review` | 拥有（结果合同须机械兼容，见 FR-MB-017） |
| stateful grilling 候选序列（区别于 Router 单跳链） | `dd-workflow-runtime/agents/routing-policy.yaml` | 引用（见 FR-MB-018） |
| 多轮编排、finding 生命周期、关闭权、续接与读取模板 | `gpt-grilling-review` | 拥有 |

`transport.md` **不得**复制上述任何表格或命令清单，只写"引用哪个属主的哪个字段"与本 skill 自有的编排规则。

对应 finding：MB-GRILL-004。

### FR-MB-007：降级、阻塞与 reviewer 连续性

分两个语义阶段，规则不同：

1. **首次审查尚未发生（PRE_INITIAL_REVIEW）**：后端不可用时按 `routing-policy.yaml` 的候选顺序降级。
2. **已产生 finding 之后（ACTIVE_GRILLING_SESSION）**：原 reviewer / 会话不可恢复 → `BLOCKED: reviewer_continuity_lost`，**默认不得切换 reviewer**。
3. 若未来支持 reviewer 转移，必须作为独立协议，要求：完整原 finding、原审核证据、全部修复 diff、当前源码、baseline，且新 reviewer 完整重新验证；不得称之为"继续原会话"。
4. 任一后端返回 FINDINGS / schema 非法 / 基线漂移 / 只读违例 / 续接违例：**不得降级**（fail-closed）。
5. 后端可用性降级**不增加**返工计数，也**不清零**已有计数。

对应 finding：MB-GRILL-005。

### FR-MB-008：不改名、不新建顶层 skill、属主措辞收窄

1. 保留 `gpt-grilling-review` 名称与属主身份；多后端不新建成顶层 skill。
2. `AGENTS.md` §8 表述改为："外部强审 finding 闭环及其多轮编排：`gpt-grilling-review`"——**收窄措辞**，不写"与传输"以免被读成 grilling 拥有全部 backend 传输事实。

对应 finding：MB-GRILL-014。

### FR-MB-009：幂等、去重与崩溃恢复

1. 复用 runtime 的供应商中立外部审核防重合同（`runtime-contract.md`）；具体字段、状态名与状态机由 runtime 拥有，**本文不复制**。
2. grilling 侧不变式：提交不确定状态恢复后，必须先用幂等键与后端对账，确认无在途任务才允许重新提交——**重复提交次数为零**。
3. **resume 重试 ≠ submit 重试**，两者不得共用重试语义。

对应 finding：MB-GRILL-009。

### FR-MB-010：返工轮次上限

1. 复用 canonical `routing.max_rework_cycles`（默认 2），达到上限停止并 BLOCKED。
2. 计数规则：finding 修复后重新送复审算一次；REOPEN 后再修改再复审继续递增；后端可用性降级不计入、也不清零。

对应 finding：MB-GRILL-010。

### FR-MB-011：会话句柄的归属、并发与生命周期

以下不变式由本文冻结；字段 schema 与保留策略由 runtime 状态属主定义，grilling 只消费、不私有保存。

1. 句柄唯一绑定一个 workflow + backend + reviewer 身份，**不得跨 workflow 复用**。
2. 一个 active grilling session **同时只允许一个 in-flight 轮次**；并发续接必须机械串行化。
3. `initial` 创建句柄；`resume` 只能使用该 workflow 当前的 active 句柄。
4. 派生类调用（如 `--fork` 形态）生成新句柄并保存 parent 关系；**旧句柄不自动转移关闭权**。
5. 崩溃后仅从 runtime 持久状态恢复，不从 stdout、临时文件或 provider 私有文件重建。
6. workflow 完成或放弃后，句柄转为历史证据，不再作为 active 句柄参与续接。
7. 保留与回收策略引用 runtime canonical policy，本文不另设。

对应 finding：MB-GRILL-011。

### FR-MB-012：能力探测与失效触发器

1. 能力证据至少绑定：backend ID、CLI / provider 版本、调用形态、只读模式、agent / profile、续接方式、结果格式。
2. **检查时机（MUST）**：每次 `initial` 前、每次 `resume` 前、以及从中断状态恢复后，都必须检查是否存在与当前 backend / 版本 / 调用形态 / 只读模式 / profile 完全匹配的有效能力证据；缺失或指纹不匹配时先重新取证，取证未通过则该调用形态本次不可用。
3. 失效触发器：CLI 版本变化、agent / profile 变化、只读配置变化、adapter 调用形态变化、续接参数变化。触发后旧证据失效，须重新取证。

对应 finding：MB-GRILL-012。

### FR-MB-013：结果合同双层分离（DEC-MB-03）

1. **传输层结果**：后端一轮只返回 `dd-review-result/1`（`PASS` / `FINDINGS` / `BLOCKED`），属主为 runtime。
2. **关闭层结果**：grilling 在其上定义从属 closure 合同（`CLOSED` / `REOPEN` / `VERIFICATION_REQUIRED` / `HUMAN_DECISION_REQUIRED`），属主为 `gpt-grilling-review`。
3. 转换规则（写死）：
   - `BLOCKED` → **永不得** CLOSED；
   - `FINDINGS` → 必须逐条分流处置，不得整体视为 CLOSED；
   - `PASS` → 仅作为 targeted review 的 CLOSED 候选，仍须满足 CLOSED 判据四项，由 grilling 状态机落地。
4. 不得把 `dd-review-result/1` 的 `PASS` 与 finding 的 `CLOSED` 等同。

对应 finding：MB-GRILL-007。

### FR-MB-014：OpenCode 续接语义区分（DEC-MB-01 的具体化）

| 参数 | 语义 | grilling 用法 |
|---|---|---|
| `--session <id>` | 继续指定会话 | **canonical 续接方式** |
| `--continue` | 继续"最近"会话 | 交互式便利，**不得作为可恢复自动化的合同**（存在被其他任务改写的歧义） |
| `--fork` | 派生子会话 | 会话身份发生变化，必须生成新句柄并保存 parent 关系 |

对应 finding：MB-GRILL-013。

### FR-MB-015：续接由 adapter 提供（DEC-MB-01）

1. canonical adapter 必须具备 `initial` 与 `resume` 两种调用形态，并对两者都输出可校验的会话标识。
2. grilling 只编排轮次（何时再叫同一个 reviewer 一次），**不直接拼装 provider 命令行**。
3. 本需求不规定 adapter 内部实现，只规定其合同外沿：调用形态、会话标识输出、只读模式、退出码分类、结果 schema 均由 runtime registry 拥有。

对应 finding：MB-GRILL-002。

### FR-MB-016：结构化会话标识接口（DEC-MB-01 与 DEC-MB-03 的接口）

1. runtime 拥有的 adapter 合同必须为 `initial` 与 `resume` 两种调用形态提供**结构化**会话标识输出，供 grilling 执行身份校验。
2. 在该结构化合同落地前，grilling **不得**通过非结构化 evidence、stdout 旁路或 provider 私有字段自行解析会话标识——那样既无法机械校验，也会形成隐式 schema。
3. 该字段是加进 `dd-review-result/1` 还是放进 runtime 拥有的 envelope，由 runtime schema 属主决定；**本文只提属主级要求，不自行造字段**。

对应 finding：MB-GRILL-016。

### FR-MB-017：finding 三字段的机械语义兼容

1. grilling 的三字段枚举语义（`SEVERITY`、`CLASSIFICATION` 的 F/V/H、`CHANGE_RISK` 的 LOW/MEDIUM/HIGH）由 `gpt-grilling-review` 拥有；本文不复制枚举定义。
2. 对可用于 grilling 的 backend，runtime 拥有的 `dd-review-result/1` finding 合同必须**机械保证** `severity`、`classification`、`change_risk` 与上述 canonical 语义一致，**不得允许 provider 定义另一套枚举含义**。
3. **主审裁决（2026-09-02，runtime targeted 复查 + 2026-09-03 争议复核，见 §11.6）**：`STATUS: CLOSED`——原 finding 已真正解决、未越权、无新增 finding、CHANGE_RISK 保持 HIGH 未降级。**尚未 commit**，commit 需单独授权。
4. **落地状态（2026-09-02 二次核实，如实记录）**：
   - **已实现但未提交**：`dispatch-review.py` 的 `_validate_finding` 已加三字段 canonical 枚举校验（`SEVERITY_VALUES` / `CLASSIFICATION_VALUES` / `CHANGE_RISK_VALUES`，与 `gpt-grilling-review/SKILL.md` 三个独立字段的定义逐项一致，且 `_validate_finding` 是 findings 归一化的**唯一**路径，无旁路）；配套 `test_dispatch_review.py` 新增 `FindingEnumContractTests`（5 项）与 1 项归一化入口测试；`codex/strong-reviewer.toml`、`opencode/strong-reviewer-cli.md` 的示例已从 `behavioral-correctness` / `behavioral` 改为 canonical 值。全量 `test_*.py` **170 项通过**（baseline `ba2df3d` 为 **164 项**），`validate-review-routing.py` 与 `validate-bindings.py` 通过。
   - **完整性缺口已补齐**：`tests/test_codex_review.py:41-42`、`tests/test_opencode_review.py:38-39` 的"合法输出"fixture 已改为 `FINDING` / `MEDIUM`（此前与 router 新校验给出两个互相矛盾的"合法 finding"答案）。**保留** `test_opencode_review.py:89` 与 `:166` 中的 `"x"` / `"y"` 占位值——前者测 tool 事件与文本提取、后者测 PASS 带 findings 被拒，均不经过枚举校验，与合同无关。
   - `tests/evidence/*-l7-evidence.yaml` 中的旧值**保持不变**：属历史取证记录，不得回溯改写；主审已确认它们不是当前 runtime 归一化入口的输入，不会绕过新校验。
5. 枚举与 schema 校验的实现由 runtime 属主完成；在该机械校验落地前，多后端 finding 的 F/V/H 分流不得视为已保证。

对应 finding：MB-GRILL-019。

### FR-MB-018：stateful grilling 候选序列

1. 候选顺序与降级分类的属主仍是 `routing-policy.yaml`，grilling 不另建 policy 文件、不自行维护 fallback 顺序。
2. runtime 必须在该属主内提供一个**与 Generic Router 单跳链相区分**的 canonical stateful 候选序列（角色名与 key 由 runtime 决定，本文不自行造字段）；该序列中只允许包含满足 FR-MB-001 三项能力条件的 backend。
3. **不得**把 `chatgpt-tunnel` 直接塞进 Router 现有的 `strong-reviewer` 单跳链——那会改变 Router v1 的单跳语义。
4. 现状缺口（2026-09-02 核实）：`routing-policy.yaml` 的 `strong-reviewer` 链为 `[mcp-review, codex-cli, host-native]`，既不含 `chatgpt-tunnel`／`opencode-cli`，也服务于单跳语义，尚无可引用的 stateful 序列。缺口补齐前，FR-MB-007 的 PRE_INITIAL_REVIEW 降级无可引用的 canonical 顺序，须按 `backend_unavailable` 阻塞而非自行排序。

对应 finding：MB-GRILL-020。

### FR-MB-019：受审候选基线标识（Review Baseline Identity）

**为什么需要**：FR-MB-004 的只读强制只保证"reviewer 不改东西"，**不保证"reviewer 看到的东西在两轮之间没被第三方改过"**。本地 CLI 后端（`opencode-cli` / `codex-cli` / `codex-native` / `opencode-native`）读的是**活的**工作树：主 Agent 的修复提交、其他进程、或并发任务都可能在第 N 轮与第 N+1 轮之间改变受审内容，使后一轮 verdict 不再对应前一轮的修复结果——此时 CLOSED 判据失去所指对象。

1. 每个 authoritative review turn 必须绑定一个**受审候选标识**（candidate identity），至少能区分：仓库 / 工作区身份 + 内容状态（例如 `HEAD SHA` 与受审 scope 的内容或 diff hash）。该标识的字段名与持久化方式由 runtime 状态属主定义，**本文不自行造字段**（沿用 FR-MB-006 的单向引用纪律）。
2. **捕获与复核时机（MUST，方案 A，2026-09-03 用户裁决）**：每轮送审前必须先 commit 当轮修复（WIP commit 可接受），以该 commit 的 HEAD SHA 作为本轮 candidate identity，工作树必须干净。在 verdict 进入 CLOSED 判据**之前**重新校验 HEAD 仍等于该 SHA 且工作树仍干净；不通过 → 按既有 runtime canonical 状态 `baseline_mismatch` 处理（**不新造状态名**），本轮 verdict **不得用于 CLOSED 任何 finding**，并 fail-closed（按 FR-MB-007 第 4 条，不得降级）。
3. **与只读强制正交**：基线标识防"受审内容被第三方改变"，只读强制防"reviewer 自身产生副作用"。**满足只读 ≠ 满足基线一致**，两者不得互相替代或合并取证。
4. **证据生命周期分离（MUST）**：candidate identity **不属于** readonly capability proof，不得作为只读能力证据的替代。`readonly evidence` 与 `baseline evidence` 必须**分别持久化、分别失效、分别重新取证**——任一份失效只使它自身失效，不得牵连另一份的有效性判断。
5. **适用于所有 grilling 后端**，包括 `chatgpt-tunnel`：审核方经授权通道自读时，本地同样无法保证其读取的远端状态在多轮之间不变。各后端如何捕获该标识，由 runtime 属主按后端读取方式分别定义。
6. **与 runtime 既有机制的关系（2026-09-02 本地核对订正，见 §11.7 MB-GRILL-027）**：
   - runtime **已存在**冻结基线校验 `_verify_frozen_baseline`（`dispatch-review.py:567-581`），校验 HEAD 是否等于请求 `head_sha`、工作树是否干净、scope 是否全部 git 跟踪，失败即抛 `baseline_mismatch`。因此 v0.5 所称"runtime 无任何 candidate identity 机制"**与事实不符**，此处订正。
   - 该既有机制服务的是 **Router 单跳**语义：它要求工作树**完全干净**，而 grilling 多轮闭环必然在首轮之后产生修复改动。二者若直接混用，多轮复审会在第二轮起就被 `baseline_mismatch` 拒死。
   - 因此 FR-MB-019 要求的是**多轮语境下的跨轮基线复核**，与单跳冻结基线不是同一件事；**裁决结果（2026-09-03，用户采纳方案 A）**：grilling 多轮**复用**既有单跳机制——每轮送审前 commit（WIP 可接受）→ 工作树恢复干净 → 该轮 HEAD SHA 即 candidate identity → 由既有 `_verify_frozen_baseline` 机械校验。"工作树干净"与多轮语义的冲突由"每轮先 commit"化解；不新增多轮专用机制，**不新造第二个状态名**（那正是 FR-MB-020 要防的第二套规则）。
   - 在裁决与落地前，多后端多轮 verdict **不得视为可 CLOSED 的证据**（fail-closed），本地 CLI 后端的多轮形态不可用。

对应 finding：MB-REVIEW-005（补登，见 §11.5）。

### FR-MB-020：transport / runtime 状态与 finding 命名空间正交

1. **runtime registry 中所有 `failure_category` 取值均属 transport / runtime 命名空间，不是 grilling finding。** 该集合的 canonical 属主是 runtime（`dispatch-review.py` 的 `KNOWN_FAILURE_CATEGORIES`，2026-09-02 核实为 17 项）：`all_backends_unavailable`、`authorization_violation`、`backend_execution_failed`、`backend_unavailable`、`baseline_mismatch`、`capability_unavailable`、`configuration_invalid`、`endpoint_unavailable`、`evidence_mismatch`、`executable_missing`、`readonly_violation`、`recursion_violation`、`review_incomplete`、`schema_invalid`、`security_policy_violation`、`temporary_backend_failure`、`verification_failed`。本文**引用而非复制**该集合（FR-MB-006）。
2. grilling 自身新增的阻塞状态（`reviewer_continuity_lost`、`session_resume_mismatch`；FR-MB-019 经 2026-09-03 用户裁决**复用既有 `baseline_mismatch`，不新增状态名**）同样适用本规则；**但新状态名不得与 runtime 既有 `failure_category` 重名或语义重叠**——命名须先查上表（MB-GRILL-027 即因 `baseline_drift` 与既有 `baseline_mismatch` 撞车而退回）。
3. **默认继承规则（防止未来遗漏）**：runtime 后续新增的任何 `failure_category`，**默认继承本条规则**（属 transport / runtime 命名空间、不得被赋三字段、不得进 finding 生命周期），除非经协议变更**显式声明**其为业务 finding。据此，枚举清单不完整不再成为漏洞入口。
4. 上述状态**不得**被赋予 `SEVERITY` / `CLASSIFICATION`（F/V/H）/ `CHANGE_RISK` 三字段，**不得**进入 finding 生命周期，**不得**参与 CLOSED / REOPEN / 逐条裁决分流，**不得**计入返工计数（与 FR-MB-007 第 5 条、FR-MB-010 第 2 条一致）。
5. **唯一转化路径**：只有当 reviewer 在结构化结果中**显式返回**业务 finding 时，该条目才进入 grilling 生命周期。任何"把阻塞状态包装成 finding 以便走裁决流程"的写法一律 fail-closed——那正是 FR-MB-008 / 第 10 节要防的"第二套 finding 规则"。
6. 阻塞状态的处置动作是"修复环境 / 配置 / 取证后**重跑该轮次**"，不是"逐条裁决"。
7. **待核实（VERIFICATION_REQUIRED）**：需确认 `dispatch-review.py` 与 grilling 编排实现中，不存在把 transport 状态 materialize 成 finding 的既有路径。该项曾由主审口头确认，但主审随后出现事实陈述失真（§11.6，已于 2026-09-03 争议复核中自读更正），故**不得以口头确认为据**，仍需机械核实。

对应 finding：MB-REVIEW-012（补登，见 §11.5）。

## 6. Non-Functional Requirements（非功能需求）

- NFR-MB-001：后端选择**不得改变既有 routing / budget eligibility**——对同一条 grilling 状态机轨迹，不得因 transport 后端选择而增加额外的强模型审核 round（多轮返工次数由 FR-MB-010 的 canonical 上限约束，与后端选择正交）。低风险任务独立强模型调用为零，沿用 `model-routing.md` NFR-002。
- NFR-MB-002：句柄、**受审候选标识（FR-MB-019）**、只读证据、覆盖清单、幂等键、返工计数作为可恢复证据持久化，支持跨轮与中断恢复；具体字段由 runtime 状态属主维护。
- NFR-MB-003：每个后端分节可独立验证（续接身份校验 + 只读证据 + 结果 schema 校验），互不牵连。

## 7. 草案设计（Design Sketch）

### 7.1 分层结构（替代 v0.1 的两层）

```
gpt-grilling-review
├─ grilling 协议层（后端中立）
│  finding 生命周期 / 三字段 / CLOSED 判据 / DISPUTED / HARD-GATE / 关闭权
├─ 有状态会话编排层（本 skill 拥有）
│  review_session_handle / 轮次顺序 / reviewer 连续性 / 返工计数 / 恢复
├─ canonical adapter 合同（runtime 拥有）
│  initial / resume / 归一化结果 / 退出码分类 / 只读证据
└─ runtime canonical 事实
   review-backends.yaml / routing-policy.yaml / runtime-contract.md
```

原则：**grilling 拥有"何时再叫同一个 reviewer 一次"；runtime 与 adapter 拥有"这个后端应怎样被安全、规范地调用"。**

### 7.2 文件改动

| 文件 | 改动 |
|---|---|
| `gpt-grilling-review/SKILL.md` | 新增后端选择输入项；协议层术语去 ChatGPT 化（保留"同一强审身份/同一闭环上下文"语义，不做机械全局替换）；引用重构后的 transport |
| `gpt-grilling-review/references/transport.md` | 重构成后端中立合同：编排合同 + 续接句柄与身份校验 + 只读矩阵（引用，不复制）+ 各后端分节 + 降级与阻塞 |
| `dd-workflow-runtime/agents/review-backends.yaml` | 按 DEC-MB-01 增加 `initial` / `resume` 调用形态与会话标识输出约定；按 DEC-MB-02 **新增 `chatgpt-tunnel` canonical backend，并保留 `mcp-review` 原单跳快照语义不变**（属 runtime） |
| `dd-workflow-runtime/agents/dispatch-review.py` | 按 FR-MB-017 把 finding 三字段从"非空字符串"校验升级为 canonical 枚举校验（属 runtime，需连带其测试） |
| `dd-workflow-runtime/agents/routing-policy.yaml` | 按 FR-MB-018 增加/扩展与 Router 单跳链相区分的 stateful grilling 候选序列（属 runtime） |
| `dd-workflow-runtime` reviewer 合同（`strong-reviewer-cli.md`、`strong-reviewer.toml` 等） | 按 FR-MB-017 对齐 canonical 三字段枚举，移除 `behavioral-correctness` 一类 provider 自定义取值（属 runtime） |
| `dd-workflow-runtime/agents/codex-review`、`opencode-review` | 实现 `resume` 子形态（属 runtime，需连带其测试） |
| `AGENTS.md` §8 | 措辞按 FR-MB-008 收窄 |
| 测试 | 续接身份校验、未知 backend fail-closed、双层结果转换、返工上限等合同测试 |

### 7.3 职责边界（与 Router）

- `gpt-grilling-review`：多轮编排、finding 生命周期、关闭权、逐条裁决。
- `dd-workflow-runtime` Router v1：单跳、无状态、不关闭 finding。
- 两者共享 backend registry 与只读证据，各自只引用不复制。

## 8. Open Questions（实测回填后）

1. **Codex 续接与只读开关（未决，fail-closed）**
   - 已实测（2026-09-02，codex-cli 0.149.1）：`codex exec --json` 输出 `thread.started.thread_id`；`codex exec resume <thread_id> <prompt>` **非交互续接有效**（恢复首轮埋点 7391，thread_id 不变）。
   - 已实测：`codex exec resume` **不接受 `--sandbox` / `--cd`**（报 `unexpected argument`）。续接时无法用命令行显式声明只读，只能用 `-c sandbox="read-only"`。
   - 待取证：`-c sandbox="read-only"` 的有效性。写入对照探测中，对照组（`--sandbox danger-full-access`）同样被 `sandbox-exec: sandbox_apply: Operation not permitted` 拦下，**当前环境无法区分两者**，故该开关有效性未证实。在取证前 `codex-cli` 的续接形态不可用。
   - 取证要求：必须在非嵌套沙箱环境（如 CI 或独立终端）做**行为正负对照**——正、负两组**都使用 resume 调用形态、只改变 sandbox 配置值**，不得把 `initial --sandbox` 与 `resume -c sandbox=` 两种形态混进同一对照；同时检查文件内容 / hash、文件列表与 Git 状态。配置解析或回读只能作辅助证据，**不能单独证明沙箱真正阻止写入**。
   - 结论边界：Codex 的 `initial` 形态可沿用既有 backend-bound 只读证据；`resume` 是新调用形态，在取得上述对照证据前**不得复用旧证据、不得启用**。
2. **OpenCode 会话续接身份与权限合同连续性：CLOSED（2026-09-03，主审终确认）**
   - 已实测（2026-09-02，opencode 1.18.25）：`opencode run --format json` 输出 `sessionID`；`opencode run --session <sessionID> --format json` **续接有效**（恢复首轮埋点 4826，sessionID 一致）。
   - 第一轮取证（2026-09-03）：同 agent、只差 `--session` 的写探测——write 工具在两轮中均不存在于可用工具集（agent 自报）；主审核实为 `VERIFICATION_REQUIRED`：**agent 自述不构成引擎级证据**（无 tool schema、无拒绝事件、无成功 read 事件），evidence 中 "engine-enforced" 标注被点名为过度断言并已修正。
   - 第二轮补证（2026-09-03，按主审最小补证方案）：initial 与 resume 各执行一次真实 read——**两轮均产生事件级 `tool_use: read, state.status=completed`**，输出与本地独立核对一致（`# AGENTS.md`）；resume 轮 sessionID 与首轮一致（`ses_f9af604f…`）且准确复述上轮探测编号（`MB-OC-C0903`）；全程无写工具暴露。
   - **主审终确认（STATUS: CLOSED）**，边界声明（原文引用）：
     > 真机取证确认，在 `opencode-cli` + `strong-reviewer-cli`、OpenCode **1.18.25**、调用形态 `opencode run --session <sessionID> --agent strong-reviewer-cli --format json` 下，initial 与 resume 两轮保持同一 `sessionID`，且两轮均产生实际 `read` tool event 并以 `state.status=completed` 成功读取同一 repo 文件，证明 allow-side 只读工具能力在 resume 形态连续；write 能力在两轮均未暴露，但该部分证据等级为 agent-self-reported-consistent，而非 engine-denial-event-backed。该结论**仅覆盖上述 backend / agent / OpenCode 版本 / resume 调用形态，不外推到其他 agent、版本、backend 或调用形态**。
   - 证据：`dd-workflow-runtime/tests/evidence/opencode-resume-readonly-evidence.yaml`（4 份原始事件流）。
3. **只读证据覆盖面**：任何新增调用形态（尤其是带会话标识的续接形态）是否仍被现有 backend-bound 只读证据覆盖？未被覆盖的调用形态须重新取证，不得沿用。
4. **后端选择策略归属**：已裁决——grilling 不另设独立 backend-selection policy，候选顺序与降级分类引用 `routing-policy.yaml`。

## 9. 验证证据

| 项目 | 结果 |
|---|---|
| 既有校验 `validate-review-routing.py` | 通过（5 backends / 1 roles） |
| 既有测试 `test_dispatch_review.py` | 37 项通过（unittest） |
| Codex 非交互续接 | 通过（句柄 `01a05fd7-…`，恢复埋点 7391） |
| Codex `resume` 不接受 `--sandbox` | 复现（`unexpected argument '--sandbox' found`） |
| Codex 只读开关有效性 | **未证实**（对照组同样被拦，证据不足） |
| OpenCode `--session` 续接身份 | 通过（句柄 `ses_fa028e8e5ffe…`，恢复埋点 4826）；只读资格见下行 |
| OpenCode 续接形态权限合同连续性（2026-09-03，两轮取证） | **CLOSED**：第一轮 write 侧 agent 自述被判不足（"engine-enforced" 过度断言被点名修正）；第二轮按最小补证方案补齐**事件级正向 read**（initial/resume 均 `read completed`）、sessionID 连续、编号复述准确——主审终确认，引用边界限定 opencode-cli + strong-reviewer-cli + 1.18.25 + resume 形态 |

## 10. 风险与红线

- 不得因多后端复制 finding 生命周期或关闭权规则（违反单一事实源）。
- 不得为"换后端"放宽只读或关闭权。
- 不得把 Router 的单跳结果当成 grilling 的 CLOSED。
- 不得把后端返回 `PASS` 等同于 finding `CLOSED`；`BLOCKED` 永不得 CLOSED。
- 不得把进程退出码 0 当作续接成功证据；必须校验实际会话身份。
- 不得把显式未知 backend 当作默认后端（显式未知即 BLOCKED）。
- 不得绕过 canonical adapter 自行拼装 provider 命令行。
- 不得把 `--continue`（最近会话）作为可恢复自动化的续接依据。
- 不得在 finding 已存在后静默更换 reviewer 并继承原 reviewer 的 CLOSED 权限。
- 不得复用与当前 backend / 只读模式 / 调用形态不匹配的只读证据。
- 不得无限返工；须遵守 canonical 返工上限。
- 不得在同一会话并发发送多个有序闭环轮次，除非有机械串行化合同。
- 不得在崩溃恢复后未经幂等键对账重新提交同一审核。
- 不得在非结构化 evidence、stdout 旁路或 provider 私有字段上自行解析会话标识。
- 不得把"存在于 registry"当作"可用于 grilling 多轮"（无续接能力或只读证据不足者不可选）。
- 未实测的后端续接与只读开关不得标 `confirmed`。
- 不得在受审候选标识未绑定或已漂移时用本轮 verdict 关闭任何 finding；**机械只读不等于基线一致**，两者不得互相替代（FR-MB-019）。
- 不得把 transport / runtime 阻塞状态包装成 finding，赋予三字段或送进 CLOSED 分流（FR-MB-020）。

## 11. 复核状态（如实记录，不掩饰）

### 11.1 ChatGPT 复审轮次

| 轮次 | 输入版本 | 结论 | finding 处置 |
|---|---|---|---|
| 第一轮 | v0.1-DRAFT | 14 个 finding（8 HIGH / 5 MEDIUM / 1 LOW） | 3 条架构项经用户裁决（DEC-MB-01~03）；11 条 FINDING 在 v0.2 处置 |
| 第二轮 | v0.2-DRAFT | `STATUS: REOPEN` | 5 条原 finding 未真正解决（001 / 004 / 008 / 011 / 012）+ 新增 4 项（015、016 HIGH；017、018 MEDIUM）→ 全部在 v0.3 处置 |
| 第三轮 | v0.3-DRAFT | `STATUS: REOPEN` | 上述 9 项**全部 CLOSED**；新增 2 项跨属主接口缺口（019 HIGH、020 MEDIUM）+ 2 处文案歧义 → 全部在 v0.4 处置 |
| 第四轮 | v0.4-DRAFT | `STATUS: REOPEN` | 经换新会话重审（见 11.2）：019 / 020 判为**文档已补齐但 runtime 未落地**，新增 021（`chatgpt-tunnel` 不在 registry 却已是默认后端） |

### 11.2 第四轮的传输层故障与处置（基础设施问题，非评审结论）

对 v0.4 的复审请求共提交三次，均未取得基于 v0.4 的新评审意见：

1. 第一次（task `767d5dda`）：返回内容与第三轮**逐字相同**（表头仍为"v0.3 复查"），判定为旧结果；
2. 第二次（task `218c51ae`）：加版本校验指令后重发，先 `[RUNNING]`，最终 `[FAILED] [TIMEOUT]`；
3. 第三次（task `012c3f54`）：精简提问（要求 400 字内）重试一次，仍返回与第三轮逐字相同的旧结论。

按 grilling 协议，基础设施失败最多重试 1 次，额度已用尽。经用户裁决换新会话（新 `conversation_id`）重审后取得**真实**回复，上述"缓存旧结论"问题确认是传输层副作用，不是评审意见。

### 11.2.1 第四轮真实结论（2026-09-02，新会话）

| finding | 结论 | 主审理由 |
|---|---|---|
| MB-GRILL-019 | `REOPEN`（HIGH） | 文档层属主划分正确，但 runtime 未机械校验三字段枚举，仍未满足 FR-MB-017 |
| MB-GRILL-020 | `REOPEN`（MEDIUM） | `routing-policy.yaml` 尚无 stateful 候选序列，FR-MB-018 第 2 条未满足 |
| MB-GRILL-021 | 新增（MEDIUM，`introduced_by=v0.4`） | 文档把 `chatgpt-tunnel` 设为默认后端，但该 backend 不在 registry 中，默认路径当前不可解析 |

三项均属 **runtime 落地缺口**，不是本文档的架构或措辞问题。主审明确：在 019 / 020 / 021 处理前不建议批准。

### 11.3 本地自证（弱模型自核，不等于主审 CLOSED）

v0.4 相对 v0.3 的改动已逐项覆盖第三轮主审给出的最小修改集，逐条自核如下：

| 主审要求的最小修改集 | v0.4 落地位置 | 自核结论 |
|---|---|---|
| 1. 新增"finding 三字段必须机械兼容 grilling canonical 语义"的属主级 requirement | FR-MB-017 + FR-MB-006 属主表新行 | 已落地；现状缺口（`dispatch-review.py:659` 只校验非空字符串、reviewer 示例为 `behavioral-correctness`）已本地核实属实并写入 FR-MB-017 第 3 条 |
| 2. 明确 `routing-policy.yaml` 需拥有区别于 Router 单跳链的 stateful 候选序列 | FR-MB-018 + FR-MB-006 属主表新行 | 已落地；现状缺口（链为 `[mcp-review, codex-cli, host-native]`、服务单跳语义）已本地核实属实并写入 FR-MB-018 第 4 条 |
| 3. §7.2 补两项未来 runtime contract 改动 | §7.2 新增三行（registry / `dispatch-review.py` / `routing-policy.yaml` / reviewer 合同） | 已落地 |
| 4. 修正 `chatgpt-tunnel` 措辞与"新增或重命名"歧义 | FR-MB-004 表格、§7.2 表格 | 已落地 |

### 11.4 未决事项

**批准阻塞项（均需 runtime 落地，超出本文档修订范围，待用户裁决）**

| ID | 缺口 | 需要改动的文件 | 性质 |
|---|---|---|---|
| MB-GRILL-019 | **已 CLOSED**（第五轮，2026-09-02，见 §11.6）——~~finding 三字段未做枚举校验~~。实现在 worktree 分支 `fix/mb-grill-019-finding-enum`，**尚未 commit** | 已完成：`dispatch-review.py` 的 `_validate_finding`、两个 reviewer 合同示例、新增合同测试、两个 adapter fixture canonical 化 | 生产代码 + 测试语义 |
| MB-GRILL-020 | **已落地（v0.8，未 commit）**——`routing-policy.yaml` 新增 `stateful_roles.strong-reviewer-stateful`（成员见 §11.10），validator 与测试同步；不影响 `strong-reviewer` 单跳链与 `max_hops=1` | 已完成 | 配置 + 代码 + 测试 |
| MB-GRILL-021 | **已落地（v0.8，未 commit）**——裁决为 registry 增加条目：`review-backends.yaml` 收编 `chatgpt-tunnel`（`router_selectable: false`，`tunnel-self-read-only`） | 已完成 | 跨 skill 范围决策 |

**VERIFICATION_REQUIRED（取证类，非批准阻塞，但阻塞对应后端启用）**

- Codex 续接形态的只读开关有效性（第 8 节 #1）：需非嵌套沙箱环境做行为正负对照，本机沙箱内无法完成。
- ~~OpenCode 续接形态下 `strong-reviewer-cli` 权限合同连续性（第 8 节 #2）~~：**CLOSED**（2026-09-03，两轮取证 + 主审终确认；证据 `opencode-resume-readonly-evidence.yaml`，引用边界限定 opencode-cli + strong-reviewer-cli + opencode 1.18.25 + resume 调用形态）。

**纪律**

- 上述三项**以及 §11.5 登记的 MB-REVIEW-005（FR-MB-019）**未处置前，本文档不得视为已批准。
- 处置涉及 runtime 生产代码与测试语义时，须按 `gpt-grilling-review` 的关闭权规则送回主审返回 `CLOSED`，本地不得自行关闭。
- 在用户裁决前，**不改动** `gpt-grilling-review/SKILL.md`、`references/transport.md`、`AGENTS.md` 及任何 runtime 文件。

### 11.5 本地审核意见补登（MB-REVIEW 命名空间）

v0.1 阶段曾产生一份针对本文的本地审核意见（MB-REVIEW-001~013）。该命名空间**从未进入任何 ChatGPT 复核台账**，v0.2~v0.4 只处置了 MB-GRILL 命名空间，导致部分意见被静默遗漏。2026-09-02 逐条核对 v0.4 后的结论：

| 处置状态 | finding | 说明 |
|---|---|---|
| 已在 v0.2~v0.4 落地 | 001 / 002 / 003 / 006 / 007 / 008 / 009 / 010 / 013 | 分别对应 §8 实测回填、FR-MB-014、FR-MB-007、FR-MB-001.3、FR-MB-006、FR-MB-008、FR-MB-004、FR-MB-009/011、DEC-MB-02 |
| 部分落地 | 004 | FR-MB-003 / 011 / 012 已覆盖身份校验、归属并发、能力探测维度，**缺"受审内容基线"维度**，由 v0.5 的 FR-MB-019 补齐 |
| v0.5 已处置（纯文档层，不阻塞批准） | 011 / 012 | NFR-MB-001 措辞改写；FR-MB-020 增加命名空间正交约束 |
| **v0.5 新增批准阻塞项** | 005 | FR-MB-019：需 runtime 定义 candidate identity 字段与持久化，grilling 实现捕获 / 复核时机 |

**纪律**

- FR-MB-019 属跨属主实现，须经用户裁决；未落地前本地 CLI 后端的多轮形态按 fail-closed 不可用，本文不得视为已批准。
- FR-MB-020 的转化现状属 VERIFICATION_REQUIRED（不阻塞批准，但阻塞"transport 状态未被污染 finding 命名空间"这一断言）。
- 本命名空间此后必须纳入台账：任何审核意见（无论来自主审还是本地审核）都须登记 finding ID 与处置位置，不得只留在会话里。
- **§11 各节（含 §11.5 / §11.6 / §11.7）仅记录复核历史与处置状态，不替代 canonical 属主**：backend 调用与 `failure_category` 属 `dd-workflow-runtime`；finding 三字段语义与关闭权属 `gpt-grilling-review`；候选顺序与降级分类属 `routing-policy.yaml`。台账不得被反向当作事实源引用（FR-MB-006）。

### 11.6 MB-GRILL-019 runtime 修复后针对性复查（2026-09-02，代码级 targeted，**不占 §11.1 文档轮次编号**）

> 编号说明：本文档级轮次以 §11.1 表为准（1~4 轮）+ §11.7（第五轮）+ 第六轮（见 §11.8）。本节是 runtime 代码的修复后复查，与文档轮次并行，此前误标"第五轮"与 §11.7 撞号，已订正。

| 项目 | 内容 |
|---|---|
| 形态 | 修复后针对性复查（非首次全量审核）；六段式数据包 risk / source / test / rule+req / judgment / scope |
| 送审对象 | worktree `work/AGENT/skills-worktrees/fix/mb-grill-019-finding-enum`，分支 `fix/mb-grill-019-finding-enum` |
| CHANGE_RISK | **HIGH**（跨 skill 合同变更 + 影响全部 backend 的 finding 准入 + fail-closed 语义收紧），**未降级** |
| 主审结论 | `STATUS: CLOSED`——原 finding 已真正解决、未越权、无新增 finding |
| 证据 | baseline `ba2df3d` 164 项 → 改动后 170 项全通过；两个 validator 通过；真实 diff + 当前源码经 Tunnel 由主审自读 |

**本地核对差异（如实记录，不掩饰）**

主审结论成立，但其中一条**事实陈述有误**：主审称 `test_opencode_review.py` 中"当前搜索未发现 `"x"` / `"y"` 命中"。实际**存在**两处：

- `test_opencode_review.py:89`（`test_reasoning_tool_mixed`）：测 tool 事件与最终文本提取，finding 内容为无关占位；
- `test_opencode_review.py:166`（`test_pass_with_findings_rejected`）：测 PASS 带 findings 被拒，枚举值为无关占位。

本地复核结论：两处**均不经过枚举校验**，与主审"不构成枚举合同漏洞"的结论一致，故**不改**。但该陈述本身失真，记录在此以免后续复审被误导。保留这两处占位值是有意决定，理由见 FR-MB-017 第 4 条。

**争议处置（2026-09-03 同会话 targeted reconsideration）**

按 DISPUTED 路径把上述反证送回主审（同 conversation_id），主审自读文件核实后返回 `STATUS: CLOSED`：

1. **事实记录已更正**：主审确认 `test_opencode_review.py:89` 与 `:166` 两处 `"classification":"x"` / `"change_risk":"y"` **确实存在**，此前"未发现命中"的描述错误；
2. **CLOSED 维持**：两处均在 adapter 层测试路径（`_extract_final_text` 的文本提取、PASS-with-findings 的拒绝），不进入 `_validate_finding` canonical 枚举入口，不构成 MB-GRILL-019 漏洞，无新增 finding、无需 `introduced_by`；
3. **保留占位值获得主审认可**，且补充了一个职责边界理由：若 adapter fixture 也写成 canonical 值，反而会让读者误以为 adapter 拥有枚举语义责任，模糊 adapter（管形状）/ router（管 canonical 语义）/ grilling（管生命周期）的分层；
4. **主审可选建议（未执行）**：给两处测试加"intentionally non-canonical"注释以防未来误读。属测试可读性增强、非 finding 修复，超出本轮授权（"补齐 fixture 后整体送主审"），**不擅自动手**，待用户裁决是否采纳。

**待办**

- MB-GRILL-019 已 CLOSED 但**未 commit**：按自动化约定，commit / push 需用户单独授权。
- 批准阻塞项剩余两项（MB-GRILL-020、021）与 §11.5 的 MB-REVIEW-005（FR-MB-019）。

### 11.7 第五轮：v0.5 文档级复审（2026-09-02）

**主审结论：`STATUS: REOPEN`**——核心架构方向正确，未发现 FR-MB-019 / FR-MB-020 引入新的架构冲突；但存在 1 项事实性问题需在批准前修正。

| ID | 级别 | 问题 | 位置 | v0.6 处置 |
|---|---|---|---|---|
| MB-GRILL-022 | HIGH | §0 称"本轮只改本文档，未改动任何 runtime 文件"，与 worktree 中 6 个 runtime 改动矛盾 | 文档 §0 版本状态行 | 已改为分开表述：文档修订只改本文档；worktree 另含 MB-GRILL-019 的未提交 runtime 落地 |
| MB-GRILL-023 | MEDIUM | FR-MB-019 未明确 candidate identity 与 readonly evidence 的证据生命周期关系 | FR-MB-019 | 新增第 4 条：分别持久化、分别失效、不得互为替代 |
| MB-GRILL-024 | MEDIUM | FR-MB-020 阻塞状态清单不完整（仅 8 项），且无未来扩展默认规则；本地核对发现漏列 12 个 runtime 既有 `failure_category` | FR-MB-020 第 1 条 | 改为引用 runtime canonical `KNOWN_FAILURE_CATEGORIES`（17 项）+ 新增第 3 条默认继承规则 |
| MB-GRILL-025 | MEDIUM | NFR-MB-001 的"round"与 resume/retry 易混淆 | NFR-MB-001 | 新增 round 定义消歧条款 |
| MB-GRILL-026 | MEDIUM | §11.5/§11.6 易被误读为 finding 事实源 | §11.5 纪律 | 新增声明：§11 只记历史与状态，不替代 canonical 属主 |

**本地核对另行发现（主审未识别，MB-GRILL-027，HIGH）**

主审判定"runtime 无相关机制"方向的陈述未被核验，实际不成立。本地核实：

- `_verify_frozen_baseline`（`dispatch-review.py:567-581`）**已存在**，校验 `HEAD == request.head_sha`、工作树干净、scope 全部 git 跟踪，失败抛 `baseline_mismatch`；
- `KNOWN_FAILURE_CATEGORIES` 共 **17 项**（`FALLBACK_CATEGORIES` 5 项 + 扩展 12 项），已列为 FR-MB-020 的 canonical 引用源。

由此产生三项后果，均已在 v0.6 处置或挂起：

1. v0.5 所称"grilling 与 runtime 均无任何 candidate identity 机制"**与事实不符** → FR-MB-019 第 6 条已订正；
2. FR-MB-019 新造的 `baseline_drift` 与既有 `baseline_mismatch` **命名撞车**，正是 FR-MB-020 要防的第二套规则 → 状态名回退为待裁决（FR-MB-019 第 2 条暂记 `baseline_drift?`）；
3. 既有机制要求**工作树完全干净**，而 grilling 多轮闭环在首轮之后必然产生修复改动——直接复用会让多轮复审在第二轮起被 `baseline_mismatch` 拒死。

**HUMAN_DECISION_REQUIRED（待用户裁决，裁决前不得实现）**

FR-MB-019 采用哪种基线模型：

- **方案 A｜提交后送审**：grilling 每轮复审前先 commit 修复，工作树恢复干净，candidate identity 复用既有 `head_sha` 与 `baseline_mismatch`。改动最小、零新增状态名，但强制 grilling 中间态必须产生提交。
- **方案 B｜允许 dirty 的 scope 内容基线**：runtime 新增多轮专用 candidate identity（scope 内容/diff hash），允许工作树在两轮之间 dirty。更贴合 grilling 语义，但需 runtime 新增机制与新的状态名，且须与单跳 `_verify_frozen_baseline` 明确并存边界。

裁决前本文不锁定状态名与实现路径；FR-MB-019 维持 fail-closed（多轮 verdict 不得视为可 CLOSED 证据）。

**用户裁决（2026-09-03，HARD-GATE 逐条裁决）：采用方案 A（每轮先 commit）。**

- 理由（用户采纳推荐项）：复用已验证的机械机制、**零新增状态名**（正面呼应 MB-GRILL-027 的撞名教训）、与既有 commit-and-push 工作流一致；中间态用 WIP commit 承接。
- 落地：FR-MB-019 第 2 条改为"每轮送审前 commit → 该轮 HEAD SHA 即 candidate identity → 复用 `_verify_frozen_baseline` / `baseline_mismatch`"；第 6 条补裁决结果；FR-MB-020 第 2 条同步。
- **MB-GRILL-027：`CLOSED`**（裁决已落地为条文；轻量 targeted 复核见 §11.9）。

**纪律**：因主审在第五轮与 §11.6 两轮均出现事实陈述失真，后续各轮主审关于"runtime 现状"的陈述一律须本地机械核实后方可采纳，不得直接引用为证据。

### 11.8 第六轮：v0.6 文档级复审（2026-09-03）

**主审结论：`STATUS: PASS`——零新增 finding（无 MB-GRILL-028+）。**

| 复核维度 | 结果 |
|---|---|
| runtime 现实一致性 | `_verify_frozen_baseline`（`dispatch-review.py:567-581`）与源码逐项一致；FR-MB-019 未再声称"runtime 无机制"，`baseline_drift?` 为裁决前占位，未形成第二套状态规则 |
| 内部一致性 | FR-MB-004（reviewer 是否改内容）/ FR-MB-012（capability 是否有效）/ FR-MB-019（candidate 是否漂移）三者边界清晰；NFR-MB-001 与 FR-MB-010 无冲突 |
| FR-MB-020 | 引用式设计（`KNOWN_FAILURE_CATEGORIES` 属主引用 + 默认继承规则）符合 FR-MB-006，堵住"清单漏列"类漏洞 |
| 方案 A/B 完备性 | 覆盖主要设计空间，未发现必须新增的第三方案（"临时 immutable snapshot"属方案 B 实现变体，不构成遗漏决策分支） |
| §11 台账 | §11.6 编号订正确认彻底；MB-GRILL-019 状态与审计历史一致 |
| 覆盖清单 | REVIEWED: 本文档；UNREADABLE: 无 |

**本地补验（主审诚实标注的未直读项）**：主审声明未直接读取 `KNOWN_FAILURE_CATEGORIES` 的定义位置。本地已机械补验：`dispatch-review.py:51` `KNOWN_FAILURE_CATEGORIES = FALLBACK_CATEGORIES | {12 项}`，5 + 12 = **17 项**，与 FR-MB-020 第 1 条引用清单逐项一致。

**剩余阻塞（均非文档缺陷）**

| 项 | 性质 |
|---|---|
| ~~§11.7 HUMAN_DECISION_REQUIRED：FR-MB-019 基线模型~~ | **已裁决（2026-09-03，方案 A）**，条文落地见 FR-MB-019 第 2/6 条，MB-GRILL-027 CLOSED |
| MB-GRILL-020（stateful 候选序列）/ MB-GRILL-021（`chatgpt-tunnel` 入 registry） | runtime 落地，跨 skill |
| MB-GRILL-019 改动 commit / push | 需用户单独授权 |

### 11.9 方案 A 落地的轻量 targeted 复核（2026-09-03）

**主审结论：`STATUS: CLOSED`——方案 A 落点忠实，无新增矛盾，未产生 MB-GRILL-028+。**

| 落点 | 结果 |
|---|---|
| FR-MB-019 第 2 条 | 通过。"WIP commit 可接受"**不侵蚀** candidate identity 机械性：identity 绑定不可变 commit SHA，`_verify_frozen_baseline` 只看 HEAD + clean worktree，不评判提交是否"漂亮"——WIP commit 是满足 candidate identity 的最小持久化边界 |
| FR-MB-019 第 6 条 | 通过。正确化解 MB-GRILL-027 核心矛盾：修复 → WIP commit → clean → 下轮送审；无需 dirty snapshot、无需 `baseline_drift`、无需新 `failure_category` |
| FR-MB-020 第 2 条 | 通过。与"阻止第二套阻塞状态体系"目标一致 |
| §11.7 / §11.8 | 通过。裁决记录未把"用户裁决"伪装成 runtime 已实现；阻塞表无遗漏 |
| 交叉检查 | FR-MB-011（句柄=reviewer 连续性，candidate=内容版本，两维度不混）、FR-MB-009（未引入"靠 git commit 恢复 workflow 状态"的错误语义）、FR-MB-007（fail-closed 不降级）、FR-MB-012（baseline evidence 与 capability evidence 分离保持）均无冲突 |
| 覆盖 | REVIEWED: 本文档；UNREADABLE: 无 |

### 11.10 MB-GRILL-021 / MB-GRILL-020 runtime 落地（2026-09-03；复核结论见 §11.11 / §11.12）

**021——registry 收编 `chatgpt-tunnel`（`review-backends.yaml`）**

- 新条目：`type: mcp`、`execution: external`、`router_selectable: false`、`readonly_mode: tunnel-self-read-only`、`capabilities: [strong-review]`、result_schema 不变；注释写明 Tunnel 自读模型与 transport 合同属主（`gpt-grilling-review/references/transport.md`）。
- `tunnel-self-read-only` 为 registry 新定义的只读模式类别（属 runtime 拥有），语义 = "审核方经授权 Tunnel 按 `work/<相对路径>` repo 名自读；本地不发送绝对路径与文件内容"——与 `snapshot-send-only`（本地发快照）是两个类别，对应 FR-MB-004 表格两行。
- **校验器配套改动（`dispatch-review.py`）**：
  1. 新增 `KNOWN_READONLY_MODES` 白名单（5 值：snapshot-send-only / tunnel-self-read-only / codex-read-only-transport / agent-read-only-contract / codex-route-guard），所有 backend 的 `readonly_mode` 必须属于该集合；
  2. 原"MCP 必须 snapshot-send-only"硬校验**收窄**为仅约束 `router_selectable` 非 false 的 MCP backend——grilling-only MCP 后端按 DEC-MB-02 走 Tunnel 自读，豁免但仍在白名单内；
  3. 新增 `GRILLING_ONLY_BACKENDS = {chatgpt-tunnel}`，机械禁止其进入任何 Router 单跳链（FR-MB-018 第 3 条落地）。

**020——stateful 候选序列（`routing-policy.yaml`）**

- 新增顶层 `stateful_roles.strong-reviewer-stateful`：`capability: strong-review`、`backends: [chatgpt-tunnel]`、`fallback_on` 仅含 5 个可用性类（与 FR-MB-007 一致：FINDINGS / schema 非法 / 基线漂移等一律不降级）。
- 该 key 由 **grilling 消费**（PRE_INITIAL_REVIEW 降级顺序），Router 派发循环不读取；成员允许 `router_selectable: false` 的 grilling-only backend。
- **成员现状与理由**：仅 `chatgpt-tunnel`。`opencode-cli` / `codex-cli` 的**续接形态**只读证据未取得（§8 #1/#2，VERIFICATION_REQUIRED），按 FR-MB-004 第 3 条 fail-closed 暂不加入；`mcp-review` 无续接能力；native 后端需宿主接管不适用。取证后可依序加入。
- **校验器新增 `stateful_roles` 规则**：成员必须存在于 registry；`router_selectable: false` 且非 grilling-only 的成员（如 native）拒绝；`fallback_on` 类别合法性；key 可选、存在则必须非空。

**验证**

| 项 | 结果 |
|---|---|
| 全量 `test_*.py` | **178 项通过**（170 → 178，+8 项 021/020 合同测试：白名单拒绝未知 mode、router-selectable MCP 保持 snapshot 硬校验、grilling-only 禁入单跳链、stateful 成员/引用/fallback 校验、checked-in 文件含 tunnel 与 stateful 序列） |
| `validate-review-routing.py` | OK：**6 backends / 1 roles** |
| `validate-bindings.py` | OK（6 宿主 / 7 角色） |
| 测试 fixture 同步 | `_backend()` readonly_mode 按类型对齐真实合同值（原 `"test-readonly"` 不在新白名单内，属预期收紧） |

**待办**：主审 targeted 复核（见 §11.10 送审）；复核 CLOSED 后 commit。

### 11.11 第七轮：020/021 落地 targeted 复查返回 REOPEN 与 v0.9 处置（2026-09-03）

**第七轮主审结论（同会话 targeted）**：`STATUS: REOPEN`——MB-GRILL-021 **CLOSED**；MB-GRILL-020 修复不完整；**新增 MB-GRILL-028**（MEDIUM / FINDING，`introduced_by=MB-GRILL-021`）。三项事实断言已经本地逐条核实**属实**：`review_session_handle` 在 dd-workflow-runtime 零命中；`conversation_id` 仅存在于 registry 注释与 mcp-review adapter 内部；stateful validator 不校验成员资格（连 `role_spec.capability` 与 backend `capabilities` 的对照都没有）。

| finding | 结论 | 要点 |
|---|---|---|
| MB-GRILL-021 | `CLOSED` | registry 收编成立；单跳链未变；GRILLING_ONLY 禁令有效 |
| MB-GRILL-020 | `REOPEN`（原问题未完全解决） | chatgpt-tunnel 被放入 stateful 序列，但它**不满足 FR-MB-001 三项资格**（runtime-owned 会话标识合同未落、adapter resume 形态未在 runtime 定义、续接形态无 backend-bound 只读证据）——按 FR-MB-018"只允许包含满足资格的成员"，放进去本身就是违规。已知缺口定级为**明确实现缺口**（非 VERIFICATION_REQUIRED，因为合同"不存在"是机械可确认的事实） |
| MB-GRILL-028 | `OPEN`（新增） | `router_selectable: false` 未实现为通用 Router 禁令：roles validator 只拒 GRILLING_ONLY、派发层只对 native-agent 检查——未来的 external false 后端可穿透 snapshot 豁免被单跳派发 |

**v0.9 处置（本轮）**

1. **MB-GRILL-028 已修（双禁令）**：①校验层——Router 单跳链 candidate（除 `host-native` 占位）一律拒绝 `router_selectable: false`（含外部类型）；②派发层——`_check_backend_eligibility` 对非 native 的 `router_selectable: false` 统一 fail-closed（native 保留专用 handoff 信息）。测试：新增"校验层拒绝 future external false 成员"与"派发层拒绝"两项。
2. **MB-GRILL-020 退到诚实过渡态**：`stateful_roles.strong-reviewer-stateful.backends: []`——FR-MB-016 会话标识合同与续接形态只读证据落地前，**没有任何 backend 满足三项资格**，空序列是唯一诚实的声明；validator 允许空序列（含注释），grilling 读到空序列必须按 `backend_unavailable` 阻塞（FR-MB-018 第 4 条预设的合规过渡）。**不虚构资格字段**——没实现的合同不标 true。
3. 测试：178 → **181 项通过**（+3：空序列过渡态、校验层通用禁令、派发层防御禁令）；validator 6 backends / 1 roles 不变。

**020 完全闭合的前置（超出本轮，待排期）**：FR-MB-015/016 的 runtime 会话标识合同落地（字段放 `dd-review-result/1` 还是 envelope 由 runtime schema 属主决定）+ adapter `initial`/`resume` 形态定义 + 续接形态 backend-bound 只读取证 → 之后 chatgpt-tunnel（及取证后的 opencode-cli / codex-cli）才可依资格进入序列，validator 按合同字段机械校验。

### 11.12 第八轮：v0.9 处置的确认性 targeted 复核（2026-09-03）

**主审结论：`STATUS: REOPEN`（仅因 020 前置未落地）——MB-GRILL-028 `CLOSED`；MB-GRILL-021 维持 `CLOSED`；MB-GRILL-020 维持 `REOPEN` 但**当前过渡态合规、不存在额外修复缺口**；零新 finding（无需 MB-GRILL-029）。**

| 项 | 结论 | 主审核对 |
|---|---|---|
| MB-GRILL-028 | `CLOSED` | 双禁令核对成立：校验层（`dispatch-review.py` roles 检查对所有直接 candidate 拒 `router_selectable: false`，除 host-native 占位）+ 派发防御层（`_check_backend_eligibility` external false → `capability_unavailable`，native 保留 handoff 专用语义）；两项新测试分别杀中两层 |
| MB-GRILL-021 | 维持 `CLOSED` | — |
| MB-GRILL-020 | 维持 `REOPEN`（过渡态合规） | 空序列不再错误宣称 chatgpt-tunnel 具备资格、不伪造 resume / session identity 能力字段、不影响 Router 单跳链与 `max_hops=1`、validator 有测试覆盖过渡态；最终关闭等待 FR-MB-015 / FR-MB-016 合同与续接只读取证落地 |
| 覆盖 | — | 主审核对了源码与新增 3 项测试，与本轮 181 tests OK + validator OK 口径一致 |

### 11.13 FR-MB-015 / FR-MB-016 runtime 合同落地与测试补齐（2026-09-03；第九轮 REOPEN → 029~032 已 CLOSED；第十轮新增 033，已处置待确认）

**第十轮 targeted 复核：`STATUS: REOPEN`——029 / 030 / 031 / 032 全部 `CLOSED`，但新增 1 项**：

| ID | 级别 | 问题 | 处置 |
|---|---|---|---|
| MB-GRILL-033 | MEDIUM（`introduced_by=MB-GRILL-030`） | 显式 continuation 的 session capability 未在派发前校验：原逻辑只对 `resume` 要求 `session_identity`，显式 `initial` 即使 backend 无该合同也先跑完真实审核，才在结果层 `session_resume_mismatch` | `_check_backend_eligibility` 改为**任何显式 continuation（initial 或 resume）都要求 canonical `session_identity` 合同**，fail-fast（`capability_unavailable`、adapter 不执行）；legacy 无 continuation 仍完全兼容 |

边界保持不变：无 `continuation` → legacy 单跳兼容；explicit initial → 必须有 session 合同；resume → 同样必须有。

**033 的两个 full-dispatch 测试**（主审指定）：①无合同 backend + 显式 initial → `runner.calls == []`；②有 canonical 合同 backend + 显式 initial → continuation 传入 runner、返回 initial session 后 `verified=true`。**负向验证已完成**：把校验临时换回"只查 resume"的旧逻辑，杀手测试立即变红，对照测试两种逻辑下均通过。

**第十轮复核：033 修复不完整（不建新 ID）→ 已补修**

主审指出 033 的原修复只检查“`session_identity` 是 dict”，而 registry 的 canonical 校验（`field == "session"`、owner 非空）原仅挂在“声明 resume”分支——于是 **initial-only backend 声明 malformed `session_identity` 时，registry 不校验、派发层误判“合同存在”**，explicit initial 仍会真跑。

补修：registry 规则拆成两条——①`resume ∈ invocation_forms` ⇒ `session_identity` **必须存在**；②**只要 `session_identity` 被声明（无论是否声明 resume）**，即机械校验 `field == SESSION_IDENTITY_FIELD` 且 owner 非空。legacy 边界不变（无 continuation、无 session_identity 的 backend 继续合法）。

**派发层未加冗余校验（有依据）**：先查证 `dispatch_review()` 在入口即执行 `validate_registry_policy`（`dispatch-review.py:1146`），配置错误会先返回 `BLOCKED / configuration_invalid`，因此 registry 修复是真实防线；按最小修复纪律不加第二处。

**杀手测试**：`test_initial_only_backend_with_malformed_session_identity_rejected`（initial-only + `field=wrong_field, owner=""` → 拒绝）＋对照 `test_initial_only_backend_with_canonical_session_identity_accepted`。**负向验证**：同一 malformed 配置在旧逻辑下被放行、新逻辑下被拒（field 与 owner 各一项报错），canonical 配置两种逻辑下均通过。

**033 状态**：`CLOSED`（第十一轮确认）。主审同时认可"不在派发层重复 canonical 校验"的判断——`dispatch_review()` 在任何 candidate selection 与 adapter 执行之前先跑 registry validator，生产路径上已是有效且先行的机械防线。**029~033 一并闭环，已 commit 并推送。**

**分工说明（如实）**：`dispatch-review.py` 的合同实现（+111 行）由并行会话完成、未提交；本会话盘点发现**零测试覆盖、registry 无任何 backend 声明、文档缺台账**，遂按"补齐后整体送主审"先例补测试与台账，并接手处置 029~033。

**第九轮 targeted 复核：`STATUS: REOPEN`——4 个新 finding，全部属实并已处置（第十轮确认 CLOSED）**：

| ID | 级别 | 问题 | 处置 |
|---|---|---|---|
| MB-GRILL-029 | HIGH | resume 请求没跨过 adapter 边界：`adapter_request` 不含 `continuation`，且派发前不检查 backend 是否声明对应 invocation form——真实链路上 resume 无法驱动 | ①`adapter_request` 携带经校验的 `continuation`（deepcopy）；②`_check_backend_eligibility` 新增：请求 form 必须 ∈ `backend.invocation_forms`，`resume` 还须有 `session_identity` 合同；③新增 full-dispatch 测试断言 runner 实际收到 `continuation`，以及未声明 form 的 backend 被拒（`runner.calls == []`） |
| MB-GRILL-030 | HIGH | 显式 `initial` 不强制返回 session identity（测试反而固化了该错误语义）→ 首轮后无 handle 可续接，闭环断裂 | 显式 `continuation.form == "initial"` 时必须返回 `session{form: "initial", handle 非空}` 并 `verified=true`，否则 `session_resume_mismatch`；**无 continuation 的 legacy 调用保持兼容**（允许无 session） |
| MB-GRILL-031 | MEDIUM | ①registry 对"声明 resume 但完全缺失 session_identity"不报错（与本台账旧文自述"必填"矛盾）；②`session_identity.field` 可任意声明但运行时硬编码 `raw.get("session")`——假合同 | registry 层收紧：`resume ∈ invocation_forms ⇒ session_identity` 必填且完整；`field` 固定为 canonical 值 `"session"`（新增 `SESSION_IDENTITY_FIELD` 常量），自由命名不再合法。采纳主审"后者更简单"方案 |
| MB-GRILL-032 | MEDIUM | 本会话两个 request 校验测试**误绿**：`_request()` fixture 缺 `host`/`repo`/`context`，先因 host 缺失报 schema_invalid，根本没走到 continuation 校验 | fixture 补全为完整合法 request；两个测试改为精确断言错误文本含 `continuation.handle` / `continuation.form` |

主审同时确认正确的部分：`session_resume_mismatch` 命名空间隔离（transport 状态、不进 finding 生命周期、不参与 fallback）、legacy 兼容、16 项测试"不是空转"。

**落地的合同（3 层）**

| 层 | 内容 | 位置 |
|---|---|---|
| registry 声明 | `invocation_forms`（默认 `["initial"]`、必须含 `initial`）＋ 声明 `resume` 时 `session_identity.{field, owner}` **必填**且 `field` 固定为 `"session"`（`SESSION_IDENTITY_FIELD`） | `review-backends.yaml`（本次无 backend 声明，见下） |
| stateful 资格 | 序列成员必须同时满足：声明 `resume` 形态（FR-MB-015）＋ 有 `session_identity` 合同（FR-MB-016）＋ `continuation_readonly_evidence: true`（FR-MB-004.3） | `validate_registry_policy` 的 `stateful_roles` 段 |
| 派发与运行时比对 | 请求 form ∈ backend 声明（MB-GRILL-029）＋ **任何显式 continuation 都要求 canonical `session_identity` 合同**（MB-GRILL-033，fail-fast）；`continuation` 注入 adapter；`request.continuation` ↔ `result.session` 机械比对（resume：form+handle 精确匹配；显式 initial：必须返回 initial 身份），一致则 `session.verified = true`，否则 `session_resume_mismatch` | `_check_backend_eligibility` / `dispatch_review(adapter_request)`（continuation 注入点） / `_normalize_result` |

**关键纪律**：`session_resume_mismatch` 属 transport/runtime 状态，按 FR-MB-020 不得被赋三字段、不得进入 finding 生命周期。续接会话"必须被证明，不能被假设"（FR-MB-003.2）——退出码与 adapter 自报都不算证据。

**为什么不声明任何 backend**：目前无 backend 同时具备 resume 证据与 adapter resume 子形态；按 MB-GRILL-020 教训（不得虚构资格），registry 保持不声明、序列保持空过渡态。

> ⚠️ 此段为 §11.13 记录的**中间状态**（v0.13），已被 §11.14 取代：opencode-cli 已声明续接合同并进入 stateful 序列，MB-GRILL-020 已 CLOSED。

**验证**：**207 tests OK**（197 → 203 → 205 → 207；033 补修新增 2 项，均通过负向验证）；`validate-review-routing.py` 6 backends / 1 roles OK；`validate-bindings.py` OK。

### 11.14 第九轮：端到端断链修复 → MB-GRILL-020 CLOSED（2026-09-03）

**断链发现（本地机械验证）**：§11.13 落地后 adapter 已实现 resume，但 registry 无任何 backend 声明 `session_identity`，opencode-cli 也无 `invocation_forms`——按 MB-GRILL-033 新规则，显式 continuation 在派发层 fail-fast（`initial` → "declares no session identity contract"；`resume` → "does not declare the requested invocation form"），**端到端断链**。222 项测试绿仅覆盖适配层，未覆盖"registry 声明 + 派发资格"段——"测试绿 ≠ 闭环"实例。

**修复（v0.14，主审确认 `STATUS: CLOSED`）**：

1. `review-backends.yaml`：opencode-cli 声明 `invocation_forms: [initial, resume]`、`session_identity: {field: session, owner: opencode-review}`（field 为 canonical 常量 `SESSION_IDENTITY_FIELD`）、`continuation_readonly_evidence: true`（证据：`tests/evidence/opencode-resume-readonly-evidence.yaml`）；
2. `routing-policy.yaml`：`stateful_roles.strong-reviewer-stateful.backends: [opencode-cli]`——其续接只读取证已取得（§8 #2 CLOSED），成为**首个满足 FR-MB-001 三项资格**的 stateful 成员；chatgpt-tunnel（会话合同属 transport 层、跨 owner）与 codex-cli（续接只读取证未取得）仍在外；
3. `opencode-review` adapter 续接子形态（并行会话半成品，本轮纳入复核）：resume → `opencode run --session <handle>`、从 NDJSON `sessionID` 提取真实会话、输出 `result["session"]={form,handle}`，字段与 `SESSION_IDENTITY_FIELD` 一致；
4. 测试：`InvocationFormsRegistryContractTests` helper 改为从"无续接声明"的干净基底构造（避免 checked-in 完整声明掩盖缺字段用例），registry 层与 stateful 资格检查解耦；fixture 与 checked-in 对齐。

**主审核查结论**：registry 声明与 adapter 实现配套、FR-MB-001 三项资格全部机械满足、opencode-cli 未进入 Router 单跳链（分层保持）、无越权、无新 finding。

**MB-GRILL-020 → `CLOSED`。至此 MB-GRILL-001~033 全部闭环。**

| finding | 状态 |
|---|---|
| MB-GRILL-001~018 | 早期轮次处置（v0.1~v0.4） |
| MB-GRILL-019 / 020 / 021 / 027 / 028 | CLOSED |
| MB-GRILL-022~026 / 029~033 | CLOSED |
| **全部** | **CLOSED** |

**剩余（非 finding，VERIFICATION_REQUIRED / 待裁决）**：codex-cli 续接形态只读开关有效性（§8 #1，需非嵌套沙箱行为正负对照）；chatgpt-tunnel 会话合同的 runtime 声明方式（跨 owner：transport 属 grilling skill、registry 属 runtime，待用户裁决后它方可具备 stateful 资格）；分支并入 develop 方式。

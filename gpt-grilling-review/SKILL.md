---
name: gpt-grilling-review
description: Use when 用户要求 ChatGPT 审核指定文件/指定仓库、让 ChatGPT 自行读取本地代码找问题并给修改意见、弱模型按意见修改后需要送回复审，或需要对审核发现做裁决处置。触发词：ChatGPT 文件审核、指定文件审核、gpt grilling、修改后复审、裁决。
---

# ChatGPT 文件 Grilling 审核

## 目标

角色反转的审核闭环：**ChatGPT（强模型）是主审与最终关闭人**，**本地 agent（弱模型）是执行者与核对者**，**用户是最终裁决人**。依据 [classification-policy.md](references/classification-policy.md) 的人工判断升级规则，对核对属实的风险点做三类分流，**仅 HUMAN_DECISION_REQUIRED 逐条裁决**。修复采用三个独立字段（SEVERITY / CLASSIFICATION / CHANGE_RISK）：**凡 ChatGPT 提出的 finding 修改了生产代码或测试语义，弱模型不得自行 CLOSED，必须由 ChatGPT 针对性复查（原 finding + 真实 diff + 授权范围 + 验证结果）返回 CLOSED 才闭环**；纯拼写/格式可本地验证关闭。

## 角色分工

| 角色 | 职责 | 禁止 |
|---|---|---|
| ChatGPT（强模型/主审） | 首审输出 finding + SEVERITY + 建议分流；针对性复查并给出 STATUS | 不得只凭弱模型摘要 CLOSED |
| 本地 agent（弱模型，执行+核对） | 送审、核对引用、按规则分流、执行获批修改、按风险分级送复查 | 不得机械接受意见；不得静默重分类 F/V/H 或降级 CHANGE_RISK；不得自行 CLOSED 生产代码/测试语义修改；不得未经授权修改；不得覆盖用户已有变更 |
| 用户（裁决人） | 对 HUMAN_DECISION_REQUIRED 逐条裁决；对 FINDING 批量授权；对 VERIFICATION_REQUIRED 确认取证方式 | — |

**违反规则的字面意思就是违反规则的精神。**

## 三个独立字段

每个 finding 有三个独立字段，不得混用：

- **SEVERITY**（首审 ChatGPT 输出）：finding 本身的严重度，HIGH/MEDIUM/LOW。仅表示严重度，不决定处置路径
- **CLASSIFICATION**（问题分流，处置轴一）：FINDING / VERIFICATION_REQUIRED / HUMAN_DECISION_REQUIRED
- **CHANGE_RISK**（修改方案确定后评估，处置轴二）：LOW/MEDIUM/HIGH，回答"这个具体修改有多大复查风险"

CLASSIFICATION 与 CHANGE_RISK 是两个处置轴；SEVERITY 仅表示严重度。**HUMAN_DECISION_REQUIRED 不是第四级 CHANGE_RISK。** 一个 H 项经人工选择后，仍需独立评估 CHANGE_RISK（H+LOW / H+MEDIUM / H+HIGH 都可能）。

**SEVERITY 不得直接决定 CHANGE_RISK**：高严重度崩溃可能是低风险修复；低严重度兼容性瑕疵可能是高风险架构迁移。

### CHANGE_RISK 下限（弱模型可升级，不得无理由突破下限降级）

- 至少 **HIGH**：公共 API、用户可见行为、并发、安全/权限、持久化/文件格式、兼容性、数据迁移
- 至少 **MEDIUM**：状态机、异步逻辑、错误语义、fail-open/fail-closed、公共函数行为、测试期望变化
- 同时命中多个下限时，取最高等级
- 突破下限降级须送 ChatGPT 复核（见「弱模型重分类复核」）

## finding 生命周期（轻量）

每个 finding 有两个独立字段：

- **lifecycle**：`OPEN` / `DISPUTED` / `CLOSED` / `INVALIDATED`
- **disposition**：`NONE`（未处置）/ `TODO` / `LATER` / `ACCEPTED_RISK`（用户不采纳）/ `VERIFICATION_PENDING`（待取证）

| lifecycle | 含义 |
|---|---|
| OPEN | 已发现待处置 |
| DISPUTED | 弱模型对 ChatGPT finding 提出反证，待 ChatGPT 复核 |
| CLOSED | 满足 CLOSED 判据（见下） |
| INVALIDATED | 经 DISPUTED 复核确认 finding 不成立 |

disposition 不改变 lifecycle：TODO/LATER/ACCEPTED_RISK/VERIFICATION_PENDING 项 lifecycle 仍为 OPEN（已登记处置意向或待取证，但未闭环），均不进入本轮主动处置循环；其中 VERIFICATION_PENDING 在新证据到达前挂起，取得证据后按「VERIFICATION_REQUIRED 转换」恢复处理。`REOPEN` 是复查结果而非 lifecycle 状态：收到 REOPEN 后原 finding lifecycle 置回/保持 `OPEN`，保留原 finding ID（原问题没修好仍是原 finding，不是新风险点）；修复引入的新问题创建新 finding ID，记录 `introduced_by=<原 finding ID>`。

**review processing complete ≠ all findings closed**：状态机收尾时必须区分"已处置"与"已 CLOSED"，最终报告须列明各 finding 的 lifecycle + disposition。

### CLOSED 判据（必须同时满足）

1. 原问题被真正解决
2. 修改未越权（在用户授权范围/裁决方案内）
3. 没有修复引入的新客观问题
4. 所需证据充分

任何一项不满足都不得 CLOSED。

## 输入

收到外部 review 后，先按 [receiving-feedback.md](references/receiving-feedback.md) 验证事实再采纳，禁止因措辞权威而盲目修改。


开始前必须确认（缺失则向用户提问，不得猜测）：

1. **仓库名**：按 [transport.md](references/transport.md) 的仓库命名规则；送审前 `git worktree list` 确认存在
2. **文件清单**：用户指定的待审文件（仓库内相对路径）；用户只给了目录或分支时，先送审"列范围"请求，拿到 ChatGPT 发现的文件清单后与用户确认
3. **可选权威依据**：需求/设计/规范文档路径
4. **修改前 baseline**（修复阶段必记）：当前 HEAD、`git status --short`、已有 dirty diff、相关测试命令及既有失败。**禁止修改/覆盖用户已有变更**

## 循环状态机

1. 确认输入（仓库名 + 文件清单）
2. 首次送审（见「首次送审模板」），拿到 ChatGPT 的 finding 清单（含 SEVERITY + 建议分流 + reviewed/missing 覆盖）
3. **本地核对**：对 ChatGPT 引用的每个文件、行号、结论，用 Read/Grep 当场验证
   - 引用属实 → 进入分流
   - 引用有误/结论不成立 → 走「DISPUTED 路径」，不得直接丢弃
4. **风险分流**：依据「风险分流规则」+ ChatGPT 建议分流，归入 FINDING / VERIFICATION_REQUIRED / HUMAN_DECISION_REQUIRED；弱模型重分类须复核
5. 按分流路径处置：
   - FINDING → 走「批量 finding 处置」
   - VERIFICATION_REQUIRED → 登记 VERIFICATION_PENDING，按「VERIFICATION_REQUIRED 转换」处置
   - HUMAN_DECISION_REQUIRED → 走「逐条裁决」（HARD-GATE 适用）
6. 任何「立即修复」执行后，评估 CHANGE_RISK，按「修复后复查（按风险分级）」处置；HUMAN_DECISION_REQUIRED 项先人工定方案再实现
7. 还有本轮可主动处置的 finding → 回步骤 5 对应路径；仅剩 TODO/LATER/ACCEPTED_RISK/VERIFICATION_PENDING → 输出最终报告（列明各 finding 的 lifecycle + disposition），询问是否扩大范围/收尾（不得自动继续）

<HARD-GATE>
- 仅对 HUMAN_DECISION_REQUIRED 类逐条裁决：每轮只处理一个、只提一个裁决问题；用户未回答不得继续下一个
- 原子单位是"独立的人类决策点"，不是 finding 数量：若多个 finding 由同一产品决策控制，可作为一个决策组一次裁决，但须说明依赖关系（"此决定影响另外 N 个已发现事项，后续不会要求同时裁决"）
- 不得提前列出后续 HUMAN_DECISION_REQUIRED 清单让用户批量决定
- FINDING / VERIFICATION_REQUIRED 不受逐条裁决约束
</HARD-GATE>

## 风险分流规则

分流权威依据：[classification-policy.md](references/classification-policy.md)。**不得把可客观判定的问题升级为人工决策。**

### FINDING（可以客观判定，应修复）
能根据代码、测试或明确规格证明的问题：明确逻辑错误、崩溃、越界、竞态、资源泄漏、与明确规格直接冲突、明确缺少错误处理、明确违反架构规则、测试能稳定证明的问题。

- 正确行为明确但缺测试 → 仍归 FINDING，直接指出应补什么测试；但"缺测试"与"代码有 bug"是不同 finding，不得混为一谈

### VERIFICATION_REQUIRED（行为明确，缺运行证据）
**正确行为明确，只需真实环境证明实现是否达到该行为** → VERIFICATION_REQUIRED（缺事实证据=V）。需 CI、真机、基准、真实语料、GUI 等证据。

### HUMAN_DECISION_REQUIRED（正确行为需人决策）
**真实环境暴露的是"应该选择哪种行为/阈值/策略"，而规格没有答案** → HUMAN_DECISION_REQUIRED（缺正确行为定义=H）。

**优先规则**：HUMAN_DECISION_REQUIRED 列举的场景（兼容性/公共 API/安全/fail-open/fail-closed 等）**仅在"正确行为尚未由权威规格确定"时成立**。若明确规格已定行为（如规格写"鉴权失败必须 fail-closed"），即使涉及安全/fail-closed，仍按 FINDING 处理。

### 分流纪律
- 不要因"可能有问题"就升级为人工决策；能证明的直接归 FINDING
- 不要把个人编码偏好升级为人工决策
- 不要因测试缺失就自动要求人工判断；正确行为明确的，直接指出该补什么测试（归 FINDING）
- 缺事实证据 → V；缺正确行为定义 → H
- 优先减少误报

### 弱模型重分类复核
弱模型若改变 ChatGPT 建议的 CLASSIFICATION（任何 F/V/H 重分类），**不得静默改分流**，须把反证送 ChatGPT targeted reconsideration。CHANGE_RISK 突破下限降级同样须复核。反向升级（如 F→H）须说明理由。最简单可靠的执行：**任何 F/V/H 重分类均须 ChatGPT 复核**（例如 ChatGPT 判定 FINDING，弱模型不得改成 VERIFICATION_REQUIRED 把应修复问题变成无限待验证）。

## DISPUTED 路径

弱模型不得静默否定 ChatGPT finding（"引用有误"不能让问题直接消失）：

1. 弱模型发现 ChatGPT 引用/结论不成立 → 标记 `DISPUTED`，附本地反证（实际代码/行号/规格）
2. 送 ChatGPT 复核反证（同 conversation_id）
3. ChatGPT 确认不成立 → `INVALIDATED`；确认成立 → 恢复原分流继续处置

## VERIFICATION_REQUIRED 转换

取得证据后（不新增 lifecycle 状态）：
- 证明实现违反明确行为 → 转 FINDING（lifecycle 仍 OPEN，CLASSIFICATION 改为 FINDING）
- 证明实现符合明确行为 → CLOSED，记录 `resolution=NO_CHANGE`
- 证据仍不足 → 保持 VERIFICATION_PENDING

## 首次送审模板

调用契约遵循 [transport.md](references/transport.md)。content：

```
请使用你可用的工具，自行读取仓库 "<repo>" 中的以下文件（不要依赖我提供内容）：
<文件清单，每行一个相对路径>

逐文件审核：正确性、边界处理、错误传播、与同目录其他代码的一致性；
如有提供需求/设计文档（<文档路径>），同时审核实现与文档的一致性。

对每个 finding 输出：finding ID、SEVERITY(HIGH/MEDIUM/LOW)、问题描述、位置(文件:行号)、修改建议、建议分流(FINDING/VERIFICATION_REQUIRED/HUMAN_DECISION_REQUIRED)。

最后必须输出文件覆盖清单：
REVIEWED: <已读文件>
UNREADABLE: <未能读取的文件>

只要有指定文件未读到，不得宣称范围审核完成。如果无法读取任何指定文件，直接回复一行：无法读取指定文件。
```

## 修复后复查（按风险分级）

弱模型负责实现已确认的修复方案，**不负责宣告问题已关闭**。修改完成后必须提供：修改摘要、涉及文件、对应测试/验证结果、仍存在的不确定性、修改前 baseline 对比。

### 关闭权规则（堵自闭环）

- **凡 ChatGPT 提出的 finding，修改了生产代码或测试语义，弱模型不得自行 CLOSED**，必须由 ChatGPT 针对性复查返回 CLOSED
- LOW 可把多个 finding 合并成一次轻量 ChatGPT targeted review，以控制成本
- 仅纯非行为修改（确定性拼写/格式修复）允许本地验证直接 CLOSED
- HUMAN_DECISION_REQUIRED 项先人工定方案再实现，不得弱模型直接修掉

### 风险分级与复查要求

| CHANGE_RISK | 复查要求 | 关闭条件 |
|---|---|---|
| LOW | 测试/静态检查通过；多个可合并一次轻量 ChatGPT targeted review | ChatGPT 返回 CLOSED（生产代码/测试语义修改）；纯拼写/格式可本地 CLOSED |
| MEDIUM | ChatGPT 针对性复查（真实 diff + 当前源码） | ChatGPT 返回 CLOSED |
| HIGH | ChatGPT 针对性复查 + 测试/真实运行证据 + baseline 对比 | ChatGPT 返回 CLOSED 且证据齐备 |

CHANGE_RISK 按「三个独立字段」中的下限评估，弱模型不得无理由突破下限降级。

### ChatGPT 针对性复查模板（同 conversation_id 续发）

不强求重新全仓审核。给 ChatGPT 输入：**finding ID、原 finding、实际 diff、当前相关源码、授权范围、人工裁决记录、baseline、测试命令与结果**。**MEDIUM/HIGH 必须提供真实 diff + 当前源码，禁止用"文件清单+修改摘要"替代**。

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
实际 diff: <真实 diff>
当前相关源码: <修改后相关代码>
验证结果: <测试命令/退出码/日志>

第一行必须且只能是以下状态之一：
STATUS: CLOSED
STATUS: REOPEN
STATUS: VERIFICATION_REQUIRED
STATUS: HUMAN_DECISION_REQUIRED

第二行起：若不是 CLOSED，说明最小原因和下一步。REOPEN 须指明是原问题未解决还是引入新问题（新问题须建新 finding ID + introduced_by）。
```

### 复查结果处置

- `CLOSED`：满足 CLOSED 判据，标记闭环
- `REOPEN`：原问题未解决 → 原 finding lifecycle 置回/保持 OPEN、保留原 ID 回步骤 3；引入新问题 → 新 finding ID + introduced_by 回步骤 3
- `VERIFICATION_REQUIRED`：登记 VERIFICATION_PENDING，补证据后再复查
- `HUMAN_DECISION_REQUIRED`：升级为逐条裁决（HARD-GATE 适用）

## 风险点展示格式（MUST）

展示任何风险点时，必须给出**能够独立理解该问题的最小完整语义上下文**：优先完整函数/方法；类级问题给完整相关成员；配置/非代码文件（YAML/JSON/SQL/Markdown 等）给完整相关块。问题语句用**对应语言的注释语法**标注警告（如 Python `# ⚠️`、SQL `-- ⚠️`），并明确这是展示标注、不是源码内容。代码块后只补 1-3 条要点。禁止：把代码打散配大段文字、行尾长注释、用宽表格替代代码。

展示内容固定四段：**ChatGPT 意见**（含 SEVERITY 与建议分流）→ **本地核对结论**（引用属实/有误，逐条）→ **分流归类**（F/V/H + 一句理由）→ **建议处置**。

- FINDING 批量展示时，多条可紧凑列出，每条仍含 ID+位置+问题+建议修复
- HUMAN_DECISION_REQUIRED 单条展示时，在「建议处置」后接「逐条裁决提问」

## 批量 finding 处置（FINDING 类）

- 把所有 FINDING 类风险点合并展示（遵循「风险点展示格式」）
- 一次性向用户确认处置（不逐条提问）：
  - 全部立即修复
  - 全部加入 TODO
  - 按子集拆分（用户指定哪几条立即修复、哪几条加入 TODO）
- 用户授权后执行修复；未经授权不得改任何文件
- 修复完成后评估 CHANGE_RISK，按「修复后复查（按风险分级）」处置

## 逐条裁决提问要求（仅 HUMAN_DECISION_REQUIRED）

- 只含当前一个 HUMAN_DECISION_REQUIRED 风险点；2-4 个互斥选项编号；标推荐项；每项一句影响说明
- 提问前必须先给技术分析 + 可选方案（A/B，必要时 C）及优缺点，对齐 [classification-policy.md](references/classification-policy.md) 的 HUMAN_DECISION_REQUIRED 格式
- 推荐项不固定：修复导致错误结论且任务允许改 → 推荐立即修复；只读审核任务 → 推荐 TODO；低优先级 → 推荐 LATER
- 用户回答含糊 → 重新提问，不得猜测裁决
- 选项：`加入 TODO` / `加入 LATER` / `立即修复` / `不采纳`（不采纳=ACCEPTED_RISK，记录理由）

## 修改边界

- 未经用户授权，不得修改任何文件；不得顺手修复相邻问题
- FINDING 类经一次性授权后，只改授权范围内事项，不夹带重构；改后重新读取文件核对
- HUMAN_DECISION_REQUIRED 类经逐条裁决后，只改当前获批事项
- 修改前必须记录 baseline（HEAD/dirty tree/测试基线/已知失败）；**禁止修改/覆盖用户已有变更**
- TODO 项不得立即改；LATER 项不得继续当阻塞项
- VERIFICATION_REQUIRED 项在取得证据前不得擅自修复

## 基线失败（无本技能时的真实错误）

| 真实失败 | 技能对策 |
|---|---|
| 机械接受 ChatGPT 意见（行号/引用错误也被照单执行） | 步骤 3 强制本地核对 |
| 弱模型修歪→自判低风险→自改测试→测试绿→自宣布 CLOSED | 关闭权规则：生产代码/测试语义修改必须 ChatGPT CLOSED |
| 把可客观判定的 FINDING 升级为逐条人工裁决 | 风险分流：FINDING 批量处置，仅 HUMAN_DECISION_REQUIRED 逐条裁决 |
| 弱模型静默重分类 F/V/H 或降级 CHANGE_RISK | 重分类复核（任何 F/V/H 重分类须 ChatGPT 复核）+ DISPUTED 路径 |
| 弱模型声称"引用有误"让 finding 消失 | DISPUTED 路径：反证送 ChatGPT 复核 |
| 中高风险只给摘要不给 diff | MEDIUM/HIGH 必须真实 diff + 当前源码 |
| 改完不复审就宣称闭环 | 风险分级复查 + CLOSED 判据 |
| 修后测试红，无法区分旧失败还是新回归 | 修改前 baseline |
| 一次倒出全部 HUMAN_DECISION_REQUIRED 问题 | HARD-GATE 仅对此类，原子单位=独立决策点 |
| 送审不指定文件清单/部分文件未读却宣称完成 | 输入必须含文件清单 + reviewed/missing 覆盖 |
| 修改时夹带无关重构 | 修改边界：只改获批事项 |
| 因测试缺失或只缺运行证据就要求人工决策 | 缺测试归 FINDING；缺证据归 VERIFICATION_REQUIRED |

## 红线 - 出现即停下纠正

| 借口 | 现实 |
|---|---|
| "ChatGPT 说的肯定对，直接照改" | 引用可能错；先本地核对，再分流（有误走 DISPUTED） |
| "低风险，测试过了我自己关掉" | 生产代码/测试语义修改必须 ChatGPT CLOSED，弱模型不得自行 CLOSED |
| "每个问题都得问用户才稳妥" | 能客观判定的归 FINDING 批量处置，只有真正决策项才逐条裁决 |
| "问题都差不多，一起问了效率高" | HUMAN_DECISION_REQUIRED 原子单位=独立决策点，一次一个 |
| "这个 H 其实是 FINDING，我直接重分类" | 重分类须送 ChatGPT 复核，不得静默改分流 |
| "引用有误，这 finding 作废" | 走 DISPUTED，反证送 ChatGPT，不得直接丢弃 |
| "中风险给个摘要就行" | MEDIUM/HIGH 必须真实 diff + 当前源码 |
| "修改 obvious 不用等授权" | 未经授权不得改任何文件 |
| "复审太慢，改得对就行" | 必须满足 CLOSED 判据四项 |
| "顺手把旁边的问题也修了" | 夹带 = 边界失控，新问题走新分流 |
| "缺测试/缺证据，让用户定夺吧" | 缺测试归 FINDING 指出补测试；缺证据归 VERIFICATION_REQUIRED |

## 禁止事项

- 弱模型自行 CLOSED 生产代码/测试语义修改（必须 ChatGPT 针对性复查返回 CLOSED）
- 把可客观判定的问题（FINDING）升级为 HUMAN_DECISION_REQUIRED 逐条裁决
- 因测试缺失或只缺运行证据就要求人工决策（应归 FINDING 指出补测试，或 VERIFICATION_REQUIRED）
- 静默重分类 F/V/H 或突破 CHANGE_RISK 下限降级（任何 F/V/H 重分类须送 ChatGPT 复核）
- 静默否定 ChatGPT finding（须走 DISPUTED）
- HUMAN_DECISION_REQUIRED 项未经人工定方案就由弱模型直接修掉
- 中高风险复查用"文件清单+摘要"替代真实 diff
- 复查模板不提供授权范围/裁决记录（导致"未授权"无法判断）
- 一次列出全部 HUMAN_DECISION_REQUIRED 风险点；一个提问捆绑多个独立决策
- HUMAN_DECISION_REQUIRED 不给技术分析和可选方案，只写"请人工确认"
- 未核对 ChatGPT 引用就展示或执行其意见
- 未指定文件清单就送审；把代码粘贴进 content（ChatGPT 自行读取）；部分文件未读却宣称范围审核完成
- 修改后不送复查就宣称 finding CLOSED；把非 CLOSED 回复当作 CLOSED；TODO/LATER/ACCEPTED_RISK 当作 CLOSED
- 修改前不记 baseline；修改/覆盖用户已有变更
- 复审发现的新问题不经过分流直接修
- 复审 content 提及通道/工具实现机制（保持业务视角）

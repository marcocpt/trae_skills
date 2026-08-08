# dd-ask-chatgpt MCP 服务器设计

> 本文档经 ChatGPT 两轮审核后修订。第一轮：方向 PASS，3 个 must-fix。第二轮：**PASS_WITH_MUST_FIX，约 85% implementation-ready**，剩余 5 项 must-fix（工具/协议正确性 + 部署可行性）已在本版全部落实。第三轮以「ChatGPT 满意」为迭代出口。

## 目标

把「查询 ChatGPT」从 `dd-xctest-newbie-grilling-review` 技能内嵌的浏览器编排逻辑中提取出来，做成一个独立的 MCP 服务器，供 Trae、opencode、WorkBuddy、Claude Code、Cursor 等所有支持 MCP 标准的应用跨 app 复用。

## 背景与问题

当前「查询 ChatGPT」逻辑内嵌在 `dd-xctest-newbie-grilling-review/references/risk-review-and-ask.md`，依赖 Trae 的 `integrated_browser`（内置浏览器）MCP 工具。这套逻辑已验证可用，但：

- 被某个技能内嵌，其他技能/项目无法直接复用。
- 依赖宿主 app 私有的内置浏览器 MCP，无法跨 app 复用。
- 因此需要一个与宿主无关的独立浏览器驱动方式。

## 部署前置条件（Deployment Precondition）

> **必须实现前裁决，不得等代码写完再处理。**

本 server 的本质是 `Playwright → ChatGPT 网页 → 自动发送 → 自动读取 Output → 程序化返回给另一个 App`。OpenAI 当前公开的个人 Terms of Use 明确列出不得自动或程序化提取数据或 Output 的限制。不同账号、区域或商业协议适用条件可能不同，不得直接假定允许。

```
dd-ask-chatgpt 只有在目标 ChatGPT 账号所适用的 OpenAI 条款、合同或明确授权
允许自动化网页交互及程序化读取 Output 时才能部署使用。
若适用条款不允许，则不得通过网页自动化方式部署，
应改用获准的官方程序化接口或取得相应授权。
```

由于本设计「不调用 ChatGPT 后端 API」（见 Out of Scope），若适用协议确实禁止 Web 自动提取，则 Out of Scope 与部署要求会形成硬冲突。此项在进入正式实现前必须裁决。

## 决策

| 项 | 决策 |
| --- | --- |
| 载体 | MCP 服务器（跨 app 通用） |
| 语言/栈 | TypeScript：`@modelcontextprotocol/server` v2 + `playwright` |
| 协议基准 | MCP 2026-07-28（stateless protocol） |
| 浏览器 | Playwright 独立浏览器实例，持久化 profile 自维护 ChatGPT 登录态 |
| 工具 1 | `dd_chatgpt_ask({ message, conversationId?, timeoutMs? })` — 有 conversationId 继续旧会话，无则新建并返回新 conversationId |
| 工具 2 | `dd_chatgpt_new_conversation({})` — 显式先建会话句柄，返回稳定 `conversationId` |
| 会话保持 | 无「当前 client 默认会话」概念（MCP stateless）；会话状态一律通过显式 `conversationId` 传递，由调用方保存 |
| 单例宿主 | **V1 冻结为唯一后端 = localhost Streamable HTTP MCP server**；stdio 仅为协议代理 |
| 并发模型 | 同一 conversation 内严格串行（`Map<ConversationId, Mutex>`）；可选全局信号量 `DD_CHATGPT_MAX_CONCURRENT_ASKS` |
| 行为 | 发送 `message`（不注入 `%%CHATGPT%%` 前缀，见配置项）→ 状态机等待生成完成 → 按 TurnLocator 读取本次回复 → 返回结构化结果 |
| 登录 | 首次运行需在 Playwright 浏览器中手动登录一次 ChatGPT，登录态持久化到独立 profile，后续自动复用 |
| 消息前缀 | `%%CHATGPT%%` 仅作旧自动化入口的触发 sentinel，**不是 MCP 协议的一部分**；通过 server 配置 `DD_CHATGPT_MESSAGE_PREFIX` 控制，默认空字符串 |

## 架构（V1 冻结：单例 Streamable HTTP 后端）

```
┌─ Trae         HTTP MCP ┐
├─ Cursor       HTTP MCP ┤
├─ Claude Code  HTTP MCP ┤──> 127.0.0.1:<port>/mcp ──> dd-ask-chatgpt singleton daemon
├─ WorkBuddy    HTTP MCP ┤                             │
├─ opencode     HTTP MCP ┘                             ├── Request Manager       并发/串行调度、Cancellation
│                                                       ├── Conversation Manager  conversationId → URL/Page
│                                                       └── Playwright ──> 独立 Chromium 实例（owned profile）
│
stdio MCP client ──> thin stdio adapter ──> 同一个 localhost MCP endpoint
```

**V1 只实现一套架构，不留「首选/兜底」二选一：**

1. **唯一后端**：localhost Streamable HTTP MCP server（独立 daemon 进程）。它独占 Playwright 与 owned profile，持有全部 conversation state。
2. **stdio adapter 只是协议代理**：它不拥有浏览器、不拥有 conversation state；把 stdio JSON-RPC 转发到同一个 localhost MCP endpoint。
3. **实例发现与单例化**：`~/.dd-ask-chatgpt/state/backend.json` 记录 `{ pid, port, instanceId, startedAt }`。adapter/启动器据此发现已运行的 backend；backend 未启动时由启动器拉起；两个启动器同时启动时用 `locks/browser.lock` 决定 winner。

**本地 HTTP 安全策略（硬合同）：**

```
BIND = 127.0.0.1 only（0.0.0.0 默认禁止）
Origin validation = MUST（防 DNS rebinding）
authentication = required（启动时生成随机 token，保存为仅当前用户可读的文件）
```

**核心不变项：MCP transport 生命周期 ≠ Chromium 生命周期。** 多个 App 的 MCP client / adapter 进程不得各自拉起一个 Chromium 去争用同一个 `userDataDir`；Playwright `launchPersistentContext(userDataDir)` 明确要求同一 User Data Directory 不能同时启动多个浏览器实例。

## 目录结构

```
~/.dd-ask-chatgpt/
  profile/          # Playwright 持久化 profile（登录态；仅由 dd-ask-chatgpt 管理，禁止指向日常 Chrome profile）
  state/
    backend.json         # { pid, port, instanceId, startedAt } 单例后端发现
    conversations.json   # conversationId → { conversationUrl, pageRef? } 映射（URL 持久，Page 临时 cache）
    auth.token           # 随机认证 token（仅当前用户可读）
  locks/
    browser.lock         # Chromium/profile 互斥锁
  logs/                  # 运行日志（stderr）

dd-ask-chatgpt-mcp/      # 仓库
  package.json
  tsconfig.json
  src/
    index.ts          # MCP server 入口，注册两个工具（Streamable HTTP backend）
    requestManager.ts # 并发/串行调度（per-conversation mutex）、Cancellation
    conversationManager.ts  # conversationId 句柄管理（URL 持久 / Page 临时 cache 分离）
    chatgpt.ts        # Playwright 浏览器控制与状态机核心逻辑
    stdioAdapter.ts   # 薄 stdio 协议代理 → localhost MCP endpoint（不含浏览器/会话状态）
  README.md           # 安装 / 配置 / 各 app 挂载说明
```

## 工具契约

MCP 2026-07-28 是 **stateless protocol**：跨请求需保持的状态必须通过显式 identifier 每次传递；stdio process/connection 不能被当作 conversation 或 session；`clientInfo` 是 self-reported 展示/日志信息，server 不得依赖它改变行为或做安全判断。因此本 server **不存在「当前 MCP client 的默认会话」**。

### `dd_chatgpt_ask`

输入（JSON 对象）：
- `message: string` — 要发送给 ChatGPT 的内容。
- `conversationId?: string` — 精确继续指定会话。
- `timeoutMs?: number` — 可选的完成等待超时（默认 `60000ms`）。

语义：
- `conversationId` 给定 → 恢复/定位该 conversation → 发送。
- `conversationId` 未给（`null`/缺省）→ 创建新 ChatGPT conversation → 发送 → 返回新的 `conversationId`。
- 不再有 `newConversation` 参数（新会话由「缺省 conversationId」或显式 `new_conversation()` 表达）。

约束：`message` 必填；`conversationId` 与 `timeoutMs` 可选。

行为：
1. 输入 `message`（发送内容为 message 原文，不注入 `%%CHATGPT%%`；如需前缀由配置 `DD_CHATGPT_MESSAGE_PREFIX` 提供）。
2. 发送。
3. 按状态机等待生成完成（见「完成状态机」），超时则返回 `status: "incomplete"` 并尽力读取已生成部分。
4. 按 **TurnLocator** 读取本次回复（见「response correlation」），不依赖 `last()`。

返回（outputSchema 结构化）：
```
{ "status": "complete" | "incomplete",
  "content": "...",
  "operationId": "op_xxx",
  "conversationId": "conv_xxx",
  "conversationUrl": string | null }
```

`status: "incomplete"` 在 V1 明确只代表 `ASK_TIMEOUT`，语义干净。

失败：MCP tool result 设 `isError: true`，返回结构化错误 `{ code, message, retryable }`（见「错误处理」）。

### `dd_chatgpt_new_conversation`

输入：`{}`（无参数）。

行为：仅创建空会话句柄并返回稳定 `conversationId`（先建立 handle → 后续 `ask({ conversationId })`）。此时 `conversationUrl: null`（尚未真正发消息），首次发送后才回填。`conversationId` 是 MCP server 定义的稳定引用，**URL 只是外部元数据，不是主键**。

返回：
```
{ "conversationId": "conv_xxx", "conversationUrl": string | null }
```

## conversation 生命周期（不自动换绑）

**冻结原则：`conversationId` 一旦签发，绝不自动换绑到其他 ChatGPT conversation；只有显式 `new_conversation()` 才创建新的 conversationId。**

- `conversationId` 与 ChatGPT conversation 的关系持久化于 `state/conversations.json`，其中 URL 持久、Page 只是临时 cache（服务器重启、tab 关闭、内存回收均不影响 conversation identity）。
- Page 被关闭 → `conversationId` 仍不变 → 查 URL → 重新打开该 URL → 验证会话可读 → 继续该 conversation。
- 唯一可重开空页的特例：`new_conversation()` 后尚未发送首条消息（`conversationUrl == null`）时 Page 意外关闭，可重新准备空页面。
- 其他失败（URL 被删除、账号变化、URL 无权访问、会话无法加载）→ 返回 `CONVERSATION_NOT_FOUND` 或 `CONVERSATION_RECOVERY_FAILED`，**绝不静默创建新 conversation**（否则如 XCTest 审核 `A→B→C` 中 B 后 Page 关闭，C 会丢失 A/B 上下文而 Agent 不知情）。

## response correlation（TurnLocator）

在「同 conversation 严格串行」后，并发串回复的 race 已基本消除，但「DOM 一直渲染全部 assistant messages」不应成为正式 contract。抽象 `TurnLocator`：

```
优先：识别本次新增的 user turn → 验证内容/fingerprint 与本次发送一致 → 定位其后的 assistant turn
fallback：count()/nth() 计数定位（const before = assistantMessages.count(); 等待 count>=before+1; 读 nth(before)）
```

`requestId → 本次 user turn → 其后 assistant turn` 比 `requestId → assistant DOM count N` 更稳定。动态 UI 读取优先用 Playwright Locator 的 retry/auto-wait，避免手写固定 sleep。

## 完成状态机

`「停止回答」按钮消失` 只是完成判据之一，不作为唯一依据。采用状态机：

```
SENT → WAIT_NEW_ASSISTANT_TURN → GENERATING → WAIT_STABLE → COMPLETE
```

完成条件至少组合：
1. 已观察到本次新增 assistant turn（TurnLocator 命中）。
2. streaming / stop indicator 不存在。
3. 输入框恢复可操作。
4. assistant 文本连续约 500–1000ms 不再变化。

超时：返回 `status: "incomplete"`（仍属成功的 tool result，带已生成部分），不抛异常。完全无法完成（如 DOM 无法识别）才走 `isError: true`。

## 并发模型

- **同一 conversation 内严格串行**：`Map<ConversationId, Mutex>`，避免两个 prompt 同时塞进同一 ChatGPT 会话。
- **不同 conversation 可并行**：互不阻塞。
- 可选全局信号量 `DD_CHATGPT_MAX_CONCURRENT_ASKS` 限制整体并发。

## Cancellation

区分「业务执行失败」与「客户端取消」两种截然不同的语义：

```
业务执行失败 → isError: true → LOGIN_REQUIRED / DOM_CHANGED / SEND_FAILED ...
客户端取消  → 不返回 tool result → 中止工作 → finally 释放 mutex → 日志记录 status=cancelled
```

- MCP 取消行为是 transport-specific：stdio → `notifications/cancelled`；Streamable HTTP → client 关闭该请求的 SSE response stream；server 收到取消后应尽快停止处理、释放资源，被取消后不得继续向该请求发送消息。
- `CANCELLED` 保留为**内部 OperationStatus/日志/metrics 状态**，但不作为 `{ isError: true, code: "CANCELLED" }` 外部 tool 错误。
- stdio adapter 职责：收到 `notifications/cancelled` → 找到对应 backend HTTP request → `AbortController.abort()` → 关闭 backend request/response stream。否则 thin adapter 会把 MCP cancellation 丢掉。

## 错误处理（机器可恢复）

定义稳定错误码，供 Agent 采取恢复动作。错误码示例：

```
LOGIN_REQUIRED / PROFILE_LOCKED / BROWSER_LAUNCH_FAILED / PAGE_NOT_AVAILABLE /
CONVERSATION_NOT_FOUND / CONVERSATION_RECOVERY_FAILED / SEND_FAILED /
RESPONSE_NOT_FOUND / DOM_CHANGED / NETWORK_ERROR / ASK_TIMEOUT
```

返回：`{ "code": "LOGIN_REQUIRED", "message": "...", "retryable": false }`，并在 tool result 上设 `isError: true`。

失败边界约定：
- 部分答案 + 超时 → 普通成功，`status: "incomplete"`。
- 完全无法完成（未登录、profile 锁、DOM 无法识别、浏览器启动失败）→ `isError: true`。
- conversation 恢复失败 → `CONVERSATION_NOT_FOUND` / `CONVERSATION_RECOVERY_FAILED`，不自动新建。

## outputSchema

为多宿主服务，定义稳定机器契约（`outputSchema` + `structuredContent`），不让客户端解析文本。两工具的 output 见上文工具契约。声明 `outputSchema` 后，server 返回符合该 schema 的结构化数据。工具契约对象（含 `schemaVersion`）随版本演进，但保证向后兼容。

## profile 生命周期

- 目录：`~/.dd-ask-chatgpt/profile/`。
- **单一 owner**：该 profile 只能由 dd-ask-chatgpt 管理，不允许指向用户日常 Chrome profile（Playwright 官方警告不要自动化主用户 profile）。
- **互斥**：通过 `locks/browser.lock` 保证同一时间只有一个进程持有 Chromium/profile。
- **崩溃/重启恢复**：server 或 Chromium 崩溃后，清理遗留锁、识别 stale profile 并重建，不因残留锁永久阻塞；backend 重启后从 `state/conversations.json` 恢复 conversation handle（URL 持久层）。

## 日志

- 记录：`operationId / clientInfo / conversationId / startTime / duration / status / errorCode / URL`。
- **不默认记录完整 prompt / response**（可能含源码、测试代码、内部文档）。
- **stdio 传输时：stdout 只走 MCP JSON-RPC wire，普通日志一律写 stderr**，避免破坏协议（`console.log` 不得用于日志）。
- 日志写入 `~/.dd-ask-chatgpt/logs/`。

## 配置项

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DD_CHATGPT_MESSAGE_PREFIX` | `""` | 发送前附加到 message 的前缀；默认空。旧技能如需 `%%CHATGPT%%` 哨兵在此配置，**不写死在工具契约里** |
| `DD_CHATGPT_PROFILE_DIR` | `~/.dd-ask-chatgpt/profile` | profile 目录 |
| `DD_CHATGPT_ASK_TIMEOUT_MS` | `60000` | 单次 ask 默认超时（ms） |
| `DD_CHATGPT_MAX_CONCURRENT_ASKS` | `1` | 全局并发上限（信号量） |
| `DD_CHATGPT_BIND` | `127.0.0.1` | Streamable HTTP 绑定地址（禁止 0.0.0.0） |

## 验证（验证矩阵）

「两个 MCP client 同时调用」必须作为 Exit Gate，而非增强测试，否则「跨 app」核心目标未被验证。

| 测试 | 必要性 |
| --- | --- |
| 首次登录后重启 server，仍保持登录 | MUST |
| 单 client：`ask({ message })`（无 conversationId）→ 返回非空 + 新 conversationId | MUST |
| 单 client：`ask({ message, conversationId })` 连续 3 次 → conversationId/URL 不变 | MUST |
| `new_conversation()` 后旧 conversation 仍可继续 | MUST |
| 同 conversation 两次并发 ask，不串回复 | MUST |
| **两个 MCP client 同时调用**（并发/串行、同一 conversation 不打架） | **MUST（Exit Gate）** |
| `status: "incomplete"` 超时路径（无 assistant turn） | MUST |
| 用户取消 MCP 请求 → 释放 mutex、日志 cancelled | SHOULD |
| 浏览器进程被 kill 后自动恢复 | SHOULD |
| page 被用户误关后恢复同一 conversation | MUST |
| server 重启后 conversation handle 行为明确（从持久层恢复） | SHOULD |
| `LOGIN_REQUIRED` / `DOM_CHANGED` / `CONVERSATION_NOT_FOUND` 错误路径 | MUST |
| conversationId 精确复用与「绝不自动换绑」校验 | MUST |

## 范围外（Out of Scope）

- 不替换/不删除 `dd-xctest-newbie-grilling-review` 现有的内置浏览器路径；MCP 作为独立可复用的通用能力提供。技能在 MCP 可用时优先调用，内置浏览器作为回退。
- 不支持多账号并行会话（单 profile 单 owner）。
- 不实现 ChatGPT 网页端之外的任何后端 API 调用（与「部署前置条件」构成必须裁决的合规边界）。
- 第一版不实现「cancel 时点击 Stop generation」等增强。

# dd-ask-chatgpt MCP 服务器设计

> 本文档经 ChatGPT 审核后修订。审核结论：方向 PASS，但需先解决 3 个 must-fix 架构问题后再实现（单例浏览器宿主、conversationId + per-conversation 串行、response correlation），并补全结构化契约、状态机、并发模型与 profile 生命周期。

## 目标

把「查询 ChatGPT」从 `dd-xctest-newbie-grilling-review` 技能内嵌的浏览器编排逻辑中提取出来，做成一个独立的 MCP 服务器，供 Trae、opencode、WorkBuddy、Claude Code、Cursor 等所有支持 MCP 标准的应用跨 app 复用。

## 背景与问题

当前「查询 ChatGPT」逻辑内嵌在 `dd-xctest-newbie-grilling-review/references/risk-review-and-ask.md`，依赖 Trae 的 `integrated_browser`（内置浏览器）MCP 工具。这套逻辑已验证可用，但：

- 被某个技能内嵌，其他技能/项目无法直接复用。
- 依赖宿主 app 私有的内置浏览器 MCP，无法跨 app 复用。
- 因此需要一个与宿主无关的独立浏览器驱动方式。

## 决策

| 项 | 决策 |
| --- | --- |
| 载体 | MCP 服务器（跨 app 通用） |
| 语言/栈 | TypeScript：`@modelcontextprotocol/sdk` + `playwright` |
| 浏览器 | Playwright 独立浏览器实例，持久化 profile 自维护 ChatGPT 登录态 |
| 工具 1 | `dd_chatgpt_ask({ message, conversationId?, newConversation?, timeoutMs? })` — 显式定位会话，可选新建 |
| 工具 2 | `dd_chatgpt_new_conversation()` — 显式新建一个会话，返回稳定 `conversationId` |
| 会话保持 | 默认复用当前 MCP client 的默认会话；显式传 `conversationId` 精确定位；`newConversation=true` 时新建 |
| 单例宿主 | **MCP transport 生命周期 ≠ Chromium 生命周期**：浏览器由单例宿主进程独占持有，避免多 App 争抢同一 profile |
| 并发模型 | 同一 conversation 内严格串行，不同 conversation 可并行；首版可退化为全 server 单队列 |
| 行为 | 发送 `message`（不注入 `%%CHATGPT%%` 前缀，见配置项）→ 状态机等待生成完成 → 按 turn anchor 读取本次回复 → 返回结构化结果 |
| 登录 | 首次运行需在 Playwright 浏览器中手动登录一次 ChatGPT，登录态持久化到独立 profile，后续自动复用 |
| 消息前缀 | `%%CHATGPT%%` 仅作旧自动化入口的触发 sentinel，**不是 MCP 协议的一部分**；通过 server 配置 `DD_CHATGPT_MESSAGE_PREFIX` 控制，默认空字符串 |

## 架构（单例浏览器宿主）

```
[任意 MCP 客户端 app] ── MCP transport ──> dd-ask-chatgpt MCP server (singleton)
                                               │  ┌──────────────────────────────┐
                                               ├─>│ Request Manager              │ 并发/串行调度、Cancellation
                                               ├─>│ Conversation Manager         │ conversationId → Page/URL
                                               │  └──────────────┬───────────────┘
                                               │                 └── Playwright ──> 独立 Chromium 实例
                                               │                                        │
                                               │                        persistent profile (登录态，单一 owner)
                                               └── stdout → MCP only；stderr → logs
```

核心不变项：**MCP transport 生命周期 ≠ Chromium 生命周期**。多个 App 各自启动的 MCP server 进程不得各自拉起一个 Chromium 去争用同一个 `userDataDir`，Playwright `launchPersistentContext(userDataDir)` 明确要求同一 User Data Directory 不能同时启动多个浏览器实例。

落地形态（按对各类宿主支持程度的优先级）：

1. **首选**：一个长期运行的常驻 server（Streamable HTTP 或独立进程），天然可服务多个 MCP client，单一进程独占 Playwright 与 profile。
2. **兜底**：各 App 通过薄 stdio adapter 连接到同一个 singleton 后端（backend 独占 Playwright 与 profile），适配不支持 HTTP MCP 的宿主。
3. 无论如何，**Chromium profile 只能有一个进程持有**，server 侧用文件锁（`locks/browser.lock`）保证互斥。

## 目录结构

```
~/.dd-ask-chatgpt/
  profile/          # Playwright 持久化 profile（登录态；仅由 dd-ask-chatgpt 管理，禁止指向日常 Chrome profile）
  state/
    conversations.json   # conversationId → conversationUrl 的映射
  locks/
    browser.lock         # Chromium/profile 互斥锁
  logs/                  # 运行日志（stderr）

dd-ask-chatgpt-mcp/      # 仓库
  package.json
  tsconfig.json
  src/
    index.ts          # MCP server 入口，注册两个工具
    requestManager.ts # 并发/串行调度（per-conversation mutex）、Cancellation
    conversationManager.ts  # conversationId 句柄管理
    chatgpt.ts        # Playwright 浏览器控制与状态机核心逻辑
  README.md           # 安装 / 配置 / 各 app 挂载说明
```

## 工具契约

### `dd_chatgpt_ask`

输入（JSON 对象）：
- `message: string` — 要发送给 ChatGPT 的内容。
- `conversationId?: string` — 精确复用指定会话；与 `newConversation=true` 互斥。
- `newConversation?: boolean` — 默认 `false`；`true` 时先新建会话再发送。
- `timeoutMs?: number` — 可选的完成等待超时（默认 30–60s）。

约束：`conversationId` 与 `newConversation=true` **互斥**，同时给出报参数错误。

行为：
1. 定位会话：`newConversation=true` → 新建；`conversationId` 指定 → 精确复用；两者都没给 → 使用当前 MCP client 的默认会话。
2. 在输入框输入 `message`（发送内容为 message 原文，不注入 `%%CHATGPT%%`；如需前缀由配置 `DD_CHATGPT_MESSAGE_PREFIX` 提供）。
3. 发送。
4. 按状态机等待生成完成（见「完成状态机」），超时则返回 `status: "incomplete"` 并尽力读取已生成部分。
5. 按 **turn anchor** 读取本次回复（见「response correlation」），不依赖 `last()`。

返回（outputSchema 结构化）：
```
{ "status": "complete" | "incomplete",
  "content": "...",
  "requestId": "req_xxx",
  "conversationId": "conv_xxx",
  "conversationUrl"?: "..." }
```

失败：MCP tool result 设 `isError: true`，返回结构化错误 `{ code, message, retryable }`（见「错误处理」）。

### `dd_chatgpt_new_conversation`

输入：`{}`（无参数）。

行为：新开一个 ChatGPT 会话，返回**稳定 `conversationId` 句柄**；此时 `conversationUrl` 可为 `null`（尚未真正发消息），首次发送后才回填 URL。`conversationId` 是 MCP server 定义的稳定引用，**URL 只是外部元数据，不是主键**。

返回：
```
{ "conversationId": "conv_xxx", "conversationUrl"?: "..." }
```

## response correlation（请求归属）

不依赖「最后一条回复」，避免并发/UI 重绘导致的 race condition：

```
请求 A 发送前：const before = await assistantMessages.count()
发送后等待：assistantMessages.count() >= before + 1
回复 = assistantMessages.nth(before)          // 而非 .last()
```

每次请求建立自己的 turn anchor，进一步记录 `requestId / conversationId / userMessageIndex / assistantMessageIndex`，形成 `Request → User turn N → Assistant turn N` 的请求-响应绑定。动态列表的 DOM 读取优先用 Playwright locator + 等待条件同步，避免手写固定 sleep。

## 完成状态机

`「停止回答」按钮消失` 只是完成判据之一，不作为唯一依据。采用状态机：

```
SENT → WAIT_NEW_ASSISTANT_TURN → GENERATING → WAIT_STABLE → COMPLETE
```

完成条件至少组合：
1. 已观察到本次新增 assistant turn（turn anchor 命中）。
2. streaming / stop indicator 不存在。
3. 输入框恢复可操作。
4. assistant 文本连续约 500–1000ms 不再变化。

超时：返回 `status: "incomplete"`（仍属成功的 tool result，带已生成部分），不抛异常。完全无法完成（如 DOM 无法识别）才走 `isError: true`。

## 并发模型

- **同一 conversation 内严格串行**：`Map<ConversationId, Mutex>`，避免两个 prompt 同时塞进同一 ChatGPT 会话。
- **不同 conversation 可并行**：互不阻塞，支持未来多会话同时工作。
- **首版可保守**：全 server 单队列串行，之后升级为 per-conversation queue。
- **Cancellation**：MCP cancellation → `AbortController` → 停止 Playwright wait → 释放 conversation mutex。若 ChatGPT 仍在生成可点击 Stop generation（第二阶段增强）；第一版至少停止内部等待并释放锁。

## 错误处理（机器可恢复）

定义稳定错误码，供 Agent 采取恢复动作，而非仅人可读文本。错误码示例：

```
LOGIN_REQUIRED / PROFILE_LOCKED / BROWSER_LAUNCH_FAILED / PAGE_NOT_AVAILABLE /
CONVERSATION_NOT_FOUND / SEND_FAILED / RESPONSE_NOT_FOUND / DOM_CHANGED /
NETWORK_ERROR / TIMEOUT / CANCELLED
```

返回：`{ "code": "LOGIN_REQUIRED", "message": "...", "retryable": false }`，并在 tool result 上设 `isError: true`。

失败边界约定：
- 部分答案 + timeout → 普通成功，`status: "incomplete"`。
- 完全无法完成（未登录、profile 锁、DOM 无法识别、浏览器启动失败）→ `isError: true`。
- 会话标签页异常（被关闭等）：自动新开并重建 conversationId 映射，不报致命错误；重建后返回新 conversationId。

## outputSchema

为多宿主服务，定义稳定机器契约（`outputSchema` + `structuredContent`），不让客户端解析文本。两工具的 output 见上文工具契约。使用 `outputSchema` 声明后，server 返回符合该 schema 的结构化数据。

## profile 生命周期

- 目录：`~/.dd-ask-chatgpt/profile/`。
- **单一 owner**：该 profile 只能由 dd-ask-chatgpt 管理，不允许指向用户日常 Chrome profile（Playwright 官方警告不要自动化主用户 profile）。
- **互斥**：通过 `locks/browser.lock` 保证同一时间只有一个进程持有 Chromium/profile，避免多实例争用。
- **崩溃/重启恢复**：server 或 Chromium 崩溃后，能清理遗留锁、识别 stale profile 并重建，不因残留锁永久阻塞。

## 日志

- 记录：`requestId / clientInfo / conversationId / startTime / duration / status / errorCode / URL`。
- **不默认记录完整 prompt / response**（可能含源码、测试代码、内部文档）。
- **stdio 传输时：stdout 只走 MCP JSON-RPC wire，普通日志一律写 stderr**，避免破坏协议（`console.log` 不得用于日志）。
- 日志写入 `~/.dd-ask-chatgpt/logs/`。

## 配置项

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DD_CHATGPT_MESSAGE_PREFIX` | `""` | 发送前附加到 message 的前缀；默认空。旧技能如需 `%%CHATGPT%%` 哨兵在此配置，**不写死在工具契约里** |
| `DD_CHATGPT_PROFILE_DIR` | `~/.dd-ask-chatgpt/profile` | profile 目录 |
| `DD_CHATGPT_ASK_TIMEOUT_MS` | 60000 | 单次 ask 默认超时 |

## 验证（验证矩阵）

现有 happy-path 验证只能证明「能跑」，需补充证明「能可靠跨 app 使用」。验证矩阵：

| 测试 | 必要性 |
| --- | --- |
| 单 client：new_conversation → ask → 返回非空 | 必须 |
| 单 client：再次 ask → 复用同一会话 URL | 必须 |
| new_conversation 后 ask → URL 改变（新会话生效） | 必须 |
| **两个 MCP client 同时调用**（并发/串行、同一 conversation 不打架） | **Exit Gate**（跨 app 核心目标） |
| `status: "incomplete"` 超时路径 | 必须 |
| `LOGIN_REQUIRED` / `DOM_CHANGED` 错误路径 | 必须 |
| conversationId 精确复用与互斥校验 | 必须 |

「两个 MCP client 同时调用」必须作为 Exit Gate，而非增强测试，否则「跨 app」核心目标未被验证。

## 范围外（Out of Scope）

- 不替换/不删除 `dd-xctest-newbie-grilling-review` 现有的内置浏览器路径；MCP 作为独立可复用的通用能力提供。技能在 MCP 可用时优先调用，内置浏览器作为回退。
- 不支持多账号并行会话（单 profile 单 owner）。
- 不实现 ChatGPT 网页端之外的任何后端 API 调用。
- 第一版不实现「cancel 时点击 Stop generation」等第二阶段增强。

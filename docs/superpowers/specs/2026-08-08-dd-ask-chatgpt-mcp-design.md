# dd-ask-chatgpt MCP 服务器设计

## 目标

把「查询 ChatGPT」从 `dd-xctest-newbie-grilling-review` 技能内嵌的浏览器编排逻辑中提取出来，做成一个独立的 MCP 服务器，供 Trae、opencode、WorkBuddy、Claude Code、Cursor 等所有支持 MCP 标准的应用跨 app 复用。

## 背景与问题

当前「查询 ChatGPT」逻辑内嵌在 `dd-xctest-newbie-grilling-review/references/risk-review-and-ask.md`，依赖 Trae 的 `integrated_browser`（内置浏览器）MCP 工具（`browser_tabs` / `browser_navigate` / `browser_type` / `browser_press_key` / `browser_snapshot`）。这套逻辑已验证可用，但：

- 被某个技能内嵌，其他技能/项目无法直接复用。
- 依赖宿主 app 私有的内置浏览器 MCP，无法跨 app（opencode / WorkBuddy / Claude Code 等）复用。
- 因此需要一个与宿主无关的独立浏览器驱动方式。

## 决策

| 项 | 决策 |
| --- | --- |
| 载体 | MCP 服务器（跨 app 通用） |
| 语言/栈 | TypeScript：`@modelcontextprotocol/sdk` + `playwright` |
| 浏览器 | Playwright 独立浏览器实例，持久化 profile 自维护 ChatGPT 登录态 |
| 工具 1 | `dd_chatgpt_ask(message, { newConversation? })` — 默认复用已开会话，可选显式新开 |
| 工具 2 | `dd_chatgpt_new_conversation()` — 显式新建一个会话 |
| 会话保持 | 默认复用已开会话；标签页保持不关闭；无会话或显式请求时才新开 |
| 行为 | 输入 `%%CHATGPT%%` 打头 → 发送 → 等待「停止回答」消失 → 读取本次新增的最后一条回复 → 返回 |
| 登录 | 首次运行需在 Playwright 浏览器中手动登录一次 ChatGPT，登录态持久化到独立 profile，后续自动复用 |

## 工具契约

### `dd_chatgpt_ask`

输入：
- `message: string` — 要发送给 ChatGPT 的内容。实现会自动在首行加 `%%CHATGPT%%` 标记（若调用方未加）。
- `newConversation?: boolean` — 默认 `false`（复用当前会话）；`true` 时先新建会话再发送。

行为：
1. 若 `newConversation` 或当前无可用会话 → 新开会话。
2. 否则复用当前会话标签页。
3. 在输入框输入 `%%CHATGPT%%` + `message`。
4. 发送。
5. 轮询等待「停止回答」按钮消失（生成完成），超时（约 30–60s）则尽力读取当前最后一条回复并标注「生成可能未完成」。
6. 读取本次发送后新增的最后一条 ChatGPT 回复。
7. 返回 `{ content: string, conversationUrl: string, incomplete?: boolean }`。

### `dd_chatgpt_new_conversation`

行为：新开一个 ChatGPT 会话标签页，返回 `{ conversationUrl: string }`。不发送任何消息。

## 架构

```
[任意 MCP 客户端 app] ── MCP 协议 ──> dd-ask-chatgpt MCP server
                                          │
                                          └── Playwright ──> 独立 Chromium 实例
                                                                    │
                                                     persistent profile (登录态)
```

- MCP server 是一个独立的 Node/TypeScript 进程，通过 `@modelcontextprotocol/sdk` 暴露两个工具。
- server 内部持有 Playwright `browser` 实例与当前会话页 `page`，跨调用保持（会话保持语义）。
- Playwright 使用 `launchPersistentContext`（或固定 userDataDir 的普通 context）持久化 ChatGPT 登录态，避免每次重新登录。

## 目录结构（建议）

```
dd-ask-chatgpt-mcp/
  package.json
  tsconfig.json
  src/
    index.ts          # MCP server 入口，注册两个工具
    chatgpt.ts        # Playwright 浏览器控制与「查询 ChatGPT」核心逻辑
  profile/            # Playwright 持久化 profile（登录态，gitignore）
  README.md           # 安装 / 配置 / 各 app 挂载说明
```

## 错误处理

- 未登录：提示用户先在 Playwright 浏览器完成一次登录，返回可读错误。
- 等待超时：尽力读取当前可见的最后一条回复并标注 `incomplete: true`，不抛异常。
- 读取失败：返回错误信息，不破坏 server 进程（可重试）。
- 会话标签页异常（被关闭等）：自动新开，不报致命错误。

## 验证

1. 启动 MCP server，用 MCP 客户端（如 `mcp-inspector`）调用 `dd_chatgpt_new_conversation`。
2. 在 Playwright 浏览器完成一次 ChatGPT 登录。
3. 调用 `dd_chatgpt_ask("测试")`，确认返回非空回复。
4. 再次调用 `dd_chatgpt_ask("第二条")`，确认在同一会话 URL 内追加（复用生效，URL 不变）。
5. 调用 `dd_chatgpt_new_conversation` 后再次 ask，确认 URL 改变（新开会话生效）。

## 范围外（Out of Scope）

- 不替换/不删除 `dd-xctest-newbie-grilling-review` 现有的内置浏览器路径；MCP 作为独立可复用的通用能力提供。技能可在 MCP 可用时优先调用，内置浏览器作为回退。
- 不支持多账号并行会话。
- 不实现 ChatGPT 网页端之外的任何后端 API 调用。

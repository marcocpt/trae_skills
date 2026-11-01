---
name: abu-hotline
description: 通过 curl 收发企业微信消息（阿布热线协作面）。当用户要求"查收件箱/给企微发消息/收发企微消息/阿布热线/等企微回复"时使用。
---

# 阿布热线（abu-hotline）

企业微信智能机器人长连接协作面，本机 HTTP API。任何能跑 shell 的 agent 都可以通过 curl 使用。

## 服务地址

`http://127.0.0.1:9876`

**启动检查**：`curl -s http://127.0.0.1:9876/status` → `{"status":"connected"}` 为在线；`"reconnecting"` 为重连中（等几秒重试）；`"down"` 或连不上时，按 `~/Working/AICoding/abu-hotline/docs/部署说明.md` 启动客户端（手动 `node --experimental-strip-types src/index.ts` 或 launchd 守护）。

## 机器人路由（提示词 → 端口）

多机器人模式下，按用户提示词选择实例端口：

| 用户提示词 | 机器人 | 端口 |
|---|---|---|
| 提到 "wxr1" / "阿布热线" / **未指定（默认）** | wxr1 | 9876 |
| 提到 "wxr2" | wxr2 | 9877 |

**路由规则**：

1. 用户明确说用哪个机器人（如"用 wxr2 发"/"查 wxr2 收件箱"）→ 用对应端口；
2. 未指定 → 默认 wxr1（9876）；
3. 新增机器人或不记得端口时读配置：`cat ~/Working/AICoding/abu-hotline/bots.config.json`（bots 数组的 name/apiPort 就是完整映射表）。

**零绑定原则**：agent 无需预先绑定机器人——每次请求按提示词选端口即可，切换机器人 = 换端口号，其余操作完全不变。

## 五类操作

### 1. 查状态

```bash
curl -s http://127.0.0.1:9876/status
```

### 2. 取新消息（增量）

cursor 是最后读到的 seq，各会话自行维护（首条用 0）。

```bash
curl -s 'http://127.0.0.1:9876/messages?cursor=0'
# {"messages":[{"seq":1,"msgid":"...","received_at":"...","from_userid":"...","msgtype":"text","content":"..."}]}
```

### 3. 等待新消息（长轮询，零 token）

```bash
curl -m 600 'http://127.0.0.1:9876/wait?cursor=2&timeout=570'
```

有新消息秒级返回；无则最多挂 570 秒后返回 `{"messages":[]}`。

**token 经济要点**：这是一条普通 shell 命令，挂起期间 LLM 完全不推理（零 token）。**不要用循环轮询**——每次轮询都是一次 LLM 推理（约 24 万 token/小时 vs 长轮询 1.2 万）。

### 4. 发 markdown 消息

```bash
curl -s -X POST http://127.0.0.1:9876/send \
  -H 'Content-Type: application/json' \
  -d '{"content":"**加粗标题** 普通正文"}'
# {"ok":true,"reqId":"send-...","duplicate":false}
```

超长（>20480 字节）自动拆分或转 HTML 文件。发送目标默认为最近发消息的用户。

### 5. 发 HTML 文件（暗色主题）

```bash
curl -s -X POST http://127.0.0.1:9876/send-file \
  -H 'Content-Type: application/json' \
  -d '{"path":"/absolute/path/to/result.html"}'
```

**HTML 交付物一律暗色主题**（深色背景约 #1a1a1a、浅色文字、语义色可辨识、自包含 CSS 不依赖外部资源）。

## 回合衔接

- **回合内长轮询**：任务进行中需要等用户反馈时，发 `/wait` 挂起等新消息（零 token 等待，新消息到达自动继续）；
- **回合制**：一轮结束后停下，用户说"继续"时先 `/messages` 取新消息（cursor 从上次位置续接）。

## 完整回合模板

```
1. 取消息    curl /messages?cursor=N        # 读用户需求
2. 处理      （agent 干活）
3. 发结果    curl /send 或 /send-file       # 简单结果 markdown，复杂结果 HTML 文件（暗模式）
4. 等回复    curl -m 600 /wait?cursor=M     # 长轮询等反馈（或回合制：用户说"继续"）
5. 继续      回到 1                          # cursor 更新为最新 seq
```

## 注意事项

- 发送目标默认最近发消息的用户；收件箱空时 `/send` 返回 409 `no_target`（先让用户发一条消息）；
- `req_id` 可选，传则幂等（同 req_id 不重复投递）；
- 客户端是纯通道，不自动回复——回复必须由 agent 主动调 `/send` 发起；
- **多机器人**：每个 bot 一个客户端实例 + 独立端口（wxr1=9876、wxr2=9877 等），各 agent curl 自己的端口，互不干扰；配置见 `~/Working/AICoding/abu-hotline/bots.config.json` 与 `docs/协作指引.md`。

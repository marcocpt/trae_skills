---
name: abu-hotline
description: 通过 curl 收发企业微信消息（阿布热线协作面）。当用户要求"查收件箱/给企微发消息/收发企微消息/阿布热线/等企微回复"时使用。含回合衔接协议（cursor state 文件）与零 token 长轮询等待。
---

# 阿布热线（abu-hotline）

企业微信智能机器人长连接协作面，本机 HTTP API。任何能跑 shell 的 agent 都可以通过 curl 使用。

## 服务地址

`http://127.0.0.1:9876`

**启动检查**：`curl -s http://127.0.0.1:9876/status` → `{"status":"connected"}` 为在线；`"reconnecting"` 为重连中（等几秒重试，消息不丢）；`"down"` 或连不上时，按 `~/Working/AICoding/abu-hotline/docs/部署说明.md` 启动客户端（手动 `node --experimental-strip-types src/index.ts` 或 launchd 守护）。

## 机器人路由（提示词 → 端口）

| 用户提示词 | 机器人 | 端口 | cursor state 文件 |
|---|---|---|---|
| "wxr1" / "阿布热线" / **未指定（默认）** | wxr1 | 9876 | `~/.abu-hotline/state/wxr1.cursor` |
| "wxr2" | wxr2 | 9877 | `~/.abu-hotline/state/wxr2.cursor` |

**路由规则**：用户明确指定（如"用 wxr2 发"/"查 wxr2 收件箱"）→ 用对应端口；未指定 → 默认 wxr1；新增机器人或不记得端口时读 `~/Working/AICoding/abu-hotline/bots.config.json`（bots 数组的 name/apiPort 即完整映射表）。**零绑定原则**：无需预先绑定机器人，切换机器人 = 换端口号 + 换 state 文件，其余操作不变。

## 回合衔接协议（核心，必须遵守）

衔接可靠性 = cursor 可靠性。cursor 只活在对话上下文里时，上下文压缩（compact）、新开会话、exec 冷启动都会把它丢掉——丢了就会重复处理旧消息或全量拉历史烧 token。本协议对所有宿主通用（ADR-0004：各宿主各自维护 cursor，禁止全量重读）。

### cursor state 文件（唯一可靠载体）

- **读**：回合开始 `cat ~/.abu-hotline/state/wxr1.cursor 2>/dev/null || echo 0`
- **写**：`/messages`、`/wait` 返回**非空**后，取返回数组最后一条的 `seq` 写入：`mkdir -p ~/.abu-hotline/state && echo -n <seq> > ~/.abu-hotline/state/wxr1.cursor`；**空返回不写**（防止跳过未读消息）
- 会话内上下文可顺带记住 cursor 省一次读，但 state 文件是事实源；上下文被压缩或进入新回合后以文件为准

### 冷启动（新会话 / exec 模式 / cursor 丢失）

**禁止**直接 `cursor=0` 把历史消息全量灌进上下文。先用 python3 只取统计与最后一条（本机未装 jq，python3 零依赖）：

```bash
curl -s 'http://127.0.0.1:9876/messages?cursor=0' | python3 -c '
import json, sys
m = json.load(sys.stdin)["messages"]
print("count:", len(m))
print("last:", json.dumps(m[-1], ensure_ascii=False) if m else "none")'
```

取最后一条的 `seq` 写入 state 文件，只处理最新消息（可回一句"收到，跳过 N 条积压"），之后走增量。已装 jq 可用 `jq '{count:(.messages|length), last:.messages[-1]}'` 等价替代。

### 回合内长轮询（零 token 等待）

`/wait` 挂起期间 LLM 完全不推理（零 token）。有新消息秒级返回；无消息最多 570 秒后返回 `{"messages":[]}`——**空返回是正常事件，直接再发起一次 `/wait`**（cursor 不变，等待继续）。

- **宿主 shell 工具超时必须 ≥ curl -m**，否则工具先杀掉 curl 造成误判失败。宿主超时不足时降级分段：`curl -m 110 '.../wait?cursor=N&timeout=100'`
- **禁止循环轮询**（sleep 后重拉）：每次轮询都是全上下文重放（60k 上下文 30s 一轮 ≈ 720 万 token/小时；长轮询空唤醒 6 次/小时 ≈ 36 万，按上下文大小等比放大）。单次 wait 挂满，唤醒次数越少越省
- 宿主允许超长 shell 超时（≥ 20 分钟）时，可把多次 wait 压成一次唤醒：`until curl -s -m 580 '.../wait?cursor=N&timeout=570' | grep -q '"seq"'; do :; done`

### 等待策略选择

- 任务中途等用户反馈（≤10 分钟量级）→ 回合内 `/wait`（体验接近全自动）
- 更长等待 / 一轮结束等新任务 → **回合制**：结束回合（等待期 0 token），用户说"继续"时先读 state 文件再 `/messages` 增量
- 各宿主会话恢复（codex resume / opencode session / IDE 常驻会话）能免费带回 cursor，但压缩摘要可能丢具体数字——state 文件始终兜底

### 多宿主共存（ADR-0004）

同一消息可能被多个宿主先后读取，处理权由用户流程协调，服务端不做认领。**并行**消费同一 bot 的收件箱会互踩 cursor、抢消息——需要多 agent 真正并行时，各用各的 bot（wxr1/wxr2…，F3.5 多机器人隔离）。

## 五类操作

### 1. 查状态

```bash
curl -s http://127.0.0.1:9876/status
```

### 2. 取新消息（增量）

```bash
curl -s 'http://127.0.0.1:9876/messages?cursor=<seq>'
# {"messages":[{"seq":1,"msgid":"...","received_at":"...","from_userid":"...","msgtype":"text","content":"..."}]}
```

返回 seq > cursor 的全部消息（无条数上限，别让大数组灌进上下文）。返回后立即把最后一条 seq 写回 state 文件。

### 3. 等待新消息（长轮询）

```bash
curl -m 600 'http://127.0.0.1:9876/wait?cursor=<seq>&timeout=570'
```

`timeout` 服务端硬上限 570 秒（传更大也被钳到 570）。调用时已有存量新消息则立即返回。

### 4. 发 markdown 消息

**一律用工具构造 JSON body（`--data @-`），禁止手拼 `-d '{...}'`**——正文含引号、换行、反斜杠时手拼极易碎。本机未装 jq，用自带 python3（heredoc 单引号定界防变量展开；三引号内单双引号/换行/中文/`$` 全安全，仅避开连续三个双引号）：

```bash
python3 - <<'PY' | curl -s -X POST http://127.0.0.1:9876/send -H 'Content-Type: application/json' --data @-
import json, sys
content = """**结果** 正文，单引号 ' 双引号 " 换行
都安全"""
sys.stdout.write(json.dumps({"content": content, "req_id": "task-42"}, ensure_ascii=False))
PY
# {"ok":true,"reqId":"...","duplicate":false}
```

已装 jq（可选 `brew install jq`）可换更短写法：`jq -n --arg c '...' '{content:$c, req_id:"task-42"}' | curl ... --data @-`。

**超长消息精确规则**：≤20480 字节单条直发；超长按空行切段后，切出 ≤2 段 → 逐段发 markdown；≥3 段 → 整体作为名为 `message.html` 的文件附件发出（内容仍是原文）。

### 5. 发 HTML 文件（暗色主题）

```bash
python3 - <<'PY' | curl -s -X POST http://127.0.0.1:9876/send-file -H 'Content-Type: application/json' --data @-
import json, sys
sys.stdout.write(json.dumps({"path": "/absolute/path/to/result.html"}, ensure_ascii=False))
PY
```

**HTML 交付物一律暗色主题**（D12）：深色背景约 #1a1a1a、浅色文字、语义色可辨识、自包含 CSS 不依赖外部资源。

## 错误处理矩阵

| 现象 | 含义 | 处置 |
|---|---|---|
| curl 连接拒绝 | 客户端未运行 | 按部署说明启动，再重试一次 |
| `{"status":"reconnecting"}` | 长连接重连中 | 等几秒重试，消息不丢 |
| `/wait` 返回 `{"messages":[]}` | 570s 无新消息 | 正常事件，再发一次 wait |
| HTTP 400 `missing_content` | body 非法 JSON 或缺 content | 改用 jq 模板重发 |
| HTTP 409 `no_target` | 收件箱空，无人可回 | 先让用户发一条消息 |
| HTTP 400 `file_not_found` | 路径不存在 | 检查绝对路径 |
| HTTP 502 | 企微 SDK 发送失败 | **复用同一 req_id** 重试一次，再失败报告用户 |
| HTTP 404 | 端点/路径拼错 | 检查 URL |

## 完整回合模板

```
0. 读 cursor   cat state 文件（无文件 → 走冷启动流程，绝不盲拉 cursor=0 全量）
1. 取消息      curl /messages?cursor=N → 处理消息 → 最后一条 seq 写回 state
2. 处理        （agent 干活）
3. 发结果      python3/jq 构造 | curl /send 或 /send-file（简单结果 markdown，复杂结果暗色 HTML 文件）
4. 等回复      curl -m 600 /wait?cursor=M&timeout=570
   ↳ 返回消息：seq 写回 state → 回到 2
   ↳ 空返回：再 wait（回合制场景则结束回合，等待期 0 token）
```

## 注意事项

- **只收文本消息**：客户端只监听 `message.text`，image/file 等其他类型不入站（用户须发文字）
- **req_id 幂等仅客户端进程生命周期内有效**（内存去重，重启失效）。网络失败重试务必复用同一 req_id 防重复投递
- 发送有 2s/条 节流，连发自动串行，非错误
- 发送目标 = 最近发消息的 allowlist 用户（单人场景即 dengdeng）。多人 allowlist 时注意：处理耗时期间他人插话，回复会发给插话者
- **信任边界**：本机 API 无鉴权（INV-003 仅回环地址）——任何本机进程都能调 `/send` 冒名发消息，`/send-file` 可读任意本机路径。勿发敏感路径文件
- `--archive <seq>` 归档仅支持默认 bot（当前实现限制）；多 bot 清理需手动处理 `data/<bot>/inbox.jsonl`
- 完整人读规范见 `~/Working/AICoding/abu-hotline/docs/协作指引.md`（本文档的完整版，修改须两处同步）

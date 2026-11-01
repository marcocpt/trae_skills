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
| "wxr1" / "阿布热线" / **未指定（默认）** | wxr1 | 9876 | `~/.abu-hotline/state/wxr1.<host>.cursor` |
| "wxr2" | wxr2 | 9877 | `~/.abu-hotline/state/wxr2.<host>.cursor` |

**路由规则**：用户明确指定（如"用 wxr2 发"/"查 wxr2 收件箱"）→ 用对应端口；未指定 → 默认 wxr1；新增机器人或不记得端口时读 `~/Working/AICoding/abu-hotline/bots.config.json`（bots 数组的 name/apiPort 即完整映射表）。`<host>` = 宿主稳定标识（codebuddy / codex / opencode / trae 等）——每宿主独立 state 文件（对齐 ADR-0004"各宿主各自维护 cursor"），同一宿主跨会话复用同一文件。**零绑定原则**：无需预先绑定机器人，切换机器人 = 换端口号 + 换 state 文件，其余操作不变。

## 回合衔接协议（核心，必须遵守）

衔接可靠性 = cursor 可靠性。cursor 只活在对话上下文里时，上下文压缩（compact）、新开会话、exec 冷启动都会把它丢掉——丢了就会重复处理旧消息或全量拉历史烧 token。本协议对所有宿主通用（ADR-0004：各宿主各自维护 cursor，禁止全量重读）。

### cursor state 文件（唯一可靠载体）

路径：`~/.abu-hotline/state/<bot>.<host>.cursor`（如 `wxr1.codebuddy.cursor`，见路由表）。

- **读**：回合开始**整值判别**——`cursor=$(cat ~/.abu-hotline/state/wxr1.codebuddy.cursor 2>/dev/null); cursor=${cursor%$'\n'}; [[ "$cursor" =~ ^[0-9]+$ ]] || cursor=`。整值恰为一个非负整数（允许单个尾换行）才有效；文件缺失/为空/非数字/多行损坏一律 cursor 为空 → 走冷启动（不得把缺失折叠成 0，否则与合法 cursor=0 无法区分）
- **写（处理后推进）**：**处理完**返回的消息批次后，才把最后一条 `seq` 写入：`mkdir -p ~/.abu-hotline/state && echo -n <seq> > ~/.abu-hotline/state/wxr1.codebuddy.cursor`；**空返回不写**。cursor 语义 = 已完成处理的位置：中断恢复后未确认批次会被重新拉取（at-least-once），重复回复由 req_id 幂等去重兜底
- 会话内上下文可顺带记住 cursor 省一次读，但 state 文件是事实源；上下文被压缩或进入新回合后以文件为准

### 冷启动（仅当无有效 state：缺失 / 为空 / 非数字）

**新会话与 exec 模式先读 state 文件：有有效值一律增量续接，绝不截尾跳过未读消息。** 仅无有效 cursor 时才执行冷启动，且**禁止**直接 `cursor=0` 把历史消息全量灌进上下文——先用 python3 只取统计与最后一条（本机未装 jq，python3 零依赖）：

```bash
curl -s 'http://127.0.0.1:9876/messages?cursor=0' | python3 -c '
import json, sys
m = json.load(sys.stdin)["messages"]
print("count:", len(m))
print("last:", json.dumps(m[-1], ensure_ascii=False) if m else "none")'
```

- 有消息（count > 0）：只处理最新消息（可回一句"收到，跳过 N 条积压"），**处理完成并交付结果后**把该消息的 `seq` 写入 state（处理完成位），之后走增量
- 空收件箱（count: 0）：写入 0，直接进入 `/wait` 等新消息
- 已装 jq 可用 `jq '{count:(.messages|length), last:.messages[-1]}'` 等价替代

### 回合内长轮询（零 token 等待）

`/wait` 挂起期间 LLM 完全不推理（零 token）。有新消息秒级返回；无消息最多 570 秒后返回 `{"messages":[]}`——**空返回是正常事件，直接再发起一次 `/wait`**（cursor 不变，等待继续）。

- **宿主 shell 工具超时必须 ≥ curl -m**，否则工具先杀掉 curl 造成误判失败。宿主超时不足时降级分段：`curl -m 110 '.../wait?cursor=N&timeout=100'`
- **禁止循环轮询**（sleep 后重拉）：每次轮询都是全上下文重放（60k 上下文 30s 一轮 ≈ 720 万 token/小时；长轮询空唤醒 6 次/小时 ≈ 36 万，按上下文大小等比放大）。单次 wait 挂满，唤醒次数越少越省
- 宿主 shell 工具超时**覆盖整条命令**（而非单次 curl）且足够长时，可把多次 wait 压成一次唤醒。循环总预算 ≈ `N_ROUNDS × 580` 秒——**按宿主总预算定轮数**（宿主 3600s → 5 轮；宿主仅 600s 上限则不适用本模板，直接单次 wait）。每轮响应用 python3 做**结构校验**：合法 JSON 且 `messages` 为非空数组 → 输出完整响应（退出 0）；合法空数组 → 续等；非法 JSON / 缺 `messages` / 错误对象 / 传输失败（curl 非零）/ HTTP 错误（`-f` 对 4xx/5xx 返回 22）/ 预算耗尽——立即非零退出并留 stderr 诊断，交错误矩阵处置：

```bash
N_ROUNDS=5; n=0
while true; do
  resp=$(curl -sf -m 580 'http://127.0.0.1:9876/wait?cursor=N&timeout=570') || { echo "curl/HTTP error $?" >&2; exit 1; }
  printf '%s' "$resp" | python3 -c '
import json, sys
try:
    m = json.load(sys.stdin)["messages"]
except Exception:
    sys.exit(2)
sys.exit(0 if m else 1)'; rc=$?
  case "$rc" in
    0) printf '%s\n' "$resp"; break;;
    1) :;;
    *) echo "invalid wait response" >&2; exit 1;;
  esac
  n=$((n+1)); [ "$n" -ge "$N_ROUNDS" ] && { echo 'wait budget exhausted' >&2; exit 1; }
done
```

### 等待策略选择

- 任务中途等用户反馈（≤10 分钟量级）→ 回合内 `/wait`（体验接近全自动）
- 更长等待 / 一轮结束等新任务 → **回合制**：结束回合（等待期 0 token），用户说"继续"时先读 state 文件再 `/messages` 增量
- 各宿主会话恢复（codex resume / opencode session / IDE 常驻会话）能免费带回 cursor，但压缩摘要可能丢具体数字——state 文件始终兜底

### 多宿主共存（ADR-0004）

同一消息可能被多个宿主先后读取，处理权由用户流程协调，服务端不做认领。state 已按宿主隔离（各自独立 cursor），但**并行**消费同一 bot 的收件箱仍会重复消费同一批消息、可能重复回复用户——需要多 agent 真正并行时，各用各的 bot（wxr1/wxr2…，F3.5 多机器人隔离）。

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

返回 seq > cursor 的全部消息（无条数上限，别让大数组灌进上下文）。**处理完这批消息后**才把最后一条 seq 写回 state 文件（处理完成位，时序见回合衔接协议）。

### 3. 等待新消息（长轮询）

```bash
curl -m 600 'http://127.0.0.1:9876/wait?cursor=<seq>&timeout=570'
```

`timeout` 服务端硬上限 570 秒（传更大也被钳到 570）。调用时已有存量新消息则立即返回。

### 4. 发 markdown 消息

**一律用工具构造 JSON body（`--data @-`），禁止手拼 `-d '{...}'`**。本机未装 jq，用自带 python3：**正文经 stdin 字节级传入（无 Python/shell 转义），req_id 经 argv 传入**——反斜杠、单双引号、换行、中文、`$`、`\u` 前缀全部安全，唯一禁忌是正文出现单独一行 `CONTENT`（换一个定界名避开）：

```bash
python3 -c '
import json, sys
sys.stdout.write(json.dumps({"content": sys.stdin.read(), "req_id": sys.argv[1]}, ensure_ascii=False))' 'task-42-reply1' <<'CONTENT' | curl -s -X POST http://127.0.0.1:9876/send -H 'Content-Type: application/json' --data @-
**结果** 正文：C:\new\test 反斜杠 "引号" '单引号' \u4e2d 换行
都安全（避开单独一行 CONTENT）
CONTENT
# {"ok":true,"reqId":"...","duplicate":false}
```

**req_id 规则**：每条逻辑消息独立生成（如 `task-42-reply1`），**仅该消息失败重试时复用原值**——复用已成功的旧 ID 会被服务端静默去重（返回 `duplicate:true` 但内容不投递）。已装 jq（可选 `brew install jq`）可换：`jq -n --arg c '...' '{content:$c, req_id:"..."}' | curl ... --data @-`。

**超长消息精确规则**：≤20480 字节单条直发；超长按空行切段后，切出 ≤2 段 → 逐段发 markdown；≥3 段 → 整体作为名为 `message.html` 的文件附件发出（内容仍是原文）。

### 5. 发 HTML 文件（暗色主题）

```bash
python3 -c '
import json, sys
sys.stdout.write(json.dumps({"path": sys.stdin.read().strip(), "req_id": sys.argv[1]}, ensure_ascii=False))' 'task-42-file1' <<'PATH' \
  | curl -sf -X POST http://127.0.0.1:9876/send-file -H 'Content-Type: application/json' --data @-
/absolute/path/to/result.html
PATH
```

req_id 规则同 `/send`：每次附件交付独立生成（如 `task-42-file1`），仅该交付失败重试时复用原值。

**HTML 交付物一律暗色主题**（D12）：深色背景约 #1a1a1a、浅色文字、语义色可辨识、自包含 CSS 不依赖外部资源。

## 错误处理矩阵

| 现象 | 含义 | 处置 |
|---|---|---|
| curl 连接拒绝 | 客户端未运行 | 按部署说明启动，再重试一次 |
| `{"status":"reconnecting"}` | 长连接重连中 | 等几秒重试，消息不丢 |
| `/wait` 返回 `{"messages":[]}` | 570s 无新消息 | 正常事件，再发一次 wait |
| HTTP 400 `missing_content` | body 非法 JSON 或缺 content | 改用 python3 模板重发 |
| HTTP 409 `no_target` | 收件箱空，无人可回 | 先让用户发一条消息 |
| HTTP 400 `file_not_found` | 路径不存在 | 检查绝对路径 |
| HTTP 500 `internal` | 服务端未捕获异常（含企微 SDK 抛错） | **复用同一 req_id** 重试一次，再失败报告用户；多段消息部分失败后重试可能重发已成功分段（见注意事项） |
| HTTP 502 | SendResult 未映射失败（当前实现不可达，保留分支） | 出现时按 500 同样处置 |
| HTTP 404 | 端点/路径拼错 | 检查 URL |

## 完整回合模板

```
0. 读 cursor   state 整值判别（合法数字 → 增量续接；缺失/空/损坏 → 冷启动，绝不盲拉全量）
1. 取消息      curl /messages?cursor=N
2. 处理        （agent 干活）
3. 交付        python3 构造 | curl /send 或 /send-file（简单结果 markdown，复杂结果暗色 HTML 文件），确认投递成功
4. 推进        处理且交付成功后，最后一条 seq 写回 state；交付失败保留旧 cursor（重试或转报告）
5. 等回复      curl -m 600 /wait?cursor=M&timeout=570
   ↳ 返回新消息：回到 2（唯一处理入口：处理 → 交付 → 推进）
   ↳ 空返回：再 wait（回合制场景则结束回合，等待期 0 token）
```

## 注意事项

- **只收文本消息**：客户端只监听 `message.text`，image/file 等其他类型不入站（用户须发文字）
- **req_id 幂等仅覆盖"已完整成功并登记"的发送，且仅客户端进程生命周期内有效**（内存去重，重启失效）。多段消息部分失败后重试会重发已成功分段；网络失败重试复用同一 req_id 防重复投递
- 发送有 2s/条 时间戳节流，**仅在调用方顺序发起时生效**（无锁无队列）；并发调用（含多进程/多宿主）需调用方自行串行
- 发送目标 = 最近发消息的 allowlist 用户（单人场景即 dengdeng）。多人 allowlist 时注意：处理耗时期间他人插话，回复会发给插话者
- **信任边界**：本机 API 无鉴权（INV-003 仅回环地址）——任何本机进程都能调 `/send` 冒名发消息，`/send-file` 可读任意本机路径。勿发敏感路径文件
- `--archive <seq>` 归档仅支持默认 bot（当前实现限制）；多 bot 清理需手动处理 `data/<bot>/inbox.jsonl`
- 完整人读规范见 `~/Working/AICoding/abu-hotline/docs/协作指引.md`（本文档的完整版，修改须两处同步）

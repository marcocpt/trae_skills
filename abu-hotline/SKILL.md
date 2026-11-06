---
name: abu-hotline
description: 通过 curl 收发企业微信消息（阿布热线协作面）。当用户要求"查收件箱/给企微发消息/收发企微消息/阿布热线/等企微回复"时使用；当任务需要用户决策、需要暂停等待或卡住待确认时，也必须通过本技能把完整问题发到微信机器人并持续等待回复，不得只在会话里提问。含回合衔接协议（cursor state 文件）与零 token 长轮询等待。
---

# 阿布热线（abu-hotline）

企业微信智能机器人长连接协作面，本机 HTTP API。任何能跑 shell 的 agent 都可以通过 curl 使用。

## 收到即回执（强制，2026-11-05 约定）

**用户不该空等。凡 `/messages` / `/wait` 返回非空消息批次，处理前第一动作必须先 `/send` 回一句确认；空批次不回。**

1. 取 `last_seq = max(seq)`（不依赖数组顺序）；
2. 发一条 markdown，**统一中性文案、不摘录正文**：`**收到**（seq <last_seq>）：已接住，结果稍后发回。` 文案只由 `last_seq` 决定，所有宿主一律相同——不按「本宿主是否负责处理」改写，不写「正在处理」这类无法保证的承诺，避免相同 `req_id` 对应不同内容；
3. **幂等粒度（方案 A）**：`req_id` 固定 `ack-<bot>-<last_seq>`（如 `ack-wxr2-65`），约定每 bot 每末条 seq 一条回执。不同宿主 cursor 独立，取到不同批次但末条 seq 相同时，**在同一 Sender 实例内顺序调用且首次发送已成功登记**的前提下，后发者收到 `duplicate:true` 属预期，不重试、不补发、不换 ID；并发调用不保证只投递一次。失败重试复用同一 ID，不与其他消息混用（INV-007）；
4. **保证范围**：去重只覆盖**同一 `Sender` 实例生命周期内已完整成功并登记**的 ID（`processed` 是实例字段，发送成功后才写入；`index.ts` 每进程只建一个 Sender，但范围以实例为准）。不保证并发同 ID 只投递一次（无 in-flight 合并），也不保证实例重建/重启后仍去重；并发需调用方自行串行；
5. 失败按错误矩阵复用同一 ID 重试一次，仍失败则继续处理并注明「回执未送达」，**不阻塞结果交付、不回滚 cursor**。服务端是 **2s 时间戳节流**（`sleep`）：顺序调用不丢弃，单次相邻发送最多额外等待约 2 秒（重试可能累计）；**无锁无队列**，并发不保证串行。

时序：`回执 → 处理 → 交付 → 推进 cursor`。**冷启动计数口径**：`N_total` = 返回条数；`N_total = 0` → `N_skipped = 0`、`N_processed = 0`、不发回执（写 cursor=0 进入 wait）；`N_total > 0` → `N_skipped = N_total - 1`、`N_processed = 1`。回执文案不含条数与范围，跳过积压的说明放到结果交付里；统计命令用 `min(seq)`/`max(seq)` 取端点。回执**不替代**「需要用户时，一律走微信」的完整问题与连续等待。完整规范见仓库 `docs/协作指引.md`「收到即回执」。

## 需要用户时，一律走微信（强制路由）

**凡是要决策、要暂停、或卡住等用户，都必须把完整问题发到微信机器人，并持续等到回复；不得只在当前会话里提问后结束回合。**

命中条件（满足任一即命中）：

- **要决策**：方案、方向、取舍需要用户选择；需要用户授权、批准或验收；存在多个可行解且影响后续动作；
- **要暂停**：需要用户放行、先补齐条件或先完成外部动作；按合同必须等人确认才能继续；
- **卡住等你**：缺信息、缺权限、命令或测试失败需用户裁决、环境不可用、反复重试没有进展。

判定口径：只要「下一步动作依赖用户给的输入」，就命中本节。命中后按四步执行，顺序不变。

### 1. 把问题发全

消息要自成一体，让用户只看微信就能决策，不需要回看会话上下文。至少写清：

- 当前任务、已完成的进度、卡在哪一步；
- 卡点的原始信息（报错原文、命令、相关输出、文件路径），不改写、不压缩；
- 可选项及各选项的后果、代价、影响范围，推荐项及理由（若有）；
- 需要用户给出的具体答复（例如「回 A / B」「给路径」「确认是否放行」）；
- 若不回复的默认行为与当前等待状态。

禁止用「要继续吗」「可以吗」这类空问题代替完整说明；禁止为了塞进单条消息而砍掉背景、报错或选项。

### 2. 太长的发 HTML

复用下文「五类操作」第 4、5 节的发送操作、`req_id` 规则与暗色主题要求，长度路由：

- ≤20480 字节：单条 markdown 直发；
- 超过 20480 字节，或需要携带长日志、代码、diff、多段证据：**整体写成一份暗色主题 HTML 文件**（文件名 `message.html`）用 `/send-file` 发出，再发一条简短 markdown 导语说明「完整问题见附件」与需要用户回什么；两条各自独立 `req_id`。

本节覆盖「超长消息精确规则」中「≤2 段逐段发 markdown」的做法：决策类内容不拆段，避免上下文割裂。其他消息仍按通用规则处理。

### 3. 确认送达

逐条确认 `ok:true` 且 `duplicate:false`；失败按错误处理矩阵复用同一 `req_id` 重试，未确认送达不得进入等待。发送前确认触发本次等待的消息批次已处理完并推进 cursor，等待就用这个 cursor（避免重放旧消息或漏接回复）。

### 4. 等回复不要断

送达后立即进入**回合内连续 `/wait`**，直到收到用户回复：

- `curl -m 600 'http://127.0.0.1:<端口>/wait?cursor=<当前已处理 seq>&timeout=570'`；空返回 `{"messages":[]}` 是正常事件，**原样再发一次 wait**，cursor 不变；
- 宿主 shell 工具超时、轮次预算耗尽、curl 非零或 HTTP 错误：按「回合内长轮询」模板与错误处理矩阵处置，预算耗尽就重新发起一轮（新的 shell 调用），始终继续 wait，**不结束回合**。禁止 sleep 轮询、禁止转去做别的任务、禁止自行假定答案继续推进；
- 等待回复期间**不适用**「等待策略选择」里「更长等待 → 结束回合走回合制」的分支（该分支只用于一轮结束等新任务）；
- 收到非空消息 → **立即先发统一回执**（见「收到即回执」）→ 再判断是否为本次问题的答复；是则回到「完整回合模板」的处理 → 交付 → 推进，不是则按正常新消息流程处理后继续 wait，这是唯一继续入口；空返回不回执、直接再 wait。

例外：仅当用户本次明确指定不走微信，客户端按 `docs/部署说明.md` 确认无法启动或无法恢复，或发送按错误处理矩阵重试后仍无法确认送达（含 HTTP 409 `no_target`）时，才允许在当前会话内提问并结束等待，且必须写明原因。

## 服务地址

`http://127.0.0.1:<端口>` —— 端口按本机配置取，**不要凭记忆背固定数字**（见下节）。

**启动检查**：`curl -s http://127.0.0.1:<端口>/status` → `{"status":"connected"}` 为在线；`"reconnecting"` 为重连中（等几秒重试，消息不丢）；`"down"` 或连不上时，按仓库 `docs/部署说明.md` 启动客户端（手动 `node --experimental-strip-types src/index.ts` 或 launchd 守护）。

## 机器人路由（提示词 → 端口）

**本机配置是唯一事实源。** 先定位仓库根，再读配置：

```bash
REPO=$(ls -d ~/work/AICoding/abu-hotline ~/Working/AICoding/abu-hotline 2>/dev/null | head -1)
# 多机器人模式：打印 name → apiPort 完整映射
python3 - "$REPO" <<'PY'
import json, os, sys
p = os.path.join(sys.argv[1], "bots.config.json")
if not os.path.exists(p):
    print("无 bots.config.json → 单机 .env 模式，端口见 .env 的 API_PORT")
else:
    print(json.dumps([{"name": b.get("name"), "apiPort": b.get("apiPort")}
                      for b in json.load(open(p))["bots"]], ensure_ascii=False, indent=1))
PY
```

| 用户提示词 | 机器人 | 端口 | cursor state 文件 |
|---|---|---|---|
| 未指定 / "阿布热线" / "默认" | 本机默认 bot（`bots.config.json` 第一条的 `name`；单机 `.env` 模式无名） | 该 bot 的 `apiPort`（单机 `.env` 模式取 `API_PORT`） | `~/.abu-hotline/state/<bot>.<host>.cursor` |
| "用 wxrN" / "查 wxrN 收件箱" | wxrN | `bots.config.json` 里 `name=wxrN` 的 `apiPort` | `~/.abu-hotline/state/wxrN.<host>.cursor` |

**路由规则**：用户明确指定（如"用 wxrN 发"/"查 wxrN 收件箱"）→ 用该 bot 的端口；未指定 → 本机默认 bot；配置里没有的机器人名 → 说明本机没配这个 bot，不要瞎猜端口。**机器人按机器分组**（开发机 wxr1/wxr2，其他机器各自新建如 wxr3/wxr4）——同一 BOT 凭据只能一台机器长连接，两台同时跑会互踢。`<host>` = 宿主稳定标识（codebuddy / codex / opencode / trae 等）——每宿主独立 state 文件（对齐 ADR-0004"各宿主各自维护 cursor"），同一宿主跨会话复用同一文件。**零绑定原则**：无需预先绑定机器人，切换机器人 = 换端口号 + 换 state 文件，其余操作不变。

## 回合衔接协议（核心，必须遵守）

衔接可靠性 = cursor 可靠性。cursor 只活在对话上下文里时，上下文压缩（compact）、新开会话、exec 冷启动都会把它丢掉——丢了就会重复处理旧消息或全量拉历史烧 token。本协议对所有宿主通用（ADR-0004：各宿主各自维护 cursor，禁止全量重读）。

### cursor state 文件（唯一可靠载体）

路径：`~/.abu-hotline/state/<bot>.<host>.cursor`（如 `wxr1.codebuddy.cursor`，见路由表）。

- **读**：回合开始**整值判别**。注意 shell 命令替换 `$(cat ...)` 会吞掉全部尾换行、无法区分一个与多个尾换行，须经 python3 读原始字节校验：

```bash
cursor=$(python3 -c 'import os, sys
p = sys.argv[1]
d = open(p, "rb").read() if os.path.exists(p) else b""
v = d[:-1] if d.endswith(b"\n") else d
print(v.decode() if v.isdigit() else "")' ~/.abu-hotline/state/wxr1.codebuddy.cursor)
[[ "$cursor" =~ ^[0-9]+$ ]] || cursor=   # 空 → 冷启动
```

整值恰为一个非负整数（允许单个尾换行）才有效；文件缺失/为空/非数字/多行/多尾换行一律 cursor 为空 → 走冷启动（不得把缺失折叠成 0，否则与合法 cursor=0 无法区分）
- **写（处理后推进）**：**处理完**返回的消息批次后，才把最后一条 `seq` 写入：`mkdir -p ~/.abu-hotline/state && echo -n <seq> > ~/.abu-hotline/state/wxr1.codebuddy.cursor`；**空返回不写**。cursor 语义 = 已完成处理的位置：中断恢复后未确认批次会被重新拉取（at-least-once），重复回复由 req_id 幂等去重兜底
- 会话内上下文可顺带记住 cursor 省一次读，但 state 文件是事实源；上下文被压缩或进入新回合后以文件为准

### 冷启动（仅当无有效 state：缺失 / 为空 / 非数字）

**新会话与 exec 模式先读 state 文件：有有效值一律增量续接，绝不截尾跳过未读消息。** 仅无有效 cursor 时才执行冷启动，且**禁止**直接 `cursor=0` 把历史消息全量灌进上下文——先用 python3 只取统计与最后一条（本机未装 jq，python3 零依赖）：

```bash
curl -s 'http://127.0.0.1:9876/messages?cursor=0' | python3 -c '
import json, sys
m = json.load(sys.stdin)["messages"]
print("count:", len(m))
print("min_seq:", min(x["seq"] for x in m) if m else "none")
print("max_seq:", max(x["seq"] for x in m) if m else "none")
print("last:", json.dumps(max(m, key=lambda x: x["seq"]), ensure_ascii=False) if m else "none")'
```

- 有消息（count > 0）：只处理最新消息（可回一句"收到，跳过 N 条积压"），**处理完成并交付结果后**把该消息的 `seq` 写入 state（处理完成位），之后走增量
- 空收件箱（count: 0）：写入 0，直接进入 `/wait` 等新消息
- 已装 jq 可用 `jq '{count:(.messages|length), min_seq:(if (.messages|length)>0 then (.messages|map(.seq)|min) else "none" end), max_seq:(if (.messages|length)>0 then (.messages|map(.seq)|max) else "none" end), last:(if (.messages|length)>0 then (.messages|max_by(.seq)) else "none" end)}'` 等价替代（用 `max_by(.seq)` 取末条，不依赖数组顺序）

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
if not isinstance(m, list):
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

- **优先级最高**：凡要决策、要暂停、卡住等用户 → 按「需要用户时，一律走微信」执行，回合内连续 `/wait` 直到回复，**不结束回合**；下面两条分支不适用于该场景
- 任务中途等用户反馈（≤10 分钟量级，且不属于上述场景）→ 回合内 `/wait`（体验接近全自动）
- 更长等待 / 一轮结束等新任务 → **回合制**：结束回合（等待期 0 token），用户说"继续"时先读 state 文件再 `/messages` 增量
- 各宿主会话恢复（codex resume / opencode session / IDE 常驻会话）能免费带回 cursor，但压缩摘要可能丢具体数字——state 文件始终兜底

### 常驻值守（会话在就常驻；Monitor 模式）

用户要求「会话在就一直值守，除非我说停」时：用宿主的常驻监视器（如 CodeBuddy Monitor，`persistent: true`）跑下面这个循环，而不是回合内 `/wait` 或 sleep 轮询。**必须按 seq 去重**——cursor 推进滞后时 `/wait` 会反复返回同一批消息，无去重会刷屏唤醒、烧上下文。

```bash
LAST=/tmp/abu-<bot>-last-printed
while true; do
  cursor=$(python3 -c 'import os,sys
p=sys.argv[1]
d=open(p,"rb").read() if os.path.exists(p) else b""
v=d[:-1] if d.endswith(b"\n") else d
print(v.decode() if v.isdigit() else "")' ~/.abu-hotline/state/<bot>.<host>.cursor)
  case "$cursor" in ''|*[!0-9]*) sleep 15; continue;; esac
  resp=$(curl -sf -m 580 "http://127.0.0.1:<端口>/wait?cursor=$cursor&timeout=570") || { sleep 10; continue; }
  printf '%s' "$resp" | grep -q '"messages":\[\]' && continue
  seq=$(printf '%s' "$resp" | python3 -c 'import json,sys;m=json.load(sys.stdin)["messages"];print(max(x["seq"] for x in m))' 2>/dev/null)
  [ -z "$seq" ] && continue
  last=$(cat $LAST 2>/dev/null || echo 0); case "$last" in ''|*[!0-9]*) last=0;; esac
  if [ "$seq" -gt "$last" ]; then printf '%s\n' "$resp"; echo -n "$seq" > $LAST; fi
  sleep 1
done
```

规则：

- 等待期零 token；仅新消息唤醒一次（≈一次上下文回放）。
- 去重按 seq（不按内容哈希）：处理慢或上下文压缩导致 cursor 落后时也不重复刷屏。
- Monitor 只负责唤醒，不写 cursor；agent 处理完消息后照常推进 state 文件。
- CLI 进程退出后 Monitor 即死；要「进程级常驻」需独立守护（launchd），当前场景不必要。

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

**超长消息精确规则**：≤20480 字节单条直发；超长按空行切段后，切出 ≤2 段 → 逐段发 markdown；≥3 段 → 整体作为名为 `message.html` 的文件附件发出（内容仍是原文）。决策 / 暂停 / 卡住等待类消息不适用本条的逐段发送，按「需要用户时，一律走微信」的长度路由执行。

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
1. 取消息      curl /messages?cursor=N 或 /wait 返回新消息
   ↳ 非空：**先发回执**（见「收到即回执」，req_id=ack-<bot>-<last_seq>）→ 再进入 2
   ↳ 空：不回执，继续等
2. 处理        （agent 干活）
   ↳ 需要用户决策 / 暂停 / 卡住：按「需要用户时，一律走微信」发全问题（过长发 HTML）→ 确认送达 → 连续 /wait 直到回复，再回到 2
3. 交付        python3 构造 | curl /send 或 /send-file（简单结果 markdown，复杂结果暗色 HTML 文件），确认投递成功
4. 推进        处理且交付成功后，最后一条 seq 写回 state；交付失败保留旧 cursor（重试或转报告）；回执失败不阻塞本步
5. 等回复      curl -m 600 /wait?cursor=M&timeout=570
   ↳ 返回新消息：回到 1（先回执 → 处理 → 交付 → 推进）
   ↳ 空返回：再 wait（决策等待场景不结束回合；仅"一轮结束等新任务"的回合制场景结束回合，等待期 0 token）
```

## 注意事项

- **只收文本消息**：客户端只监听 `message.text`，image/file 等其他类型不入站（用户须发文字）
- **req_id 幂等仅覆盖同一 `Sender` 实例内"已完整成功并登记"的发送**（内存 Set，实例重建/进程重启失效；并发同 ID 不保证只投递一次）。多段消息部分失败后重试会重发已成功分段；网络失败重试**必须复用同一 req_id**，但只有首次发送已完整成功并登记时后续重放才会被抑制，结果不确定的网络失败仍可能重复投递
- 发送有 2s/条 时间戳节流，**仅在调用方顺序发起时生效**（无锁无队列）；并发调用（含多进程/多宿主）需调用方自行串行
- 发送目标 = 最近发消息的 allowlist 用户（单人场景即 dengdeng）。多人 allowlist 时注意：处理耗时期间他人插话，回复会发给插话者
- **信任边界**：本机 API 无鉴权（INV-003 仅回环地址）——任何本机进程都能调 `/send` 冒名发消息，`/send-file` 可读任意本机路径。勿发敏感路径文件
- `--archive <seq>` 归档仅支持默认 bot（当前实现限制）；多 bot 清理需手动处理 `data/<bot>/inbox.jsonl`
- 完整人读规范见仓库 `docs/协作指引.md`（本文档的完整版，修改须两处同步；「收到即回执」同步写在根 `AGENTS.md` 宿主交互规则）；
- 「收到即回执」是 agent 侧协议动作，客户端不自动回复（INV-001）；回执失败不阻塞结果交付与 cursor 推进；`req_id` 去重不覆盖并发同 ID 与进程重启后

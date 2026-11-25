# 通道契约：guest-run

`bin/guest-run` 是唯一负责「把命令送进 Windows 虚拟机并取回结果」的组件。编译、烧录、探测脚本都通过它，不各自复制存根或轮询日志。

## 两种传输方式

| 方式 | 触发条件 | 行为 | 结果 |
|---|---|---|---|
| `prlctl` | `prlctl list -a` 成功且输出含 `running` | `prlctl exec <vm> --current-user cmd.exe /C "<批处理>"` | 同步，取标准输出与退出码 |
| `stub` | 上述检查失败（例如 dispatcher 登录失败） | 复制共享应用存根、改写 `APP Path`、`open` 启动、轮询日志结束标记 | 异步，结果来自日志 |

`--transport auto|prlctl|stub` 可覆盖选择。`prlctl` 通道在本机尚未实测：服务当前不可用，全部流量走 `stub`。修复服务后需先验证 UNC 批处理能否被 `cmd.exe /C` 直接执行，必要时加 `pushd` 包装，见 `ROADMAP.md` 待办第 1 项。

## 并发与排队

多个 Agent 共用一台虚拟机时，以下三处会互相破坏，所以互斥必须做在通道内核里，不能靠调用方自觉：

1. **设备独占**：一块板 + 一个调试器，同时烧录会写坏 Flash，或与调试会话抢 J-Link。
2. **存根单实例**：工作副本是固定路径 `/tmp/pemb-<虚拟机>.app`，启动前必须 `pkill` 同路径旧进程；不加锁时第二个任务会直接杀掉第一个正在跑的批处理。
3. **产物冲突**：日志清空与临时批处理命名。

### 锁的实现

- 每个锁名对应一个 `~/.pemb/locks/<锁名>.lock`，用 `flock(LOCK_EX)` 独占。进程退出或被 `kill -9` 时由内核自动释放，不会留下需要人工清理的死锁文件。
- 等待者写一个票号文件到 `~/.pemb/queue/<锁名>/`，只有票号最靠前的一个才尝试取锁，因此是**先到先得**，不是抢占。进程死掉的残留票会被后续调用清掉。
- 取到锁后写 `<锁名>.holder` 记录 pid、job、动作，供 `status` 查看；释放时删除。

### 锁名与粒度

| `--lock-scope` | 锁名 | 适用 |
|---|---|---|
| `device`（默认） | `dev-<虚拟机>` 或 `--lock-key` | 覆盖调试器与目标板，最保守 |
| `vm` | `vm-<虚拟机>` | 只保证虚拟机内单实例，允许多设备并行 |
| `none` | 不取锁 | 调用方已自行串行时使用 |

一块板对应一个 J-Link 一台虚拟机，所以默认粒度已经够用。多块板挂同一台虚拟机时才需要 `--lock-key` 区分。

### 排队与烧录确认的先后

顺序必须是**等锁 → 拿到锁 → 请求用户确认 → `--dry-run` → 执行 → 回读 → 释放**。反过来先确认再排队，等轮到时那句确认早已过期（板子可能被换、固件可能被重编）。确认阶段超时就放弃本次任务，不要占着锁等人。

### 日志与临时批处理

- `--log-mode exact`（默认）沿用给定路径，兼容 `iar/cli_build_mac.sh` 之类按固定路径 `grep` 的脚本。清空前会把上一份内容留档为 `<日志>.<job>.prev`，满足「不覆盖证据」。
- `--log-mode unique` 给日志加 job 后缀（`cli_build.<job>.log`），适合同一工程多个任务并行、需要各自留证据时。
- `exec` 的临时批处理按任务命名 `pemb_exec_<job>.bat`，不再共用固定文件名。

### 查看状态

```
bin/guest-run status --human
bin/guest-run status --key dev-Win11_M7
```

`held=True` 表示有人持有；`waiters` 是排队人数；`stale=1` 表示 holder 记录还在但进程已死（锁已由内核释放，下一次取锁会立即成功）。

## 路径与虚拟机发现

- 共享根默认 `\\Mac\Home`，对应 Mac 侧 `$HOME`；`--share-root` 与 `--mac-home` 可覆盖。
- 只有位于共享主目录下的路径才能换算成 UNC；越界会直接报错，不会静默拼接。
- 虚拟机默认从正在运行的 `prl_vm_app` 进程的 `--vm-name` 参数解析；也可用 `--vm` 指定。
- 存根源从 `~/Applications (Parallels)/<标识> Applications.localized/Windows PowerShell.app` 查找，优先选 `AppParams.pva` 中 `VM Name` 匹配的那个。
- 存根工作副本为 `/tmp/pemb-<虚拟机>.app`。每次执行前会结束同路径的旧 `WinAppHelper` 进程，否则 `open` 只激活旧实例，批处理不会重跑。

## 子命令

### `probe`

只读探测，返回当前虚拟机、可用传输方式、`prlctl` 是否可登录、存根源、共享根。

```
bin/guest-run probe --human
```

### `run`

执行共享目录中的批处理。批处理必须自己写日志并输出结束标记。

```
bin/guest-run run \
  --bat /Users/<用户>/work/<工程>/iar/cli_build.bat \
  --log /Users/<用户>/work/<工程>/iar/cli_build.log \
  --marker "CLI BUILD END" \
  --timeout 240 --human
```

| 参数 | 说明 |
|---|---|
| `--bat` | 批处理的 Mac 路径，必须可执行且为 CRLF 换行 |
| `--log` | 远端写入、本机轮询的日志路径；执行前会清空，避免命中上次残留标记 |
| `--marker` | 日志中的结束标记，出现即认为完成 |
| `--timeout` | 等待秒数，默认 180 |
| `--lock-scope` | `device`（默认）/ `vm` / `none` |
| `--lock-key` | 显式锁名，例如 J-Link 序列号 |
| `--lock-timeout` | 等锁秒数，默认 900；`0` 表示不排队、立即失败 |
| `--job-id` | 任务标识，默认自动生成；用于日志留档与临时批处理命名 |
| `--log-mode` | `exact`（默认，用给定路径）/ `unique`（加 job 后缀） |
| `--dry-run` | 只输出计划，不复制存根、不取锁、不启动虚拟机程序 |
| `--human` | 输出单行摘要，否则输出 JSON |

退出码从日志中最后一个 `rc=` 或 `*_EXIT=` 解析；标记出现且退出码为空或 0 视为成功。

### `exec`

把一条 Windows 命令包装成日志同目录下的 `pemb_exec_<job>.bat`，再复用 `run` 的通道逻辑。适用于探测与一次性命令，不适合长流程。锁参数与 `run` 相同。

```
bin/guest-run exec --command "echo ok" --log /Users/<用户>/work/<工程>/iar/probe.log --human
```

### `status`

只读查看锁占用与排队，不取锁、不影响正在运行的任务。

```
bin/guest-run status --human
bin/guest-run status --key dev-Win11_M7
bin/guest-run status --vm Win11_M7
```

## 返回字段

默认输出 JSON：

| 字段 | 含义 |
|---|---|
| `ok` | 是否成功；`--dry-run` 时为 `false`，但退出码恒为 0 |
| `transport` | 实际使用的通道 |
| `vm` | 虚拟机名称 |
| `job_id` | 本次任务标识 |
| `lock_key` / `lock_scope` | 使用的锁名与粒度；`none` 时为 `null` |
| `lock_wait_ms` | 等锁耗时 |
| `bat` / `bat_unc` | 批处理的 Mac 路径与 UNC 路径 |
| `log` / `log_base` / `log_unc` | 实际日志路径、调用方给的原始路径、UNC 路径 |
| `marker` | 等待的结束标记 |
| `exit_code` | 远端退出码，可能为空 |
| `duration_ms` | 耗时 |
| `stdout_tail` | 日志尾部最多 4000 字符 |
| `error` | 失败原因 |
| `dry_run` / `plan` | 是否为干运行及将要执行的动作 |

进程退出码：成功 `0`，失败 `1`，等锁超时 `2`，`--dry-run` 恒为 `0`。`3` 保留给「等待人工确认超时」，由调用方自行使用。

## 已知限制

- `stub` 通道无法取得远端进程的标准输出，只能依赖日志文件，因此批处理必须写日志并输出结束标记。
- 共享应用存根不转发命令行参数，`open --args`、`--command` 之类写法无效；唯一可靠入口是 `APP Path` 指向批处理。
- `prlctl` 分支的批处理路径仍为 UNC，尚未验证；若失败，改为在同步通道里也生成盘符化包装。
- 工具不负责判断动作是否有副作用。烧录确认与回读校验属于调用方与 `references/safety.md` 的职责。
- 锁只在同一台 Mac、同一个 `PEMB_HOME`（默认 `~/.pemb`）内有效；跨机器共享虚拟机时需要额外的分布式锁。
- 票号保证先到先得，但取锁失败的瞬间不做自动重试；需要排队就依赖 `--lock-timeout` 的阻塞等待，不要在外层写循环重试。
- 日志可能含 GBK 中文，读取时按替换策略解码，不影响标记与退出码判定。

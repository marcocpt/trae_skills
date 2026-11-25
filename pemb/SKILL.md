---
name: pemb
description: 当任务需要在 macOS 上通过 Parallels 的 Windows 虚拟机编译嵌入式工程、烧录固件或回读校验时使用；尤其出现 cmd.exe 不支持 UNC 当前目录、IAR 预构建命令失败、prlctl 登录失败、cspybat 参数报错、J-Link 连接确认等症状时。覆盖 IAR EWARM、J-Link、AC7840x，以及其它工具链与烧录器的扩展场景。
---

# Parallels 嵌入式构建与烧录

## 概述

把「进入 Windows 虚拟机执行命令」与「具体怎么编译、怎么烧录」分开。前者由 `bin/guest-run` 统一负责，后者按工具链选择配方。新增芯片或烧录器时增加配方，不要另写一套虚拟机通道。

## 何时使用

- 工程位于 Mac 共享目录，由 Windows 侧工具链构建；
- 需要命令行编译、下载固件、回读校验或探测调试器；
- 需要判断该用哪套工具链、哪个烧录器。

不适用于：Windows 原生构建、纯 Mac 侧工具链、与虚拟机无关的任务。

## 执行顺序

1. 运行 `bin/guest-run probe` 确认虚拟机、通道与共享根。
2. 按任务意图选配方，见 [references/recipes.md](references/recipes.md)。
3. 编译与探测可直接执行；**烧录类动作必须先向用户明确确认**，确认后先用 `--dry-run` 检查命令，再执行。
4. 用日志结束标记判断完成，用退出码判断成败；烧录必须回读校验。
5. 失败先查 [references/gotchas.md](references/gotchas.md)，不要靠改工程配置试错。

## 多 Agent 并发

虚拟机、J-Link 与目标板都是独占资源。`bin/guest-run` 内置独占锁：同一设备上只允许一个任务在跑，其余任务自动排队，先到先得。不需要调用方自己协调。

- 锁在 `run` / `exec` 内自动获取，`probe` 与 `--dry-run` 不取锁。
- 等锁默认上限 900 秒，可用 `--lock-timeout` 调整；`0` 表示不排队、立即失败。
- 等锁超时退出码为 `2`，调用方应报告「设备被占用」，**不得立即重试烧录**。
- 烧录的确认必须发生在**拿到锁之后**：排队期间那句确认可能已经过期（板子可能被换、固件可能被重编）。确认超时就放弃本次任务，不要一边占着锁一边等人。
- 需要多块板并行时，用 `--lock-key` 给每台设备一个独立锁名（例如 J-Link 序列号），否则默认按虚拟机串行。
- 查看当前谁在占用、队列多长：`bin/guest-run status --human`。

细节见 [references/guest-run.md](references/guest-run.md) 的「并发与排队」一节。

## 红线

- 烧录会擦写芯片 Flash，未经用户明确确认不得执行；不得援引「上次已确认」跳过。
- 不得绕过 `bin/guest-run` 直接 `open` 存根或直接调用 `cspybat`、`JLink.exe`：绕过就拿不到独占锁，会打断别的 Agent 正在进行的烧录。
- 不得把 UNC 路径直接交给需要当前目录的命令；工程文件路径本身也必须换成盘符路径。
- 不得因 `prlctl` 报错就放弃，必须回退到存根通道，或明确报告阻塞。
- 不得在未回读校验的情况下宣称烧录成功。
- 不得擅自改写用户工程里的路径配置来规避通道问题。

## 按需加载

| 文件 | 何时打开 |
|---|---|
| [references/guest-run.md](references/guest-run.md) | 调用通道、排查回退、查看返回字段时 |
| [references/recipes.md](references/recipes.md) | 选择编译或烧录配方、扩展新芯片与新烧录器时 |
| [references/gotchas.md](references/gotchas.md) | 出现报错、行为不符预期时 |
| [references/safety.md](references/safety.md) | 涉及擦写、复位、擦除等有副作用动作时 |
| [ROADMAP.md](ROADMAP.md) | 查看架构决策记录与今后待办时 |

## 快速参考

| 意图 | 命令 |
|---|---|
| 探测通道 | `bin/guest-run probe --human` |
| 执行批处理 | `bin/guest-run run --bat <批处理> --log <日志> --marker <结束标记> --timeout 240 --human` |
| 执行单条命令 | `bin/guest-run exec --command "echo ok" --log <日志> --human` |
| 只检查计划 | 在 `run` 或 `exec` 后加 `--dry-run` |
| 强制通道 | 加 `--transport prlctl` 或 `--transport stub` |
| 查看谁在占用设备 | `bin/guest-run status --human` |
| 不排队、占用即失败 | 加 `--lock-timeout 0` |
| 多设备并行 | 加 `--lock-key <J-Link 序列号>` |

默认输出 JSON，便于脚本与持续集成消费；`--human` 输出单行摘要。退出码：成功 `0`，失败 `1`，等锁超时 `2`，`--dry-run` 恒为 `0`。

## 常见错误

把「虚拟机里能打开某个程序」当成「命令已执行」。共享应用存根不会转发命令行参数，必须把 `APP Path` 指向一个真实批处理，再由批处理写日志。另一个常见错误是只看 `cspybat` 的退出码就宣布烧录成功，缺少回读比对。

# 配方决策树

配方回答「这个芯片用什么编译、这个烧录器用什么命令」。它不改变 `bin/guest-run` 的通道逻辑。新增支持时优先加配方，不要新增顶层流程。

## 编译

| 工具链 | 入口 | 关键点 |
|---|---|---|
| IAR EWARM | `IarBuild.exe <工程.ewp> -build <配置>` | 必须先用 `pushd` 把 UNC 共享映射成盘符，并把**盘符路径的工程文件**传给 `IarBuild.exe`；预构建命令依赖的 Python 需在 PATH 中 |
| Keil MDK | `UV4.exe -b <工程.uvproj> -o <日志>` | 待验证；日志编码与返回值语义需单独确认 |
| ChessDE | 命令行入口待确认 | 虚拟机内装有 `ChessDE P-2019.09a`，先查其构建参数 |
| GCC / Make | `make -C <目录> <目标>` | 待补；注意交叉编译器路径与 Windows 侧 shell 选择 |

选型依据：工程目录里的工程文件后缀（`.ewp`、`.uvproj`、`.prx`、`Makefile`）优先于用户口头描述。同一工程存在多个工具链文件时先问用户。

### 当前已实现：IAR EWARM

`DCM_CMT2300A` 的 Debug 配置，`iar/cli_build.bat` 负责：

1. `pushd "\\Mac\Home\...\iar"`，得到形如 `X:\work\...\iar` 的盘符路径；
2. 在 `C:\Program Files\IAR Systems\Embedded Workbench*\common\bin` 下找 `IarBuild.exe`；
3. 必要时把 `C:\Users\<用户>\AppData\Local\Programs\Python\Python314` 加入 PATH，供预构建的 `buildConfig.py` 使用；
4. 用盘符路径调用 `IarBuild.exe -build Debug`，日志写入 `iar/cli_build.log`；
5. 输出 `CLI BUILD END rc=<退出码>` 作为结束标记。

产物为 `Debug/Exe/DCM.out` 与 `DCM.hex`。已知结果：0 个错误、61 个既有警告。

## 烧录

| 烧录器 | 入口 | 关键点 |
|---|---|---|
| J-Link 经 C-SPY | `cspybat -f <通用配置> --download_only --timeout <毫秒> --backend -f <驱动配置>` | `--download_only` 是前端参数，必须在 `--backend` 之前；配置里 `VerifyDownload=1` |
| J-Link Commander | `JLink.exe -NoGui 1 -ExitOnError 1 -CommanderScript <脚本>` | 只读探测、回读、独立下载都可用；脚本命令 `ShowEmuList`、`connect`、`savebin`、`q` |
| JFlash | `JFlash.exe` 的命令行参数待确认 | 适合量产，需单独验证 |
| ST-Link | `STM32_Programmer_CLI` | 待补；注意连接模式与擦除范围 |
| CMSIS-DAP | pyOCD | 待补 |
| 串口 bootloader | 项目里 `python/ylSerial.py` 是现成线索 | 待补；注意串口占用与波特率 |

### 当前已实现：J-Link

`iar/flash_probe.bat`（只读探测）、`iar/flash.bat`（下载）、`iar/flash_verify.bat`（回读）三段：

1. 探测输出 `Connection: USB, Serial number: ...`，退出码 0 才继续；
2. `cspybat --download_only` 退出码 0，并确认 `iar/cspycomm.log` 时间戳更新；
3. 回读 `0x00000000` 起 256 字节，与 `DCM.hex` 前 256 字节逐字节比对。

芯片 `AC78406LGLA`，接口 SWD，Flash loader `FlashAC7840xxGLA.board`。J-Link 侧需 `VTref` 正常、能识别 Cortex-M4，否则视为目标板未上电或未连接。

### 端到端验证证据

- `DCM_CMT2300A`：2026-11-09 首次打通（IarBuild rc=0 + cspybat 下载 + 回读一致）。
- `YLY008`（AC7840x）：2026-11-23 全流程复验通过——IarBuild Debug 0 错误/336 既有警告；cspybat `--download_only` 烧录；回读 0x0 起 256 字节与 hex 逐字节一致（md5 28887810d85a2650d59385f6d2da65ef）。注意该项目 bat/jlink/settings 均未入库（.gitignore），**新建 worktree 必须复制一套并校对 ROOT 与 `general.xcl` 内嵌镜像路径**，否则会静默烧入别的 worktree 的旧镜像（见 gotchas）。

## 注册表草案（待落地）

新增芯片或烧录器时，用注册表代替脚本分支：

```yaml
chips:
  AC78406LGLA:
    build: iar-ewarm
    config: Debug
    flash: jlink-cspy
    device: AC78406LGLA
programmers:
  jlink:
    vidpid: "1366:0101"
    vm: Win11_M7
    recipe: jlink-cspy
    verify: readback
```

`vm` 与 `vidpid` 必须显式记录：换烧录器真正的麻烦是 USB 直通到哪台虚拟机，这与命令通道是两件事。缺少直通时应只读报错，不要静默改用别的设备。

## 新增配方的步骤

1. 在 `references/gotchas.md` 登记该工具链已知的报错与限制；
2. 写批处理：使用 `pushd` 得到盘符路径，日志写到共享目录，末尾输出固定结束标记与退出码；
3. 用 `bin/guest-run run --dry-run` 检查路径与计划；
4. 先跑只读探测，再做有副作用动作，并保留日志；
5. 在注册表加一行，在 `SKILL.md` 的快速参考里只加一句入口，不复制完整参数；
6. 把验证结果补进 `ROADMAP.md` 的验证证据。

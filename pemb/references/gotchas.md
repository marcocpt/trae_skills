# 已确认的故障与修复

以下条目都来自真实环境验证。遇到报错时先在这里对照，再动手改脚本或工程配置。

| 症状 | 根因 | 修复 |
|---|---|---|
| `FAILED: Pre-build command`，并提示 CMD 不支持将 UNC 路径作为当前目录 | 工程从 `\\Mac\Home\...` 打开，IAR 自动拼出 `cmd.exe /C "cd <UNC> && <预构建命令>"`，`cd` 失败后 `&&` 短路 | 批处理里用 `pushd` 把共享映射成盘符，并把**盘符路径的工程文件**传给构建工具 |
| 只把工作目录换成盘符，预构建仍失败 | IAR 的 `$PROJ_DIR$` 来自工程文件参数，仍是 UNC | 传给 `IarBuild.exe` 的 `.ewp` 路径也必须是盘符路径 |
| `Misplaced frontend option(s) found in backend section: --download_only` | `--download_only` 是 `cspybat` 前端参数，被放在 `--backend` 之后 | 移到 `--backend` 之前；该错误只打印用法就退出，不会写 Flash |
| `Login failed: Unable to connect to Parallels Service` | dispatcher 服务拒绝命令行登录；socket 可连但认证失败 | 回退到共享应用存根通道；修复服务需 `sudo launchctl start com.parallels.desktop.launchdaemon` 或重启 Parallels Desktop |
| `prlexec error: specified VM doesn't exist` | 脚本把 `prlctl status` 的失败误判为虚拟机不存在 | 不要据 `prlexec` 的这条报错下结论，用 `pgrep -fl prl_vm_app` 直接看运行中的虚拟机 |
| `open -a <存根> --args ...` 打开交互式窗口，命令没执行 | 共享应用存根不转发命令行参数 | 改写存根 `Contents/Resources/AppParams.pva` 的 `APP Path`，指向真实批处理 |
| 第二次 `open` 存根没有重跑批处理 | 同路径的旧 `WinAppHelper` 进程还在，`open` 只激活它 | 先按精确路径 `pkill -f`，再复制并改写存根 |
| `.bat` 双击在 Mac 侧被编辑器打开 | Launch Services 把 `.bat` 关联到了 Mac 应用 | 不要用 `open <批处理>`，统一走 `bin/guest-run` |
| 图形界面自动化报权限违例 | 辅助功能与自动化权限未授予 | 不依赖点击，用文件与日志通信 |
| IAR 图形界面仍报预构建失败 | 工程仍从 UNC 路径打开 | 命令行通道不受影响；图形界面需映射网络盘并从盘符打开工作区 |
| 构建日志里中文乱码 | Windows 侧输出为 GBK，按其它编码显示 | 只依赖英文标记与退出码判定，不解析中文 |
| 批处理行为异常或只执行第一行 | 换行是 LF | 写成 CRLF |
| 预构建提示找不到 Python | Windows 侧 Python 不在 PATH | 在调用构建工具前把 `C:\Users\<用户>\AppData\Local\Programs\Python\Python314` 加入 PATH |
| J-Link 连接失败或被占用 | 图形界面的调试会话独占 J-Link | 先只读探测，占用时先关闭图形界面会话 |
| 误以为烧录成功 | 只看了 `cspybat` 退出码 | 退出码 0 之外还要看 `cspycomm.log` 是否更新，并回读比对 |
| 烧进去的是别的 worktree 的旧镜像 | `settings/*.general.xcl` 内嵌上一次 IAR 图形界面会话的镜像绝对路径；多 worktree 场景下会指向别的 worktree | 烧录前检查 `general.xcl` 第 5 行镜像路径是否指向本 worktree；cspybat 烧错镜像同样 exit 0 且无下载输出，只有回读比对能拦住。多 worktree 时建议为每个 worktree 复制一套 bat+xcl 并校对路径（UNC `\\Mac\Home\...` 与盘符 `Z:\Users\...` 均可） |
| 两个 Agent 同时烧录，其中一个的批处理被中途打断 | 存根通道固定路径 `/tmp/pemb-<虚拟机>.app`，启动前 `pkill` 同路径旧进程，没有独占锁时后到者会杀掉先到者 | 统一走 `bin/guest-run`（`run`/`exec` 默认 `--lock-scope device` 已串行化）；不要绕过通道直接 `open` 存根或调 `cspybat` |
| `guest-run` 返回退出码 2，提示「等待 ... 锁超时」 | 设备正被另一个任务占用，等锁超过 `--lock-timeout` | 报告「设备被占用」并说明占用者（`bin/guest-run status --human`），**不要立即重试烧录**；确需排队就加大 `--lock-timeout` |
| 自己的日志被别的任务清空或内容对不上 | 多个任务共用同一个 `--log` 路径，执行前会清空 | 同一工程并行时用 `--log-mode unique` 各自留证据；`exact` 模式已把上一份留档为 `<日志>.<job>.prev` |
| `status` 显示 `stale=1` | 持有者进程崩溃，`holder` 记录残留；flock 已由内核释放 | 直接重试即可，锁会在毫秒级拿到；不要手工删 `~/.pemb` 下的锁文件 |
| 临时批处理 `pemb_exec.bat` 被另一个任务覆盖 | 旧版本用固定文件名 | 现已按任务命名为 `pemb_exec_<job>.bat`；若日志里仍出现固定名，说明调用的是旧版 `guest-run` |

## 判定顺序

1. 先分清失败发生在**通道**（虚拟机里根本没执行）还是**工具**（执行了但报错）。日志不存在或没有结束标记，通常是通道问题。
2. 退出码为 `2` 时先看 `bin/guest-run status --human`：是排队超时，不是通道或工具失败，重试之前先确认占用者是否已结束。
3. 通道问题查 `bin/guest-run probe` 的输出，看实际用了哪种传输方式。
4. 工具问题看日志里的退出码与 `references/recipes.md` 的参数要点。
5. 不要通过改用户工程配置来绕开通道问题；命令行侧用盘符路径即可。

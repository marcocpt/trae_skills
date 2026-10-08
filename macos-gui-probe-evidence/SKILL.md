---
name: "macos-gui-probe-evidence"
description: "当需要为 macOS 原生 App（尤其 SwiftUI + AppKit 混排）的输入/性能类缺陷取得真实路径证据，而 XCUITest 合成事件不可靠时使用。覆盖：合成滚轮/鼠标事件并判定设备档位、应用内 env-gated 探针取「App 实际收到什么」、NSHostingView 量单帧重算成本、交互卡顿的主线程阻塞片与相对预算。触发词：XCUITest 合成事件不生效、真机取证、事件注入、SwiftUI 卡顿测量、点击延时严重、per-tick 成本、主线程阻塞、hasPreciseScrollingDeltas。"
---

# macOS GUI 真实路径取证（XCUITest 不可靠时的替代手法）

用于「UI 行为/性能缺陷必须拿真实路径证据，但 XCUITest 合成事件在本机不可用」的场景。
本手法在 Macim（菜单栏 App + SwiftUI 工作台）上实证有效。

## 何时用

- XCUITest 报 `Failed to synthesize event: ... is not foreground`，或事件投递后**无可见效果**；
- 需要区分「事件没送到」与「送到了但判定错了」；
- 需要量化「一次状态变更导致多少视图重算」，而不满足于「看起来卡」。

**先做基线对照**：把 XCUITest 用例跑在**基线提交**上（`git show <base>:<file> > <file>` 临时还原）。
若基线同样失败，则属既有 fixture 缺陷，不要把失败归因于本次改动，也不要盲改用例。

## 手法一：合成事件并判定设备档位

```swift
// 触控板档：units: .pixel  ⇒ hasPreciseScrollingDeltas == true
// 物理滚轮档：units: .line ⇒ hasPreciseScrollingDeltas == false
let e = CGEvent(scrollWheelEvent2Source: CGEventSource(stateID: .hidSystemState),
                units: .line, wheelCount: 2, wheel1: 10, wheel2: 0, wheel3: 0)!
e.location = screenPoint                 // 屏幕坐标（左上原点）
e.flags = command ? .maskCommand : CGEventFlags()   // ★ 必须显式赋空
e.post(tap: .cghidEventTap)
```

- 先写 10 行探针脚本回读验证：`NSEvent(cgEvent: e)?.hasPreciseScrollingDeltas`。
  `.line` + `scrollWheelEventIsContinuous = 1` 也是 `true`；默认 0 才是物理滚轮档。
- ★ **`event.flags` 必须显式赋值**：不赋值时会沿用上一次投递留下的修饰键，
  实测出现「本应无 ⌘ 的事件带着 ⌘ 到达」。
- 合成事件走 `cghidEventTap` 要求目标 App **在前台**；先 `NSRunningApplication.activate()` 并等待。
- 窗口坐标：`CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)`，
  按 `kCGWindowOwnerPID` 过滤目标进程，取面积最大的窗口。
- 键盘同理：`CGEvent(keyboardEventSource:virtualKey:keyDown:)`；键码如 `25` = `9`、`36` = Return。

## 手法二：应用内 env-gated 探针（回答「App 到底收到什么」）

在事件入口与应用处各写一行，经环境变量指定日志文件；**取证完成后必须移除**：

```swift
func probeLog(_ text: String) {
    guard let path = ProcessInfo.processInfo.environment["<APP>_PROBE_LOG"] else { return }
    let line = String(format: "%.3f %@\n", CFAbsoluteTimeGetCurrent(), text)
    if let h = FileHandle(forWritingAtPath: path) {
        h.seekToEndOfFile(); h.write(Data(line.utf8)); try? h.close()
    } else { try? line.write(toFile: path, atomically: true, encoding: .utf8) }
}
```

记录内容建议：**事件原始事实**（`hasPreciseScrollingDeltas` / 修饰键 / 增量）+ **判定结果**（意图）+ **应用后的状态**。
时间戳同时给出两件事：

- 入口→应用的**处理耗时**（同一条事件的相邻两行之差）；
- **相邻 tick 间隔**：连续投递 N 个事件（如 3 ms 间隔）后看应用侧时间戳跨度，
  跨度 ≫ 投递跨度即说明主线程饱和 / 输入积压——这就是「延时」的直接证据。

若 App 有「测试根目录」之类的环境变量能自动打开目标窗口，优先用它，避免驱动菜单栏 UI。

## 手法三：SwiftUI 单帧重算成本基准

```swift
let hosting = NSHostingView(rootView: view)
let window = NSWindow(contentRect: rect, styleMask: [.borderless], backing: .buffered, defer: false)
window.isReleasedWhenClosed = false      // ★ 非 App 进程里 close 会 over-release（实测 SIGSEGV）
window.contentView = hosting
window.orderBack(nil)

func pump() { hosting.layoutSubtreeIfNeeded(); hosting.displayIfNeeded(); RunLoop.current.run(until: Date()) }

// 对照：不变更状态只 pump（应≈0）→ 再变更状态后 pump（差值即重算成本）
```

铁律：

1. **每项测量自建 view model + hosting view，并在结束时拆窗口**。
   多个 hosting view 同时观察同一 `ObservableObject` 时，一次状态变更会让它们**一起**重算，
   互相污染计时——实测把同一项从 8.4 ms 抬到 49 ms。
2. **必须加最小对照**：一个「同样订阅但只渲染一个 Text」的探针视图。
   若它 ≈0 而目标视图很大，成本确实来自视图树；若它同样大，则是固定提交开销。
3. 逐项分开跑（独立进程最稳），不要在一个测试方法里连续量多个视图。
4. 结论按「60 Hz = 16.67 ms/帧」换算，明确写出「超预算几倍 ⇒ 上限多少 fps」。

## 手法四：交互卡顿的主线程阻塞片 + 相对预算

用于「点一下按钮卡一下」这类**偶发但可感知**的卡顿（不是逐帧高频路径，手法三的量单帧成本不适用）。

```swift
// 排空主循环，返回**最长单次阻塞片**（= 用户感知的那一下卡顿）
func spinMaxSlice(_ duration: TimeInterval) -> TimeInterval {
    var maxSlice: TimeInterval = 0
    let deadline = Date().addingTimeInterval(duration)
    while Date() < deadline {
        let start = Date()
        RunLoop.main.run(until: Date().addingTimeInterval(0.001))
        maxSlice = max(maxSlice, Date().timeIntervalSince(start))
    }
    return maxSlice
}
```

铁律：

1. **必须建「同幅度纯布局变化」对照组**，不要只看绝对值。
   例：测「收起侧栏」→ 对照「窗口整体缩窄 300pt」（画布同样 -300pt，但不涉及被测机制）。
   绝对值受机器负载影响极大（同一次运行内对照组可在 70～150ms 抖动），
   而「被测 ≤ 对照 × 1.5 + 60ms」这类**相对预算**才稳定可守。
2. **每档跑三轮取中位**：单轮 `max` 对抖动极敏感，一次偶发调度就能翻倍。
3. **规模必须对齐真机**，别用夹具的小规模下结论：
   先量化真机数据规模（本次是 `capture_manifest.json` 的 **771 屏**、单屏 Region p50=40/p90=75），
   再按中位档 + 压力档两组参数化。
4. 结论写成「被测 vs 对照」，而不是「多少 ms」——前者才说明「这成本是机制引入的，还是布局本身固有的」。

**实测样例（Macim GT 侧栏显隐）**：条件分支销毁 / 重建 show ≈ 316–400ms；
常驻 + 占位宽度 0 show ≈ 76ms / hide ≈ 64ms；同幅度窗口缩放对照 ≈ 108ms
⇒ 修复后切换成本已低于对照，回到「画布变宽」的固有代价。

## 常见真凶清单（SwiftUI + 高频输入）

- **用条件分支销毁 / 重建大面板来做显隐**：`if isVisible { panel }` 会让整棵子树
  （长列表 + 每行 `.help()` 提示）在每次显示时全量重建。真机上「列表常驻时无感」的代价，
  一旦改成可收起就变成**每次点击都付一遍**。
  修法：**面板常驻视图树，显隐只改占位宽度**——内层 `frame(width:)` 钉死面板自身宽度
  （内部布局与文本截断命中缓存、零重排），外层取「宽度 / 0」并配 `clipped()`、
  `allowsHitTesting(_:)`、`accessibilityHidden(_:)`（收起后不可见 / 不可点 / AX 查不到）。
  注意口径差别：AX 观测点此时是「查不到」而非「不存在」；**也因此不会破坏
  「离屏行 AX 节点常驻」这类既有 XCUITest 依赖**，比把列表改 `LazyVStack` 更安全。
- 高频状态（视口 / 拖拽偏移 / 光标位置）与**整窗状态同住一个 `ObservableObject`**：
  每 tick 重算整棵树。修法：拆出专用 store，只让直接消费者订阅。
- `NSViewRepresentable` 的 `updateNSView` 里逐元素重建（建字体、量文字、整表重挂 `subviews`）：
  只在**集合变化**时重挂，其余只改 frame，并把可缓存量（文字尺寸）缓存起来。
- 非精确增量设备（物理滚轮）的 delta 单位是**行**，不是点：
  按点直接相加会得到 1 pt/档 ⇒ 观感「逐字跳 / 有延时」。按行高折算。
- 用派生属性（`filter` / `sorted` / `map`）在 `body` 里反复计算：每次访问都新建数组。

## 收尾

- 探针代码、临时脚本**不得进入提交**；证据写进仓库既有约定位置（如 `debug-logs/`）。
- 无法验证的测试**不要留在仓库里**：宁可不加，也不引入可能变红的用例；把缺口登记到 LATER 并写清复现条件。

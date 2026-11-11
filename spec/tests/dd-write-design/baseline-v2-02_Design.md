# 视觉识别 F3.2 模板匹配设计文档

> 最后更新：2026-07-16 | 版本：v1.0

## 1. 文档说明

本文档为 F3.2 模板匹配功能的设计文档，对应需求文档 `01_Requirements.md`。需求文档定义了"做什么"（可观察行为与约束），本文档定义"怎么做"（模块划分、职责边界、数据流、状态变化、协作关系、关键类型与接口设计）。

本文档在需求允许的"实现自由度"范围内做出技术选型与架构决策；对于需求"禁止修改"的条款（识别来源类别、多尺度层级、重叠度阈值 0.5、置信度默认值 0.8、状态集合与转换规则、激活快捷键 ⌘⇧V、两阶段流程划分），本文档严格遵循，不做变更。

实现语言选用 Swift（macOS 原生），模板匹配基于系统内置的 Accelerate framework（vDSP）实现归一化互相关，不引入第三方依赖（对应 Constraints-2）。

## 2. 总体架构

### 2.1 架构分层

系统按职责分为四层：

| 层次 | 职责 | 包含模块 |
|------|------|---------|
| 控制层 | 管理视觉识别模式生命周期、状态机流转、用户输入分发 | `VisionModeController` |
| 采集层 | 屏幕画面采集与缓存 | `ScreenCaptureService` |
| 识别层 | OCR 识别、模板匹配、结果合并去重 | `OCRRecognitionEngine`、`TemplateMatchingEngine`、`CompositeRecognitionEngine` |
| 呈现层 | 字母标签管理、屏幕覆盖层渲染、点击执行 | `LabelManager`、`ScreenOverlay`、`InputElementResolver` |

辅助模块：

| 模块 | 职责 |
|------|------|
| `ConfigurationStore` | 运行时配置存储（置信度阈值等），支持即时生效 |
| `TemplateRepository` | 模板图像加载与缓存 |
| `VisualElement` | 视觉元素数据模型 |
| `RecognitionSource` | 识别来源枚举 |

### 2.2 模块依赖关系

```
VisionModeController
├── ScreenCaptureService
├── CompositeRecognitionEngine
│   ├── OCRRecognitionEngine
│   └── TemplateMatchingEngine
│       └── TemplateRepository
├── LabelManager
├── ScreenOverlay
├── InputElementResolver
└── ConfigurationStore
```

依赖方向自上而下，下层模块不反向依赖上层模块。`CompositeRecognitionEngine` 是识别层的协调者，`VisionModeController` 是整体流程的协调者。

## 3. 模块划分与职责边界

### 3.1 VisionModeController（视觉模式控制器）

**职责**：

- 持有并驱动识别流程状态机（对应 FR-011）
- 监听激活快捷键 ⌘⇧V（对应 FR-001、Constraints-7）
- 协调采集 → 识别 → 呈现 → 输入 → 执行 的全流程
- 在状态转换时调用相应模块，确保转换规则严格符合 FR-011

**不负责**：

- 具体识别算法（由识别层承担）
- 标签编号算法（由 `LabelManager` 承担）
- 屏幕渲染细节（由 `ScreenOverlay` 承担）

**关键接口（示意）**：

```swift
protocol VisionModeControlling {
    func handleActivateShortcut()          // 用户按下 ⌘⇧V
    func handleDeactivateShortcut()        // 再次按下 ⌘⇧V
    func handleUserInput(label: Character) // 用户输入字母
    func handleTimeout()                   // 超时事件
}
```

### 3.2 ScreenCaptureService（屏幕采集服务）

**职责**：

- 采集主显示器屏幕画面（本期仅支持主显示器，对应 Out of Scope）
- 输出统一格式的画面数据（像素缓冲 + 尺寸信息）
- 提供画面缓存，供识别阶段复用

**不负责**：

- 多显示器采集（未来扩展）
- 画面预处理（缩放由模板匹配引擎内部按尺度处理）

### 3.3 OCRRecognitionEngine（OCR 识别引擎）

**职责**：

- 第一阶段：文本区域检测，输出候选元素的位置矩形（对应 FR-010 第一阶段）
- 第二阶段：对候选元素的区域识别其文字内容（对应 FR-010 第二阶段）
- 输出的视觉元素 `source` 标记为 `.ocr`（对应 FR-007）

**不负责**：

- 与模板匹配结果合并去重（由 `CompositeRecognitionEngine` 承担）
- 模板匹配相关任何逻辑

### 3.4 TemplateMatchingEngine（模板匹配引擎）

**职责**：

- 在原始尺寸、半尺寸、四分之一尺寸三个尺度下执行模板匹配（对应 FR-003、Constraints-5）
- 采用归一化互相关方法衡量相似度（对应 FR-004）
- 按置信度阈值过滤候选（对应 FR-005），阈值从 `ConfigurationStore` 读取，运行时生效（对应 NFR-006）
- 汇总三个尺度的匹配结果，输出视觉元素，`source` 标记为 `.template`（对应 FR-007）

**不负责**：

- 模板图像库的增删管理（Out of Scope）
- 离线训练（Out of Scope）
- OCR 文字识别

**关键接口（示意）**：

```swift
protocol TemplateMatchingEngining {
    func match(screen: ScreenFrame,
               templates: [TemplateImage],
               confidenceThreshold: Double) -> [VisualElement]
}
```

### 3.5 CompositeRecognitionEngine（组合识别引擎）

**职责**：

- 并行调度 OCR 引擎与模板匹配引擎（对应 FR-002、NFR-003）
- 收集两路结果后按重叠度 0.5 合并去重（对应 FR-006、Constraints-4）
- 去重规则对两类来源一视同仁，不偏袒任一来源（对应 FR-006）
- 输出合并后的视觉元素列表

**不负责**：

- 字母标签编号（由 `LabelManager` 承担）
- 状态机流转（由 `VisionModeController` 承担）

**关键接口（示意）**：

```swift
protocol CompositeRecognitionEngining {
    func recognize(screen: ScreenFrame) async -> [VisualElement]
}
```

### 3.6 LabelManager（标签管理器）

**职责**：

- 为合并去重后的视觉元素分配字母标签（对应 FR-008）
- 字母标签在 OCR 来源与模板匹配来源之间统一编号，不区分来源类别显示样式（对应 FR-008）
- 维护"屏幕区域 ↔ 字母标签"的映射，支持按区域查询（对应 FR-009）
- 在每次新一轮识别后重置映射

**不负责**：

- 标签样式自定义（Out of Scope）
- 屏幕渲染（由 `ScreenOverlay` 承担）

**关键接口（示意）**：

```swift
protocol LabelManaging {
    func assignLabels(to elements: [VisualElement]) -> [LabeledElement]
    func label(for region: CGRect) -> Character?   // 对应 FR-009
    func element(for label: Character) -> VisualElement?
    func reset()
}
```

### 3.7 ScreenOverlay（屏幕覆盖层）

**职责**：

- 在屏幕最上层渲染字母标签（对应 FR-008）
- 识别完成后 150ms 内呈现标签（对应 NFR-005）
- 在停用流程中隐藏标签

**不负责**：

- 标签编号逻辑
- 点击事件执行（由 `InputElementResolver` 承担）

### 3.8 InputElementResolver（输入元素解析器）

**职责**：

- 接收用户输入的字母，通过 `LabelManager` 解析对应视觉元素
- 在该元素位置执行点击操作（对应 FR-012）
- 点击在 100ms 内执行（对应 NFR-005）

**不负责**：

- 字母 → 元素的映射维护（由 `LabelManager` 承担）

### 3.9 ConfigurationStore（配置存储）

**职责**：

- 存储模板匹配置信度阈值，默认 0.8（对应 FR-005、Constraints 禁止修改默认值）
- 支持运行时修改并即时生效（对应 NFR-006）
- 提供阈值读取接口供 `TemplateMatchingEngine` 每次匹配时读取

**不负责**：

- 重叠度阈值存储（固定 0.5，不可配置，对应 Constraints-4）
- 尺度层级配置（固定三级，对应 Constraints-5）

### 3.10 TemplateRepository（模板仓库）

**职责**：

- 加载预置模板图像
- 缓存模板图像及其多尺度缩放版本（对应 NFR-002 内存预算内的缓存）
- 提供模板列表查询

**不负责**：

- 模板增删管理（Out of Scope）
- 模板导入导出（Out of Scope）

## 4. 核心数据结构

### 4.1 VisualElement（视觉元素）

```swift
struct VisualElement {
    let id: UUID
    let rect: CGRect              // 屏幕坐标
    let source: RecognitionSource // 对应 FR-007
    let content: String?          // OCR 来源携带文字；模板来源为 nil
    var label: Character?         // 由 LabelManager 分配，初始为 nil
}
```

### 4.2 RecognitionSource（识别来源）

```swift
enum RecognitionSource {
    case ocr       // OCR 来源
    case template  // 模板匹配来源
    case coreML    // 机器学习模型来源（预留，本次不启用，对应 FR-007、Constraints-3）
}
```

三类取值不可增减（对应 Constraints-3）。

### 4.3 ScreenFrame（屏幕画面）

```swift
struct ScreenFrame {
    let buffer: CVPixelBuffer  // 像素缓冲
    let size: CGSize           // 原始尺寸
    let timestamp: Date
}
```

### 4.4 TemplateImage（模板图像）

```swift
struct TemplateImage {
    let id: String
    let fullSize: CGImage           // 原始尺寸
    let halfSize: CGImage           // 半尺寸（预计算缓存）
    let quarterSize: CGImage        // 四分之一尺寸（预计算缓存）
}
```

多尺度版本在加载时预计算并缓存，避免运行时重复缩放（对应 NFR-001 性能要求）。

### 4.5 MatchCandidate（模板匹配候选）

```swift
struct MatchCandidate {
    let rect: CGRect
    let similarity: Double  // 归一化互相关分值，0 至 1（对应 FR-004）
    let scale: MatchScale
}

enum MatchScale {
    case original
    case half
    case quarter
}
```

## 5. 协议设计

### 5.1 识别引擎统一协议

```swift
protocol VisualRecognitionEngine {
    func recognize(screen: ScreenFrame) async -> [VisualElement]
}
```

`OCRRecognitionEngine` 与 `TemplateMatchingEngine` 均实现该协议，使 `CompositeRecognitionEngine` 能以统一方式调度两路引擎。

### 5.2 协议与模块对应关系

| 协议 | 实现者 | 调用者 |
|------|--------|--------|
| `VisualRecognitionEngine` | `OCRRecognitionEngine`、`TemplateMatchingEngine` | `CompositeRecognitionEngine` |
| `CompositeRecognitionEngining` | `CompositeRecognitionEngine` | `VisionModeController` |
| `LabelManaging` | `LabelManager` | `VisionModeController`、`InputElementResolver` |
| `VisionModeControlling` | `VisionModeController` | 快捷键监听器、输入监听器 |

## 6. 模块详细设计

### 6.1 TemplateMatchingEngine 详细设计

#### 6.1.1 多尺度匹配流程

对每个模板图像 `TemplateImage`，在三个尺度下分别执行匹配：

```
对每个 template in templates:
    对每个 scale in [.original, .half, .quarter]:
        target := screen 按 scale 缩放
        pattern := template 对应 scale 的预缓存图像
        scores := NCC(target, pattern)              // 归一化互相关
        对 scores 中每个局部极大值位置:
            候选 := 还原到原始坐标系的 rect + similarity + scale
            若 similarity >= confidenceThreshold:
                加入候选列表
汇总所有尺度的候选 → 输出
```

三个尺度的匹配相互独立，可并行执行（内部并行，与 OCR 的外部并行正交）。

#### 6.1.2 归一化互相关实现

采用 Accelerate framework 的 vDSP 实现归一化互相关：

- 将画面区域与模板均转换为单通道灰度 + 零均值归一化向量
- 利用 vDSP 的点积与归一化运算计算每个滑动位置的相似度
- 输出每个位置的相似度分值（0 至 1，对应 FR-004）

具体实现细节（是否分块、是否使用 vImageMatrixMultiply 等）由实现者根据性能测试决定，本设计不强制规定。

#### 6.1.3 置信度阈值过滤

每次匹配执行前，从 `ConfigurationStore` 实时读取当前阈值：

```
threshold := ConfigurationStore.templateConfidenceThreshold  // 默认 0.8
```

由于每次匹配都现读，阈值修改后下一次识别立即生效（对应 NFR-006），无需重启或重新激活。

#### 6.1.4 多尺度结果汇总

三个尺度可能匹配到同一区域的候选，需要在汇总阶段做尺度间去重：

- 对候选列表按相似度降序排序
- 遍历候选，若与已保留候选的重叠度 > 0.5，丢弃；否则保留
- 输出保留的候选作为模板匹配路径的结果

注意：此处的尺度间去重使用 0.5 重叠度（与跨路径去重一致），但仅作用于模板匹配内部候选；跨路径（OCR 与模板匹配）的去重由 `CompositeRecognitionEngine` 承担。

### 6.2 OCRRecognitionEngine 详细设计

#### 6.2.1 两阶段执行

```
第一阶段（文本区域检测）:
    regions := detectTextRectangles(screen)   // 输出位置矩形列表
    候选元素 := regions 映射为 VisualElement（source = .ocr, content = nil）

第二阶段（文字识别）:
    对每个候选元素:
        content := recognizeText(screen, region)
        候选元素.content := content

输出带 content 的候选元素列表
```

两阶段顺序执行，第二阶段仅作用于 OCR 路径的候选元素（对应 FR-010）。模板匹配路径无第二阶段。

#### 6.2.2 并行优化

第二阶段的文字识别可对多个候选区域并行执行（内部并行），不影响与模板匹配的外部并行。

### 6.3 CompositeRecognitionEngine 详细设计

#### 6.3.1 并行调度

采用 Swift 的 `async let` 并行绑定实现两路并行：

```swift
func recognize(screen: ScreenFrame) async -> [VisualElement] {
    async let ocrResults = ocrEngine.recognize(screen: screen)
    async let templateResults = templateEngine.recognize(screen: screen)
    let (ocr, template) = await (ocrResults, templateResults)
    return mergeAndDeduplicate(ocr: ocr, template: template)
}
```

两路执行时间相互独立，整体耗时接近较慢一路（对应 FR-002、AC-2）。

两路之间无共享可变状态（对应 NFR-003）：

- OCR 引擎不读写模板匹配引擎的任何状态
- 模板匹配引擎不读写 OCR 引擎的任何状态
- 两者各自输出独立的 `[VisualElement]`，合并阶段在主流程上同步执行

#### 6.3.2 合并去重算法

```
合并 ocr + template → combined
按相似度/置信度降序排序（OCR 元素的置信度视为 1.0，模板元素使用 similarity）
保留列表 := []
对 combined 中每个元素 e:
    与保留列表中任一元素 r 的重叠度 > 0.5:
        跳过 e（去重，对应 FR-006、Constraints-4）
    否则:
        保留 e
输出保留列表
```

重叠度计算（IoU）：

```
IoU(a, b) = 面积(a ∩ b) / 面积(a ∪ b)
```

去重规则对两类来源一视同仁（对应 FR-006）：排序时 OCR 与模板匹配元素混合排序，不因来源偏袒任一方。

### 6.4 LabelManager 详细设计

#### 6.4.1 字母标签编号策略

采用顺序编号策略：

- 可用字母集合：`a` 至 `z`（26 个），不足时扩展为大写（本期暂不扩展，元素数超过 26 时截断并记录日志）
- 按 `VisualElement` 在合并去重后列表中的顺序依次分配字母
- 不区分来源类别显示样式（对应 FR-008）

#### 6.4.2 区域查询

维护两个映射：

```swift
private var elementToLabel: [UUID: Character] = [:]
private var labelToElement: [Character: VisualElement] = [:]
private var regionToLabel: [(CGRect, Character)] = []  // 用于 FR-009 按区域查询
```

按区域查询（对应 FR-009）：遍历 `regionToLabel`，返回包含查询点或与查询区域匹配的标签。

#### 6.4.3 重置

每次新一轮识别开始前调用 `reset()`，清空所有映射，避免上一轮标签残留。

### 6.5 VisionModeController 详细设计

#### 6.5.1 状态机实现

采用"枚举 + 转换函数"方式实现状态机（对应 Decision Freedom 允许的状态机实现自由度）：

```swift
enum VisionState {
    case idle          // 待激活
    case capturing     // 采集
    case recognizing   // 识别中
    case active        // 激活
    case emptyResult   // 空结果
    case executing     // 执行中
    case deactivating  // 停用中
}
```

七个状态与 FR-011、Constraints-6 严格对应，不增减。

转换函数严格实现 FR-011 定义的转换规则，非法转换触发断言并记录错误日志。

#### 6.5.2 快捷键监听

注册全局快捷键 ⌘⇧V（对应 Constraints-7）：

- 首次按下：触发 `待激活 → 采集` 转换
- 激活态再次按下：触发 `激活 → 停用中` 转换
- 空结果态再次按下：触发 `空结果 → 待激活` 转换

#### 6.5.3 超时处理

激活状态下设置超时定时器，超时未操作触发 `激活 → 停用中` 转换（对应 FR-011）。

## 7. 数据流

### 7.1 端到端数据流

```
[用户按下 ⌘⇧V]
        │
        ▼
[VisionModeController] 状态：待激活 → 采集
        │
        ▼
[ScreenCaptureService] 采集屏幕 → ScreenFrame
        │
        ▼
[VisionModeController] 状态：采集 → 识别中
        │
        ▼
[CompositeRecognitionEngine] 并行调度
        ├──► [OCRRecognitionEngine]
        │       ├── 第一阶段：detectTextRectangles → [CGRect]
        │       └── 第二阶段：recognizeText → [VisualElement(source=.ocr)]
        │
        └──► [TemplateMatchingEngine]
                ├── 多尺度 NCC 匹配 → [MatchCandidate]
                ├── 置信度阈值过滤（从 ConfigurationStore 实时读取）
                └── 尺度间去重 → [VisualElement(source=.template)]
        │
        ▼ （await 两路结果）
[CompositeRecognitionEngine] 合并去重（IoU > 0.5）→ [VisualElement]
        │
        ▼
[VisionModeController]
        ├── 非空 → 状态：识别中 → 激活
        │       │
        │       ▼
        │   [LabelManager] 分配字母标签 → [LabeledElement]
        │       │
        │       ▼
        │   [ScreenOverlay] 渲染字母标签（150ms 内，对应 NFR-005）
        │       │
        │       ▼
        │   等待用户输入
        │
        └── 空 → 状态：识别中 → 空结果（不呈现标签，对应 AC-12）
```

### 7.2 用户输入数据流

```
[用户输入字母]
        │
        ▼
[VisionModeController] 状态：激活 → 执行中
        │
        ▼
[InputElementResolver]
        ├── [LabelManager] 查询字母 → VisualElement
        └── 在 VisualElement.rect 位置执行点击（100ms 内，对应 NFR-005）
        │
        ▼
[VisionModeController] 状态：执行中 → 激活
        │
        ▼
等待下一次输入
```

### 7.3 停用数据流

```
[用户再次按下 ⌘⇧V 或超时]
        │
        ▼
[VisionModeController] 状态：激活 → 停用中
        │
        ▼
[ScreenOverlay] 隐藏字母标签
[LabelManager] reset()
        │
        ▼
[VisionModeController] 状态：停用中 → 待激活
```

## 8. 状态变化（状态机）

### 8.1 状态集合

严格对应 FR-011、Constraints-6，七个状态：

| 状态 | 中文名 | 说明 |
|------|--------|------|
| `idle` | 待激活 | 初始状态，等待用户按下快捷键 |
| `capturing` | 采集 | 屏幕画面采集中 |
| `recognizing` | 识别中 | OCR 与模板匹配并行执行中 |
| `active` | 激活 | 字母标签已呈现，等待用户输入 |
| `emptyResult` | 空结果 | 识别无结果，等待用户再次按下快捷键 |
| `executing` | 执行中 | 用户已输入字母，点击操作执行中 |
| `deactivating` | 停用中 | 停用流程执行中 |

### 8.2 状态转换规则

严格对应 FR-011，不增减：

| 源状态 | 目标状态 | 触发条件 |
|--------|---------|---------|
| 待激活 | 采集 | 用户按下激活快捷键 |
| 采集 | 识别中 | 屏幕画面采集完成 |
| 识别中 | 激活 | 识别产生非空结果 |
| 识别中 | 空结果 | 识别无任何结果 |
| 激活 | 执行中 | 用户输入字母选择元素 |
| 执行中 | 激活 | 元素操作完成 |
| 激活 | 停用中 | 用户再次按下快捷键或超时 |
| 空结果 | 待激活 | 用户再次按下快捷键 |
| 停用中 | 待激活 | 停用流程完成 |

### 8.3 状态转换图

```
        ┌─────────────────────────────────────────────────────┐
        │                                                     │
        ▼                                                     │
    ┌────────┐  快捷键  ┌────────┐ 采集完成 ┌──────────┐         │
    │ 待激活  │─────────►│  采集   │─────────►│  识别中   │         │
    └────────┘          └────────┘          └──────────┘         │
        ▲                                     │      │           │
        │                                     │      │           │
        │                              非空结果 │      │ 空结果    │
        │                                     ▼      ▼           │
        │                                 ┌──────┐ ┌────────┐    │
        │              再次按下快捷键       │ 激活  │ │ 空结果  │    │
        │              ┌──────────────────│      │ └────────┘    │
        │              │                   └──────┘              │
        │              │                     │  │                 │
        │              │              输入字母 │  │ 再次按下/超时   │
        │              │                     ▼  ▼                 │
        │              │              ┌──────────┐                │
        │              │              │  执行中   │                │
        │              │              └──────────┘                │
        │              │                     │                     │
        │              │              操作完成 │                     │
        │              │                     ▼                     │
        │              │              ┌──────┐                     │
        │              └─────────────►│ 激活  │                     │
        │                             └──────┘                     │
        │                                  │                       │
        │                  再次按下/超时     │                       │
        │                                  ▼                       │
        │                            ┌──────────┐                  │
        │                            │  停用中   │                  │
        │                            └──────────┘                  │
        │                                  │                       │
        └──────────────── 停用完成 ─────────┘                       │
```

### 8.4 状态机实现要点

- 状态机是同步的：状态转换瞬间完成，状态本身不持有长时间任务；长时间任务（采集、识别、点击）由对应模块异步执行，完成后回调控制器推进状态。
- 非法转换防护：转换函数对未定义的 (源状态, 触发事件) 组合返回失败并记录错误日志，避免状态机进入未定义状态。
- 状态变化可观察：每次状态转换发出事件，供调试与未来扩展（如 UI 反馈）使用。

## 9. 协作关系

### 9.1 识别阶段协作

`VisionModeController` 与 `CompositeRecognitionEngine` 是主从协作：

- 控制器在 `采集 → 识别中` 转换时调用 `CompositeRecognitionEngine.recognize(screen:)`
- 组合引擎内部并行调度 OCR 引擎与模板匹配引擎
- 组合引擎返回合并去重后的 `[VisualElement]`
- 控制器根据结果是否为空，决定转换到 `激活` 或 `空结果`

OCR 引擎与模板匹配引擎之间是并行无协作关系：

- 两路引擎不直接通信
- 两路引擎不共享可变状态（对应 NFR-003）
- 仅在组合引擎层面汇合

### 9.2 呈现阶段协作

`VisionModeController`、`LabelManager`、`ScreenOverlay` 是顺序协作：

1. 控制器调用 `LabelManager.assignLabels(to:)` 分配标签
2. 控制器将带标签的元素列表传递给 `ScreenOverlay` 渲染
3. `ScreenOverlay` 在 150ms 内完成渲染（对应 NFR-005）

### 9.3 输入阶段协作

`VisionModeController`、`InputElementResolver`、`LabelManager` 是查询协作：

1. 控制器接收用户输入字母
2. 控制器调用 `InputElementResolver.resolve(label:)`
3. 解析器通过 `LabelManager.element(for:)` 查询元素
4. 解析器在元素位置执行点击
5. 控制器转换状态 `执行中 → 激活`

### 9.4 配置协作

`ConfigurationStore` 与 `TemplateMatchingEngine` 是读取协作：

- 模板匹配引擎每次匹配时从配置存储现读阈值
- 配置存储修改阈值后立即对下次读取生效
- 两者之间无锁、无缓存，靠"每次现读"保证一致性（对应 NFR-006）

### 9.5 模板仓库协作

`TemplateRepository` 与 `TemplateMatchingEngine` 是供给协作：

- 模板仓库在启动时加载并预计算多尺度模板图像
- 模板匹配引擎每次匹配时从仓库获取模板列表
- 仓库对模板图像做常驻缓存（对应 NFR-002 内存预算）

## 10. 并发设计

### 10.1 并发模型

采用 Swift Structured Concurrency（`async let` / `TaskGroup`）实现并行：

- **外部并行**：OCR 与模板匹配两路并行（对应 FR-002）
- **内部并行**：模板匹配的三尺度匹配可并行；OCR 第二阶段的文字识别可并行

### 10.2 共享状态与锁

- 两路识别引擎之间无共享可变状态（对应 NFR-003），无需锁
- `ConfigurationStore` 的阈值读写采用原子操作（如 `OSAllocatedUnfairLock` 或 actor 封装）
- `LabelManager` 的映射仅在主流程上访问（识别完成后、用户输入时），无需复杂同步
- 合并去重阶段在主流程上同步执行（对应 NFR-003），避免用户感知到的延迟抖动

### 10.3 取消与超时

- 停用流程触发时，取消正在进行的识别任务（Structured Concurrency 自动传播取消）
- 激活态超时定时器独立于识别任务，超时触发停用

## 11. 缓存策略

### 11.1 模板图像缓存

- `TemplateRepository` 在启动时加载所有模板，并预计算半尺寸、四分之一尺寸版本
- 缓存常驻，纳入 NFR-002 的 150MB 内存预算
- 模板数量与尺寸需控制，确保总缓存占用在预算内

### 11.2 屏幕画面缓存

- `ScreenCaptureService` 仅缓存当前一帧画面，供识别阶段使用
- 识别完成后可释放，避免常驻占用

### 11.3 标签映射缓存

- `LabelManager` 的映射在每次识别后重建，不跨轮次缓存
- 停用时调用 `reset()` 清空

## 12. 性能考量

### 12.1 端到端延迟预算（对应 NFR-001）

| 阶段 | 预算 |
|------|------|
| 屏幕采集 | ≤ 100ms |
| 模板匹配（含三尺度） | ≤ 200ms（NFR-001 要求） |
| OCR 识别（两阶段） | 与模板匹配并行，不额外占用端到端预算（除非更慢） |
| 合并去重 | ≤ 30ms |
| 标签分配 + 渲染 | ≤ 150ms（NFR-005 要求标签呈现） |
| 端到端总计 | ≤ 500ms（NFR-001 要求） |

### 12.2 模板匹配性能优化

- 多尺度模板预计算缓存，避免运行时缩放
- vDSP 向量化运算，利用硬件加速
- 三尺度匹配可并行，进一步缩短耗时
- 大画面可先在半尺寸/四分之一尺寸下快速定位候选区域，再在原始尺寸下精匹配（实现者可根据测试决定是否采用此策略）

### 12.3 内存预算（对应 NFR-002）

- 模板图像缓存：取决于模板数量与尺寸，需在 150MB 预算内
- 屏幕画面缓存：单帧，约几 MB
- 识别中间结果：短暂存在，识别完成后释放

### 12.4 稳定性（对应 NFR-004）

- 连续 100 次识别无崩溃、无内存泄漏
- 每轮识别结束后释放中间数据结构
- 模板图像缓存为常驻，不随识别次数增长
- 标签映射每轮 reset，不累积

## 13. 错误处理

### 13.1 识别失败

- OCR 引擎或模板匹配引擎抛出错误时，组合引擎将该路结果视为空列表，不阻塞另一路
- 两路均失败时，组合引擎返回空列表，控制器转入 `空结果` 状态

### 13.2 采集失败

- 屏幕采集失败时，控制器记录错误日志，状态回退到 `待激活`
- 不向用户呈现错误弹窗（避免干扰自动化流程）

### 13.3 非法状态转换

- 状态机遇到未定义的转换组合时，记录错误日志，保持当前状态不变
- 不崩溃，不影响后续正常操作

### 13.4 标签查询失败

- 用户输入的字母无对应元素时（如标签已失效），解析器忽略本次输入，控制器保持 `激活` 状态

## 14. 可扩展性

### 14.1 机器学习模型识别路径（对应 Future Considerations）

`RecognitionSource.coreML` 已预留（对应 FR-007），未来新增机器学习识别路径时：

- 新建 `MLRecognitionEngine` 实现 `VisualRecognitionEngine` 协议
- 在 `CompositeRecognitionEngine` 中增加第三路并行调度
- 三路结果合并去重逻辑不变（重叠度 0.5 规则对三类来源一视同仁）
- 本期不实现该路径，仅保留来源标记

### 14.2 多显示器支持（对应 Future Considerations）

本期仅支持主显示器（对应 Out of Scope）。未来扩展时：

- `ScreenCaptureService` 支持多显示器采集
- `ScreenOverlay` 支持多显示器渲染
- 识别流程不变，仅画面来源与渲染目标扩展

### 14.3 自定义模板管理（对应 Future Considerations）

本期模板图像库为预置（Out of Scope 增删管理）。未来扩展时：

- `TemplateRepository` 增加增删接口
- 增删后刷新预计算缓存
- 识别流程不变

## 15. 设计决策记录

### 15.1 为何采用组合引擎模式

需求要求 OCR 与模板匹配并行执行且结果合并去重（FR-002、FR-006）。组合引擎模式将"并行调度"与"合并去重"封装在单一模块，使 OCR 引擎与模板匹配引擎保持单一职责（仅产出候选），降低耦合。

### 15.2 为何采用枚举状态机而非状态模式

状态集合固定（Constraints-6），无运行时新增状态需求。枚举 + 转换函数的实现方式编译期穷尽所有状态，避免遗漏转换分支，且代码量小于状态模式。

### 15.3 为何多尺度模板预计算缓存

需求要求模板匹配 ≤ 200ms（NFR-001），且多尺度层级固定（Constraints-5）。预计算半尺寸、四分之一尺寸模板图像，避免每次匹配时重复缩放，将运行时开销转移到启动时的一次性计算。

### 15.4 为何置信度阈值每次现读

需求要求阈值运行时修改后下一次识别立即生效（NFR-006）。每次匹配现读避免了缓存一致性问题，读取开销可忽略（原子变量或 actor 封装）。

### 15.5 为何两路引擎无共享可变状态

需求要求并行期间无共享可变状态、互不阻塞（NFR-003）。无共享状态使两路引擎可自由并行，无需锁竞争，合并阶段在主流程同步执行避免抖动。

## 16. 与需求的追溯关系

| 需求项 | 设计章节 |
|--------|---------|
| FR-001 快捷键激活 | 3.1、6.5.2 |
| FR-002 并行执行 | 6.3.1、10.1 |
| FR-003 多尺度匹配 | 6.1.1、4.4 |
| FR-004 归一化互相关 | 6.1.2 |
| FR-005 置信度阈值过滤 | 6.1.3、3.9 |
| FR-006 合并去重 | 6.3.2 |
| FR-007 标记识别来源 | 4.1、4.2 |
| FR-008 统一字母标签 | 6.4.1 |
| FR-009 模板标签查询 | 6.4.2 |
| FR-010 两阶段执行 | 6.2.1 |
| FR-011 状态机 | 6.5.1、8 |
| FR-012 元素点击 | 3.8、7.2 |
| NFR-001 端到端延迟 | 12.1 |
| NFR-002 内存占用 | 11、12.3 |
| NFR-003 并发协调 | 10.2、6.3.1 |
| NFR-004 稳定性 | 12.4 |
| NFR-005 用户体验 | 7.1、7.2 |
| NFR-006 阈值响应 | 6.1.3、9.4 |
| Constraints-2 不新增依赖 | 1、6.1.2 |
| Constraints-3 来源类别固定 | 4.2 |
| Constraints-4 重叠度阈值固定 | 6.3.2 |
| Constraints-5 尺度层级固定 | 4.4、6.1.1 |
| Constraints-6 状态集合固定 | 8.1 |
| Constraints-7 快捷键固定 | 6.5.2 |

## 17. 验收标准覆盖

设计层面确保以下 AC 可实现：

| AC | 设计支撑 |
|----|---------|
| AC-1 快捷键激活 | 6.5.2、7.1 |
| AC-2 并行执行 | 6.3.1、10.1 |
| AC-3 多尺度匹配 | 6.1.1 |
| AC-4 NCC 输出与阈值 | 6.1.2、6.1.3 |
| AC-5 阈值运行时生效 | 6.1.3、3.9 |
| AC-6 去重 | 6.3.2 |
| AC-7 标记来源 | 4.1、4.2 |
| AC-8 统一标签 | 6.4.1 |
| AC-9 区域查询 | 6.4.2 |
| AC-10 两阶段 | 6.2.1 |
| AC-11 状态机转换 | 8 |
| AC-12 空结果 | 7.1、8.2 |
| AC-13 点击操作 | 7.2、3.8 |
| AC-14 停用 | 7.3、8.2 |

---

## 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2026-07-16 | 初版，定义 F3.2 模板匹配功能设计，覆盖模块划分、职责边界、数据流、状态变化、协作关系 |

---

## 自查

### 1. 你在 Design 中是否引用了 Requirements 中的内容？如何处理的？

是，本文档多处引用 Requirements 中的内容，处理方式如下：

- **编号引用**：在设计章节中通过 FR-xxx、NFR-xxx、AC-xxx、Constraints-x 编号引用对应需求条款，例如"对应 FR-011"、"对应 NFR-001"。这种方式既建立了设计与需求的双向追溯，又避免重复抄写需求原文。
- **章节追溯表**：第 16 节"与需求的追溯关系"以表格形式列出每个需求项对应的设计章节，确保所有 FR、NFR、Constraints 均有设计落点。
- **AC 覆盖表**：第 17 节列出每个 AC 对应的设计支撑，确保验收标准在设计层面可实现。
- **禁止条款遵循**：对于需求"禁止修改"的条款（如重叠度 0.5、置信度默认 0.8、七状态集合、⌘⇧V、两阶段划分、三类来源、三级尺度），设计文档严格遵循，并在相关章节显式标注"对应 Constraints-x"以示遵循。
- **不抄写需求原文**：设计文档不重复需求的行为描述，而是说明"如何实现"该行为。例如需求 FR-006 描述"重叠度超过 0.5 去重"是行为，设计 6.3.2 描述"IoU 计算 + 降序排序 + 遍历去重"是实现。

### 2. 你在 Design 中是否写了代码？写了哪种程度的代码？

是，本文档写了代码，但控制在"设计级"程度，未写实现级代码。具体包括：

- **类型签名**：定义了 `struct VisualElement`、`enum RecognitionSource`、`enum MatchScale`、`enum VisionState` 等数据结构的字段与取值（第 4、8 章）。这些是设计契约，定义数据形状，不含实现逻辑。
- **协议接口**：定义了 `protocol VisualRecognitionEngine`、`protocol CompositeRecognitionEngining`、`protocol LabelManaging`、`protocol VisionModeControlling` 等协议的方法签名（第 5、6 章）。这些是模块间契约，定义交互边界，不含实现。
- **并行调度示意**：6.3.1 给出 `async let` 并行调度的示意代码，说明并行结构，不含错误处理、日志等实现细节。
- **算法伪代码**：6.1.1（多尺度匹配流程）、6.1.3（阈值过滤）、6.3.2（合并去重）、6.2.1（两阶段执行）以伪代码/流程描述形式说明算法步骤，不使用具体语言语法。
- **未写的代码**：未写完整的方法实现体、未写具体的 vDSP 调用代码、未写 UI 渲染代码、未写测试代码、未写文件路径与目录结构。

总体程度：**类型定义 + 接口签名 + 算法伪代码**，足以指导实现但不束缚实现细节（如 vDSP 的具体 API 选择、是否分块等留给实现者）。

### 3. 你如何决定某句话应该写在 Design 还是 Requirements？

判断原则：

- **Requirements 写"做什么"（What）**：可观察的行为、用户视角的能力、业务约束、验收标准。判断标志：用户能从外部观察到该行为（如"按下快捷键后模式激活"、"重叠区域仅一个标签"、"标签在 150ms 内呈现"）。这些与实现技术、语言、架构无关，换语言/换框架/换类名都不需要改 Requirements。

- **Design 写"怎么做"（How）**：架构决策、模块划分、类/协议/数据结构设计、算法选择、并发模型、缓存策略、状态机实现方式。判断标志：实现者需要据此编写代码（如"采用 async let 并行调度"、"采用枚举状态机"、"采用 vDSP 实现 NCC"、"模板预计算缓存"）。这些与技术选型相关，换语言/换框架可能需要改 Design。

- **边界案例**：
  - 阈值 0.8、重叠度 0.5、七状态、⌘⇧V 这类"固定值/固定集合"属于业务约束，写在 Requirements（Constraints）；Design 引用并遵循，不重新定义。
  - "采用归一化互相关方法"是需求指定的算法类别（FR-004），写在 Requirements；"采用 vDSP 实现归一化互相关"是技术选型，写在 Design。
  - "多尺度三级"是需求约束（FR-003、Constraints-5），写在 Requirements；"半尺寸、四分之一尺寸模板预计算缓存"是设计决策，写在 Design。
  - "两阶段流程"是需求规定（FR-010），写在 Requirements；"第二阶段文字识别可并行"是设计优化，写在 Design。

- **反向验证**：写完一句话后问自己——"如果换实现语言（Swift → Rust）或换框架（不用 Accelerate），这句话还需要改吗？"若需要改，属于 Design；若不需要改，属于 Requirements。

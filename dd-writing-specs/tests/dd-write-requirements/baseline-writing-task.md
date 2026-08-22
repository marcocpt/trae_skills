# 基线写作任务：真实写作场景测试

## 任务

你是一名 AI Coding 助手。请根据以下功能描述，写一份 `01_Requirements.md`。

**重要：** 直接写文档，不要问问题，不要探索代码库。基于以下信息写一份完整的 Requirements 文档。

## 功能描述（用户提供）

F3.2 OpenCV 模板匹配功能：

- `TemplateMatchingEngine` 实现 `VisualRecognitionEngine` 协议（位于 MacimCore），基于 Accelerate framework vDSP 向量运算实现 NCC（归一化互相关，等价于 OpenCV `TM_CCOEFF_NORMED`）算法，配合金字塔 3 级多尺度匹配（1.0 / 0.5 / 0.25）
- `CompositeRecognitionEngine` 实现 `VisualRecognitionEngine` 协议，持有 `ocrEngine` + `templateEngine` 两个子引擎，通过 `async let` 并行调用，按 IoU 0.5 去重合并
- `VisualElement` 新增 `source: VisualSource` 字段，枚举值 `.ocr` / `.template` / `.coreML`
- `VisionModeController` 调用 `recognitionEngine.cachedTemplateLabels()[rect]` 填入模板 label
- 配置项 `com.macim.visual.templateConfidenceThreshold` 默认 0.8
- 复用 F3.0 的 7 状态状态机（idle / capturing / recognizing / active / emptyResult / executing / deactivating）
- Stage 1 `detectTextRectangles` 并行 OCR detect + 模板匹配，Stage 2 `recognizeText` 委托 OCR 引擎补文字
- 用户按 ⌘⇧V 激活视觉识别，OCR 与模板匹配并行执行，统一显示字母标签，输入标签点击元素位置

## 输出要求

写一份完整的 `01_Requirements.md`，包含以下章节：

1. Background（背景）
2. Problem Statement（问题定义）
3. Goals（目标）
4. Scope（范围）
5. Functional Requirements（功能需求，编号 FR-001 起）
6. Non-functional Requirements（非功能需求）
7. Constraints（约束）
8. Acceptance Criteria（验收标准，用 Given/When/Then）
9. Out of Scope（明确不做）
10. Terminology（术语）
11. Decision Freedom（实现自由度）
12. Future Considerations（未来扩展）

直接输出文档内容，使用 Markdown 格式。

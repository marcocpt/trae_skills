---
name: dd-shared-ui
description: 当需要 UI 可观测性门禁验证时使用（被 dd-ai-refactor-workflow、dd-feature-development-workflow 引用）。触发词：UI 可观测性、UI 证据、UI 门禁、可观测性矩阵。
---

# dd 共享 UI 可观测性门禁

## 概述

本技能包含 dd 系列技能通用的 UI 可观测性门禁规则，各 dd 技能引用本技能以避免重复。

本技能固定为 `invocation_mode=helper`：返回 UI 证据与 Gate 结果，不自行 Host Close；顶层 `standalone` 会话按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 收尾。

## UI 可观测性门禁

任何涉及 UI、桌面 app、Web app、可视化、快捷键交互、窗口/浮层/菜单/表单/画布的特性，都必须通过此门禁。

### 证据分层

优先级从高到低：

1. **真实路径自动化证据**：E2E、XCUITest、Playwright、Appium、真实浏览器或真实 app 流程，断言用户可见结果。
2. **稳定可观测标记**：可访问性树、DOM、窗口层级、截图像素、canvas pixel、状态日志、activation marker、ready hook；必须能证明用户可见行为。
3. **组件级 UI 证据**：渲染测试、快照、视觉回归、故事书截图；只能覆盖组件边界。
4. **手动验收证据**：明确步骤、预期画面、截图/录屏/日志路径、执行时间和执行人；只能用于自动化不可行的部分。
5. **内部状态证据**：单元测试、ViewModel 状态、Core 状态机、日志；只能证明支撑逻辑，不能单独关闭 UI AC。

### 关闭规则

- 每个 UI AC 至少需要一种 1-4 层证据；只有第 5 层证据时，状态必须标为"未完成 UI 验证"或"存在 UI 风险"。
- 自动化不可行时，必须在设计文档和子计划中写明原因、手动验收步骤、证据保存位置和剩余风险。
- 任何"测试不到但应该没问题"的结论都必须升级为风险项，不能作为完成依据。

## 被其他 skill 引用方式

各 dd 技能中涉及 UI 的步骤引用本技能。引用格式：`UI 可观测性门禁遵循 [dd-shared-ui](../dd-shared-ui/SKILL.md)`

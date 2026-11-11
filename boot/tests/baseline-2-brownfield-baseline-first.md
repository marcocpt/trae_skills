# 基线场景 2：Brownfield 从 Roadmap 入口仍先 Baseline

**这是决策测试。选择并执行，不询问流程已能决定的问题。**

## 背景

`/tmp/legacy-pdf-lib/` 已发布两年，有生产用户、公共 API、持久化文件和部分失效测试。用户明确说：“先从 Roadmap 开始，不做调研。”

仓库没有 Baseline、Architecture Contract 或 AI Conventions。

## 选择

A) 尊重 requested entry，立即写 Roadmap，Baseline 以后补
B) 先做完整 Research，再写 Roadmap
C) 记录 requested entry=Roadmap；Gap Scan 插入 Brownfield Baseline，通过后直接进入 Roadmap
D) 只按源文件数量决定是否 Baseline

## 预期

**C**

requested entry 决定目标入口，不绕过依赖。生产兼容义务使项目成为 Brownfield；Baseline 是 Roadmap 状态、Legacy Surface 和 Phase Contract 的证据前置。用户已排除非阻塞调研时，不强制 Research。

# Intake and Requirements

## 目录

- [规则来源](#规则来源)
- [规则摘要](#规则摘要)
- [功能与参考规格](#功能与参考规格)
- [Grill](#grill)
- [上游 Seed](#上游-seed)
- [Requirements Gate](#requirements-gate)

## 规则来源

按存在情况读取：

- `.trae/rules/docs.md`
- `docs.md`
- `docs/standards/CODING_STANDARDS.md`
- `docs/CODING_STANDARDS.md`
- `docs/standards/xctest-rules.md`
- `docs/AI/trae-xctest-rules.md`

不存在时先用仓库搜索确认，再使用 writer 默认规则；不要反复 ASK 已知缺失。

## 规则摘要

`.step0-rules-summary.md` 至少记录：

1. Requirements 章节；
2. Design 章节；
3. 文档顺序；
4. 四篇文件命名；
5. 存放路径；
6. 版本和更新时间；
7. Visual/Test 是否必需；
8. 标点与术语；
9. Mermaid/HTML 约束；
10. 跨文档同步规则；
11. 来源路径与版本/Commit。

默认命名：

- `F{N}_{功能名}_需求文档.md`
- `F{N}_{功能名}_设计文档.md`
- `F{N}_{功能名}_视觉原型.html`
- `F{N}_{功能名}_测试用例表.md`

默认路径优先遵循项目现有 `docs/planning/P{n}/F{m}/`；不存在时才使用项目约定的新位置。

## 功能与参考规格

搜索根目录和 `docs/` 下的 app 功能列表，记录：

- Feature 编号和优先级；
- 相关/冲突功能；
- 已有简述和范围；
- 规划依赖。

在 `docs/` 下按修改时间/提交搜索最近 1–3 份 Requirements/Design。完整读最近 1 份，浏览其余目录与 AC 粒度。复用结构和风格，不复制正文。

## Grill

一次一个问题，依次覆盖：

1. 用户问题和业务目标；
2. 成功标准；
3. IN/OUT；
4. 入口、主路径、失败与退出；
5. 业务数据、外部接口和持久化影响；
6. 兼容与迁移；
7. 可测试 AC；
8. Phase 输入；
9. UI 可见证据；
10. Feature 编号、优先级和路径。

能从代码/文档回答的先探索。每问给推荐答案和理由；null 重问。最终 ASK：

- 确认并写 Requirements；
- 补充细节；
- 方向错误，重新描述。

确认后持久化并提交 `.step1-requirements-summary.md`。

## 上游 Seed

Feature workflow 调用时读取其状态或 `.feature-step0-requirements-summary.md`：

1. 验证路径和来源 Commit；
2. 对照功能列表与规则；
3. 检查 10 项 grill 信息是否足够；
4. 一致则写 `.step1-requirements-confirmed.md`；
5. 只有冲突/缺失 blocker 才 ASK。

不得因文件命名不同就重复 grill；以父状态明确传入的 seed 为准。

## Requirements Gate

默认 12 章节：

1. Background
2. Problem Statement
3. Goals
4. Scope
5. Functional Requirements
6. Non-functional Requirements
7. Constraints
8. Acceptance Criteria
9. Out of Scope
10. Terminology
11. Decision Freedom
12. Future Considerations

P0 全文检查：

- 无类/协议/方法/字段/枚举/配置键；
- 无框架 API、并发原语、算法常量、文件路径；
- FR 从业务结果描述；
- NFR 可测量；
- AC 使用 Given/When/Then；
- Decision Freedom 同时写允许和禁止；
- 无 TODO/TBD/待定/占位符；
- 版本头和记录符合项目规则。

写完先提交 draft；review 修复和确认再独立提交，保证基线可追溯。

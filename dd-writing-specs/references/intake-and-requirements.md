# Intake and Requirements

## 目录

- [规则来源](#规则来源)
- [规则摘要](#规则摘要)
- [功能与参考规格](#功能与参考规格)
- [Grill](#grill)
- [上游 Seed](#上游-seed)
- [Lite 任务包](#lite-任务包)
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

规则无法从项目中取得时，只记录已确认缺失与采用的默认来源，不虚构项目规则。项目 `docs.md` 或正式项目约束硬性要求逐篇确认或套件而与本 skill 默认（最小任务包、按决定确认）冲突时，遵循项目规则，并显式向用户报告冲突位置、影响和可选处理，不静默绕过。

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

**已明确项不问**：目标、范围、成功标准等事实已从代码、已批准文档或既有确认记录恢复且覆盖 Grill 对应项时，直接复用，不重复 grill；只清点仍未解决且影响执行的项（产品决策、范围变化、高风险、授权边界）。

确认后持久化 `.step1-requirements-summary.md` 及确认依据；Git 动作按已明确 `delivery_policy` 单独处理。

## 上游 Seed

Feature workflow 调用时读取其状态或 `.feature-step0-requirements-summary.md`：

1. 验证路径和来源 Commit；
2. 对照功能列表与规则；
3. 检查 10 项 grill 信息是否足够；
4. 一致则写 `.step1-requirements-confirmed.md`；
5. 只有冲突/缺失 blocker 才 ASK。

不得因文件命名不同就重复 grill；以父状态明确传入的 seed 为准。

## Lite 任务包

Lite 模式（默认）不产出四件套，只写**持久任务入口**一个文件（入口选择规则见 [SKILL.md](../SKILL.md) 持久任务入口节：`child` 复用父入口，`standalone` 复用项目既有入口，无则创建任务专属路径），包含四块内容加看板与交接：

1. **目标/范围**：要解决什么问题、IN/OUT 清单；目标与范围已由上游 seed 或已批准文档给出且未变化时，引用不复述；
2. **必要设计决定**：只记影响正确性或后续执行的决策，每条写"决策/理由/代价"；实现细节（类名、接口、目录、框架）不写；
3. **验证条件**：AC 用 Given/When/Then，可观察、可测量，无模糊词；每个 AC 对应任务安排中的验证方式（命令、测试或人工步骤）——验收条件由执行方实际运行，writer 只保证其可执行、可测量；
4. **任务安排**：人话任务清单，每条含完成条件；与 AC 的映射紧凑表达，不维护独立追溯表。

写后自检：AC 可观察可测量、无 TODO/占位符；需求事实无代码符号（判定与 Rewrite Strategy 见 [requirements-writer.md](requirements-writer.md)）；范围无越界；与项目规则一致。

**确认只覆盖未解决决策**（产品决策、范围变化、高风险、授权边界）：存在未解决项时展示自检结论后一次 ASK；全部已解决且已有效授权时自检通过即继续，不重复确认；已明确目标与授权范围内的机械整理不重复确认；未批准语义不因合并进任务包而变为已批准。

**writer 不执行生产实现**：任务包完成后交还调用方（`standalone` 交还用户及其后续执行方，`child` 返回 Feature workflow）；实现与验证由调用方或 Feature/Bug 负责，本 writer 只准备规格与可执行验收条件。实现状态以代码与实际运行证据为准（命令、退出码、产物），文档 PASS、勾选或旧报告不算实测；文档自检结论不等于实现已通过。

满足任一条件时从任务包拆出独立单篇（沿用对应 writer 的 Gate）：出现明确消费者或独立稳定合同；用户/项目明确要求。拆出后未拆事实仍以任务包为属主，不复制成第二份；拆文件不改变批准范围。**高风险本身不构成拆份条件**：风险通过 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 加强审查/验证/tracer 承接，不以增加文档数量代理风险控制。

## Requirements Gate

以下默认 12 章节**仅在产出独立 Requirements 文档时适用**（Full 模式或单文档模式）；Lite 模式的等价事实（目标/范围/AC）承载于任务包，不强制 12 章节，但 P0 与可验证性要求不变。

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

写完先落盘 draft；review 修复后记录确认版本、内容指纹和批准依据。只有已明确交付策略要求时，才按对应边界提交。

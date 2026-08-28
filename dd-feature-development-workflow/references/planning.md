> 迁移来源：`writing-plans/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。


# 编写计划

## 概述

为零历史上下文的执行者生成自足、可验证的任务包。只展开当前任务需要的冻结事实，不复制无关背景或整段实现；保持 DRY、YAGNI 和 TDD。

通用来源、失效、证据和授权字段由 [artifact-source-and-packet](../../dd-workflow-runtime/references/artifact-source-and-packet.md) 唯一维护；本文件只定义 Feature 计划如何实例化这些字段。生命周期、同步影响与保留的唯一定义见 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3，本文件不重定义 `updated|no-update|stale|not-applicable|retired` 或生命周期枚举。

**上下文：** 使用 Feature workflow 已固定的 worktree；不要自行创建第二套工作环境。

**计划保存位置：** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- （用户对计划位置的偏好优先于此默认值）

## 范围检查

如果规格涵盖了多个独立子系统，它应该在头脑风暴阶段就被拆分为子项目规格。如果没有，建议将其拆分为独立的计划——每个子系统一个。每个计划应该能独立产出可工作、可测试的软件。

## 文件结构

在定义任务之前，先列出将要创建或修改的文件以及每个文件的职责。这是锁定分解决策的地方。

- 设计边界清晰、接口定义良好的单元。每个文件应有一个明确的职责。
- 你对能一次放入上下文的代码推理得最好，文件越专注你的编辑越可靠。优先选择小而专注的文件，而非承担过多功能的大文件。
- 一起变更的文件应放在一起。按职责拆分，而非按技术层级拆分。
- 在现有代码库中，遵循已有模式。如果代码库使用大文件，不要单方面重构——但如果你正在修改的文件已经变得难以管理，在计划中包含拆分是合理的。

此结构决定了任务分解。每个任务应产出独立的、有意义的变更。

## 任务粒度

每个 Task 必须是有意义、可独立验证的行为切片，并在一个执行上下文中保留质量余量。不要把共享接口的设计分散给多个 Task，也不要为固定分钟数把脚手架、实现和唯一验收证据拆开。步骤仍按 Red → 验证失败 → Green → 验证通过 → 必要 Refactor 排序；Git 动作只在 `delivery_authorization` 允许时出现。

## 计划文档头部

**每个计划必须以此头部开始：**

```markdown
# [功能名称] 实现计划

> **面向 AI 代理的工作者：** 由 `dd-feature-development-workflow` 的 Implementation Stage 逐 Phase 执行本计划；步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** [一句话描述要构建什么]

**架构：** [2-3 句话描述方案]

**技术栈：** [关键技术/库]

---
```

## 任务结构

Phase plan 头部定义一次 `source_manifest`（每个被引用来源的完整 metadata 只出现一次，见 [artifact-source-and-packet §2.1](../../dd-workflow-runtime/references/artifact-source-and-packet.md)）；每个 Task 只写 `sources: [{ref, anchors}]`，不复制 path/version/digest/approval。

```markdown
### Phase plan 头部

**source_manifest：** [完整来源 metadata 唯一一次定义]
```yaml
source_manifest:
  SPEC-REQ:
    stable_id: SPEC-REQ
    path: docs/specs/feature/requirements.md
    digest: sha256:current-content
    approval: {status, authority, decided_at, evidence_ref}
    version_label: v1.0  # optional
```

```markdown
### 任务 N：[组件名称]

**Sources：** `sources: [{ref: SPEC-REQ, anchors: [FR-001, AC-001]}]`（完整 metadata 见 plan 头部 `source_manifest`）

**Consumes：** [精确输入／接口]

**Produces：** [精确输出／供下游使用的接口]

**Write scope：**
- 创建：`exact/path`
- 修改：`exact/path`
- 删除：无

- [ ] **步骤 1：编写失败的测试**

  指明测试文件、行为、输入和 oracle；只有签名或脆弱逻辑无法从来源确定时才内联必要代码。

- [ ] **步骤 2：运行测试验证失败**

  运行：`<exact command>`
  预期：`FAIL`，且失败原因是缺少目标行为。

- [ ] **步骤 3：编写最少实现代码**

  指明修改位置、必须保持的接口／约束和最小行为；不复制可从当前允许文件直接读取的整段代码。

- [ ] **步骤 4：运行测试验证通过**

  运行：`<exact command>`
  预期：`PASS`，并写明证据位置。

**Stop conditions：** [来源过期、越界、验证失败或缺权限时的 BLOCKED／STOP 与下一安全动作]

**Delivery authorization：** [`{status, actions, scope, authority, decided_at, evidence_ref}`]
```

## 跨 Phase 集成计划

当 `split_mode=per-phase-with-integration`（Phase ≥ 6 或跨子系统，见 [planning-stage.md](planning-stage.md) 拆分档位）时，除逐 Phase 子计划外，必须额外产出 `plan-integration-cross-phase.md`。该文件：

- 显式列出 Phase 间 IN/OUT 契约与依赖边（哪些 `Produces` 被哪些下游 Phase `Consumes`）；
- 覆盖跨 Phase 的端到端 AC 与集成验收（不能由任一 Phase 独立验证的部分）；
- 定义集成验收的验证命令与证据位置；
- 明确集成计划不是 Phase 子计划的替代，也不是把 Phase 内容复制合并成一个总计划。

未产出 integration plan 时，复杂档不得进入 Implementation（`BLOCKED`）。

## 禁止占位符

每个步骤都必须包含工程师需要的实际内容。以下是**计划缺陷**——绝不要写出来：
- "待定"、"TODO"、"后续实现"、"补充细节"
- "添加适当的错误处理" / "添加验证" / "处理边界情况"
- "为上述代码编写测试"（没有实际测试代码）
- "类似任务 N"（重复代码——工程师可能不按顺序阅读任务）
- 只描述目标，不给精确位置、接口、约束或验证 oracle
- 引用了未在任何任务中定义的类型、函数或方法

## 注意事项
- 始终使用精确的文件路径
- 必要签名／数据结构必须精确；整段实现仅在歧义或脆弱性确有需要时内联
- 精确的命令和预期输出
- DRY、YAGNI、TDD；Git 步骤服从 `delivery_authorization`

## 自检

编写完整计划后，以全新视角审视规格并对照检查计划。这是你自己执行的检查清单——不是子代理调度。

**1. 来源新鲜度：** 逐项核对每个任务的来源内容指纹和批准依据；任一变化将任务包标记 stale，重新派生。

**2. 原文覆盖度：** 以本 Stage 首次完整读取生成的 canonical inventory（`canonical-index.json` 含 `normative_anchors` + `source_manifest_digest` 绑定）为基准，检查 inventory → Task/Test/Evidence 是否无遗漏或越界；仅在 missing/partial/conflicting、source digest drift、anchor 无法定位或来源缺少稳定 IDs 时定向回读对应 canonical anchor，修复后复核；不得为自检无条件再次完整读取整套规格，无法证明 index 完整时允许一次全文复核（`validate-workflow-artifact.py planning-index <canonical-index.json> <plan>` 校验，仅该 JSON 索引路径允许机械 PASS）。

**3. 执行包完整性：** 检查 [artifact-source-and-packet](../../dd-workflow-runtime/references/artifact-source-and-packet.md) 的必需字段、精确验证预期、停止条件和授权；缺失即 BLOCKED。

**4. 接口一致性：** 后续任务使用的类型、签名和属性名必须与其 `Consumes` 来源及前序 `Produces` 一致。

**5. 占位符扫描：** 搜索上方“禁止占位符”的模式并修复。

发现派生表达错误可重新生成并复核；发现原始规格冲突、缺批准或权限时停止并回到属主，不得在计划内自行裁决。

## 执行交接

计划保存并通过自检后，返回 `dd-feature-development-workflow` 的 Planning Gate，由其按 Phase 顺序进入 Implementation。不要再路由到额外的执行编排 Skill；Codex 可在父工作流约束下直接或并行执行无共享状态的子任务。

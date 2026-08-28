---
name: dd-ai-refactor-workflow
description: 当重构遗留代码、用户提到 AI 重构/refactoring、或工作到达需要人类确认的刹车点时使用。触发词：refactor、重构流程、Characterization Test、解依赖、God Object 拆分、行为漂移检测。
---

# AI 重构工作流

## 目标

先理解，再用 Characterization Test 锁定行为，最后以小 Commit 重构。运行时使用 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)，保证长流程可恢复；细节按需加载，不能用省 token 为由降低质量。

## 适用边界

适用：遗留代码整理、God Object/Long Method/循环依赖治理、解依赖与行为保持型架构演进。

不适用：

- 明确 Bug：用 [dd-bug-fix-workflow](../dd-bug-fix-workflow/SKILL.md)；
- 新用户行为或新能力：用 [dd-feature-development-workflow](../dd-feature-development-workflow/SKILL.md)；
- 只有文档审查：用对应文档 Skill。

AI 无权威证据且无法判断 Bug/Feature 时必须 ASK，不得把产品选择伪装为重构。

## 运行时入口

直接响应用户时传：

```yaml
workflow_type: ai-refactor
invocation_mode: standalone
host: auto
requested_entry: understanding
state_file: $(git rev-parse --git-dir)/ai-refactor-state.json
required_exit_stages:
  - understanding
  - characterization
  - diagnosis
  - roadmap
  - execution
  - verification
```

被其他编排器调用时使用 `invocation_mode=child`，完成后返回父工作流，不执行 Host Close。

首次进入或恢复：

1. 读取适用规则、仓库、分支、工作树、已有文档、测试与 CI 事实；
2. 恢复状态；状态缺失时从提交、产物和 CI 证据重建；
3. Gap Scan 找出第一个未满足 Gate；
4. 首次修改文件前按 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md) 确定 worktree；
5. 已解决事实不重问，阶段间 happy path 自动推进。

状态至少记录 `current_stage`、`completed_stages`、行为基线、改动批次、提交、CI run、blocker 与 `next_safe_action`。每个 Gate 后原子持久化。

## Stage Graph

```text
Understanding
    ↓
Characterization
    ↓
Diagnosis / Refactor Report
    ↓
Roadmap / Dependency Batches
    ↓
Small-step Execution
    ↓
CI
    ↺ next batch / Complete
```

### 1. Understanding

只读代码，不改实现。产出或校验：

- `Architecture.md`：目录、模块职责、依赖方向；
- `Build.md`：构建、CI、度量和失败定位方式；
- 当前可观察行为、外部依赖和高风险区域。

Gate：入口、依赖、验证命令和行为边界都有仓库证据。

### 2. Characterization

按高/中/低/极低可测性分类：直接测试 → 注入 Stub → 先解依赖 → 记录暂不覆盖。完整策略见 [refactor-method.md](references/refactor-method.md)。

Gate：

- 关键行为有 Characterization Test 或明确例外；
- 测试在 CI 环境通过；
- 疑似 Bug 已通过硬刹车决定“锁现状”还是“先修正”；
- 基线提交可追溯。

未锁行为禁止进入实现。

### 3. Diagnosis

扫描重复、God Object、Long Method、循环依赖、SOLID 违例和测试阻力，产出重构报告。按风险、价值、依赖和可逆性排序，不把风格偏好当问题。

### 4. Roadmap

产出依赖图与批次表。每批只处理一种问题：

1. 行为保持型：Rename / Extract Method / Move Method；
2. 结构型：Extract Class / Extract Protocol / DI；
3. 架构演进：模块化、状态机等，必须先过硬刹车。

每批声明 `requires / produces / gate / rollback / recovery_evidence`。

### 5. Small-step Execution

- 一个 Commit 只解决一种问题；
- 功能行为修正与纯重构分开提交；
- 公共文件按 [dd-git-workflow/conflict](../dd-git-workflow/references/conflict.md) 隔离并标记 `PublicFile`；
- commit 遵循 [dd-git-workflow/merge](../dd-git-workflow/references/merge.md)，禁止 rebase、`--no-verify`、force push；
- 不暂存无关脏文件。

**文档影响判定：** 按 [artifact-lifecycle](../dd-workflow-runtime/references/artifact-lifecycle.md) §3.3 裁决，本 workflow 属 pure-refactor 路由，具体 Requirements/Design/Test Policy disposition 取共享合同（不复制路由表）。

### 6. CI 验证

每个逻辑批次完成确定性验证；只有 `delivery_authorization` 允许 push 时才 push 并取得同一 SHA 的远端 CI。必需远端 CI 未授权时停在 Delivery 边界，不得擅自 push。行为保持由测试证明，不再做 commit 后 LLM 审查：

1. Characterization Test 在 CI 全绿；
2. 远端 CI 全绿（同一 SHA）。

覆盖充分性不变量：所有受影响的可观察行为必须映射到 Characterization Test；存在未覆盖路径时先补测试，不得进入重构；重构 Commit 不得同时弱化 characterization oracle；CI 必须在同一 SHA 运行这些测试。

本地测试只可辅助定位，不能替代 CI，也不能关闭必需远端 CI Gate。CI 失败处置、回滚和覆盖边界见 [verification-and-delivery.md](references/verification-and-delivery.md)。

## 硬性刹车点

只有以下情况 ASK；其余 happy path 自动推进：

| 场景 | 必须决定 |
|---|---|
| 无权威证据，无法判断 Bug 还是业务逻辑 | 转 Bug、转 Feature 或保持现状 |
| 启动重大架构演进 | 是否接受范围、迁移和回滚成本 |
| 解依赖后复核发现可观察行为漂移风险 | 接受、拆分或回滚 |
| Characterization Test 将锁定疑似 Bug | 锁现状或先修正 |
| CI 连续三轮修复仍失败 | 继续、仅定位或暂停 |
| 权威事实已明确但是否调整仍属产品判断 | 是否纳入当前范围 |

ASK 前先核验文件路径和行号，并附查证摘要；null 必须重问。询问遵循 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md)。

## Exit Gate

- 所有计划批次已完成或有明确、非阻塞的延后记录；
- Characterization Test 与必需 CI 全绿；
- 无新增 Warning；
- 报告、路线图、提交、CI 和回滚证据可追溯；
- Git/交付边界满足用户与项目规则；
- 状态已原子持久化。

未满足时只能继续、暂停或报告 blocker，不得伪装完成。

## Host Close

仅 `invocation_mode=standalone` 执行。

Trae：

1. 先写 `status=completed`，必要时写 Completion Receipt；
2. 禁止直接结束；
3. 用结构化 ASK，且只提供 `结束本次任务` / `还有其他任务`；
4. null 重问；“还有其他任务”创建新 workflow；“结束本次任务”后输出最终摘要。

Codex：正常输出最终摘要，除非用户或项目规则要求额外确认。

## 红线

- 未理解或未锁定行为就改实现；
- 一次性重写；
- AI 无依据自行判定 Bug/Feature；
- 跳过 CI 后合并；
- 用本地测试替代 CI；
- 把 CI 排队/未触发当作可跳过；
- 重构和功能修正混在同一 Commit；
- 未持久化就跨 Stage 或执行外部动作；
- child Skill 自行 Host Close；
- Trae 最终完成后直接结束。

## 按需读取

- 方法、四阶段产物、事实/业务边界、刹车细节：[references/refactor-method.md](references/refactor-method.md)
- CI、提交、回滚、失败与交付：[references/verification-and-delivery.md](references/verification-and-delivery.md)
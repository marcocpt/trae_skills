---
name: dd-project-bootstrap-workflow
description: 当需要从零创建 Greenfield 项目、为 Brownfield 项目重建 AI 协作基础，或补齐项目级 Roadmap、Architecture、Coding Standards、AGENTS.md 与首阶段合同缺口时使用。通过 Preflight Gap Scan、可恢复状态、依赖图和原子 writer，把任意入口推进到完整 Handoff；触发词：创建新项目、迁移老项目、项目脚手架、project bootstrap、初始化项目 AI 协作、项目级文档套件。
---

# 项目 Bootstrap 工作流

## 目标

把 Greenfield 或 Brownfield repository 推进到可由 [dd-feature-development-workflow](../dd-feature-development-workflow/SKILL.md) 稳定开发首个 Feature 的状态。

本 skill 只负责编排、状态、Gate 和 Handoff。具体项目级产物由 `dd-project-docs` 按 `requested_artifact` 编写；长流程运行遵循 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)，详细政策按需读取 references。

## 不适用

- 单个 Feature 实现：使用 `dd-feature-development-workflow`；
- Bug 修复：使用 `dd-bug-fix-workflow`；
- 已完整项目套件中的局部文档修订：直接使用对应 writer；
- 纯查询或只读审查。

## 核心原则

1. 入口灵活，出口严格；
2. Brownfield 必须先有 Baseline；
3. 一条事实只有一个 SSOT；
4. 工作流只编排，子 Skill 负责撰写；
5. 已解决事实只继承，不重问；
6. Workflow Gate 不是 Git commit；
7. 审查语义固定，执行成本随风险调整；
8. Trae 完成前必须显式最终 ASK。

## 首步：Preflight

以 `workflow_type=project-bootstrap`、`invocation_mode=standalone` 调用共享运行时，并读取 [execution-contract.md](references/execution-contract.md) 的 Bootstrap Node 与 Handoff 差异：

1. 检测适用规则、Git/worktree 和宿主能力；
2. 恢复或重建 `project-bootstrap-state.json`；
3. 记录用户的 `requested_entry`；
4. 判断 Greenfield/Brownfield；
5. 扫描已有治理产物；
6. 生成 `blocking_gaps`、`deferred_gaps` 和执行顺序；
7. 只询问无法从状态、仓库或已批准文档推断的 blocker；
8. 首次修改文件前确定并持久化工作环境。

用户请求“从 Roadmap 开始”只决定目标入口。若 Brownfield Baseline 缺失，必须先补 Baseline。

模式判定读取 [brownfield-policy.md](references/brownfield-policy.md)。不得用“存在至少一个源文件”单独判定 Brownfield。

## 状态恢复

状态持久化遵循 [dd-workflow-runtime/state](../dd-workflow-runtime/references/state.md)：

```text
WORKFLOW_TYPE=project-bootstrap
STATE_FILE=$(git rev-parse --git-dir)/project-bootstrap-state.json
PROGRESS_FIELD=current_node
```

每个 Node Gate 通过后更新：

- `current_node`
- `completed_nodes`
- `artifacts`
- `decisions`
- `blocking_gaps`
- `deferred_gaps`
- `status`

恢复时先验证路径、产物和项目规则。状态不存在时从仓库事实重建，禁止默认从头 grill。

## 依赖图

```text
Preflight
  ↓
Docs Governance
  ├─ Brownfield Baseline（Brownfield）
  └─ Research / Technical Validation（风险触发）
             ↓
           Roadmap
             ↓
    Architecture Contract
             ↓
      Coding Standards
             ↓
       AI Conventions
             ↓
 Phase Contract（Brownfield）
             ↓
           Handoff
```

执行顺序由依赖和 Gap Scan 决定，不使用固定 `0→1→...` 步骤强迫所有项目加载相同上下文。

## 节点路由

### Docs Governance

创建或校验根目录 `docs.md` 时读取 [docs-governance.md](references/docs-governance.md)。只创建当前需要的目录和文件，不生成空壳。

Gate：

- 文档目录和命名明确；
- SSOT 唯一；
- 同步和阅读策略明确；
- `docs.md` 不复制下游正文。

### Brownfield Baseline

Brownfield 必须调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=brownfield-baseline`。Greenfield 跳过。

产物必须包含能力、使用关系、处置和 Characterization Test 清单。

### Research / Technical Validation

调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=research`。

仅在未验证高风险假设会改变 Roadmap/Architecture、外部证据不足或用户明确要求时执行。可靠证据已存在时记录证据并跳过重复研究。

### Roadmap

调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=roadmap`。

Gate：

- 阶段 Goal/IN/OUT/Exit Gate 明确；
- 功能编号、依赖和首个 Feature 明确；
- Brownfield 状态基于 Baseline，不基于代码数量猜测。

### Architecture Contract

调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=architecture-contract`。

Gate：

- 依赖方向、不变量和禁止方向明确；
- Brownfield 分开维护 Legacy Compatibility Surface 与 Target Public Surface；
- Bootstrap 出口状态至少为 `approved-baseline`；
- 没有真实实现证据时不声称 `frozen`。

### Coding Standards

调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=coding-standards`。

Gate：

- 规则符合实际语言和工具链；
- 验证命令可执行；
- Greenfield 使用零新增违规；
- Brownfield 使用 baseline + changed-code ratchet。

### AI Conventions

调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=ai-conventions`。

Gate：

- 根 `AGENTS.md` 是短执行入口；
- 按需使用 nested `AGENTS.md`；
- Trae/其他宿主文件是薄适配器，不复制 Standards/Architecture；
- 明确 Always read / Read when relevant / Do not preload；
- `host=trae` 时包含“完成后 ASK 结束或其他任务”的硬约束。

### Phase Contract

Brownfield 调用 [dd-project-docs](../dd-project-docs/SKILL.md)，`requested_artifact=phase-contract`。Greenfield 默认跳过，由 Feature workflow 编写首个功能规格。

Gate：

- Characterization Test 已完成处置分类；
- `KNOWN_DEFECT` 没有升级为目标 AC；
- `TOLERATED_COMPATIBILITY` 有明确范围；
- `REVIEW` 为零；
- AC 可验证。

## 子 skill 调用合同

调用每个子 skill 时传递：

```yaml
project_mode: greenfield
host: codex
worktree_path: /absolute/path
resolved_decisions: []
artifact_paths: {}
blocking_questions: []
delivery_policy: project-rules
```

子 skill 必须消费上游事实，不得重复询问已解决内容。只允许询问缺失 blocker 或该产物特有的新决策。发现上游冲突时返回 blocker，不在下游另写一套规则。

所有子 skill 一律传 `invocation_mode=child`（原子 Git/CI/shared 能力传 `helper`），完成后返回本编排器；不得自行执行最终 Host Close。

询问和 worktree 选择遵循 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md)。

## 审查与 Gate

审查语义遵循 [dd-workflow-runtime/review-gate](../dd-workflow-runtime/references/review-gate.md)。

通用 Workflow Gate：

1. artifact exists；
2. artifact validated；
3. blocking decisions resolved；
4. state persisted；
5. blocking issues 为零。

Git status、lint、test、commit、push 和 PR 属于 Delivery Gate，遵循用户、项目规则和 [dd-git-workflow](../dd-git-workflow/SKILL.md)。不得用“最新 commit 不是当前产物”否定已验证的 Node 状态。

## Handoff

Handoff 的 payload schema、Greenfield/Brownfield 携带要求、写入 `status=handoff-ready` 与下游确认 `completed` 的语义，统一以 [execution-contract.md](references/execution-contract.md) 的 Handoff 章节为准，统一交给 `dd-feature-development-workflow`。Feature workflow 是唯一 Handoff 出口，Greenfield 不得绕过它直达 `dd-writing-specs`；规格 writer 由 Feature workflow 在消费 Requirements Seed 后调用。

## Exit Gate

Greenfield：

- docs governance、Roadmap、Architecture approved baseline、Coding Standards、AI Conventions 有效；
- 首个 Feature 和 Requirements Seed 明确；
- Handoff ready。

Brownfield：

- 上述 Greenfield 产物有效；
- Baseline 与处置矩阵有效；
- Legacy/Target Public Surface 分离；
- approved Phase Contract 有效；
- Handoff ready。

任一 blocking gap 未解决时不得宣布完成。

## 宿主结束合同

仅 `invocation_mode=standalone` 执行：Exit Gate 与 Handoff 完成后先原子持久化 `status=completed`（必要时写 Completion Receipt），再按 [dd-workflow-runtime 宿主结束合同](../dd-workflow-runtime/SKILL.md) 收尾——Trae 结构化 ASK `结束本次任务 / 还有其他任务`（null 重问），Codex 正常交付完成结果。询问与收尾模板遵循 [dd-workflow-runtime/ask](../dd-workflow-runtime/references/ask.md)。

## References

- Docs governance：[references/docs-governance.md](references/docs-governance.md)
- Execution/state/gates/handoff：[references/execution-contract.md](references/execution-contract.md)
- Brownfield/compatibility/quality：[references/brownfield-policy.md](references/brownfield-policy.md)

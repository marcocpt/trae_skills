---
name: dd-feature-development-workflow
description: 当实现需要规格套件、分阶段计划、TDD、CI 或用户可见 UI 证据的新功能、大规模重构或 API 迁移时使用；也用于接收 project-bootstrap Handoff，或恢复长期运行的 Feature 工作流。触发词：新特性流程、feature development workflow、规格文档套件先行、分阶段计划、Feature Handoff。
---

# 新特性实现工作流

## 目标

把已确认的 Feature 从需求输入推进到已验证、可恢复的完成状态。主文件只做**路由**：触发/运行时、核心不变量、Stage/Gate 图与红线；每个 Stage 的正文按需读取对应 reference，不在此重复。

## 不适用

- Bug 修复：使用 `dd-bug-fix-workflow`；
- 项目级 Bootstrap：使用 `dd-project-bootstrap-workflow`；
- 简单文本或纯文档微调：直接使用对应工具或 writer；
- 只读审查。

## 运行时

开始或恢复时调用 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)：

```yaml
workflow_type: feature-development
host: auto
requested_entry: user-request-or-bootstrap-handoff
state_file: $(git rev-parse --git-dir)/feature-development-state.json
stage_graph: feature-stage-graph
required_exit_stages:
  - intake
  - environment
  - specification
  - planning
  - implementation
  - documentation
  - final-candidate
  - confirmation
  - delivery
  - closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。

## 核心不变量

1. No approved specification, no production code；
2. Resolved Bootstrap facts are inherited；
3. Every Phase ends with a local quality Gate；
4. High-risk UI changes get remote Smoke CI；
5. The exact frozen candidate entering develop gets full CI；
6. User-visible behavior requires user-visible evidence；
7. Persist before every Stage transition；
8. Trae completion requires a final ASK；
9. Re-read approved originals; summaries only locate sources；
10. Phase 只读 anchors/global constraints，不每 Phase 重读整份规格；
11. Candidate Gate 不推进目标分支；Delivery 只推进同一 `candidate_sha`；
12. 内容批准 / 测试 PASS / Reviewer PASS 均不授权 Git 或外部动作。

## Stage / Gate 图

五个对外 Gate 是内部十个可恢复 Stage 的聚合命名；内部仍按 Stage 推进。

```text
Source Gate:   intake → environment → specification
Plan Gate:     planning
Phase Gate:    implementation (× N Phase)
Candidate Gate: documentation → freeze candidate SHA
              → deterministic verification
              → one independent A/B/C review + full-spec gap
              → Full CI on exact SHA
Delivery Gate: confirmation → authorized same-SHA promote → delivery → closure
```

Gate 结果与 Delivery 状态分开持久化：Candidate 可以 `PASS`，而 Delivery 同时为 `not-required`、`not-authorized`、`pending` 或 `completed`。

固定 Stage 顺序：

```text
intake → environment → specification → planning → implementation
→ documentation → final-candidate → confirmation → delivery → closure
```

恢复任务从第一个未满足 Gate 的 Stage 继续；禁止重复已验证 Stage 或绕过缺失依赖。

## Stage 路由（每 Stage 一行）

| Stage | 读取 | Gate 概要 |
|---|---|---|
| Intake | [intake-and-environment.md](references/intake-and-environment.md) | 需求摘要确认并持久化 |
| Environment | [intake-and-environment.md](references/intake-and-environment.md) | 路径固定、无并发、基线有效、state 写入 |
| Specification | [specification.md](references/specification.md) | 规格套件批准、版本/指纹/批准依据入 state |
| Planning | [planning-stage.md](references/planning-stage.md) | Phase 档位强制、phase_plan_paths 一致 |
| Implementation | [implementation.md](references/implementation.md) | Phase TDD + Local Gate + 紧凑 review + 风险 Smoke |
| Documentation | [documentation.md](references/documentation.md) | 候选冻结前文档同步 |
| Final Candidate | [candidate.md](references/candidate.md) | 冻结 SHA + 独立 review + full gap + Full CI |
| Confirmation | [candidate.md](references/candidate.md) | 用户继续或回退决策 |
| Delivery | [delivery-and-closure.md](references/delivery-and-closure.md) | exact-SHA + 授权 promote |
| Closure | [delivery-and-closure.md](references/delivery-and-closure.md) | completed Receipt / paused |

- Bootstrap Handoff、Feature state、legacy `current_step` mapping 与恢复：[state-and-handoff.md](references/state-and-handoff.md)；
- Planning 模板（source_manifest / 任务结构）：[planning.md](references/planning.md)；
- 来源/执行包/compact verification 合同：[artifact-contract](../dd-workflow-runtime/references/artifact-contract.md)；
- A/B/C 审查与风险升级：[review-gate](../dd-workflow-runtime/references/review-gate.md)；
- 测试位置与 CI：[test-location](../dd-workflow-runtime/references/test-location.md) 和 [ci](../dd-workflow-runtime/references/ci.md)。

## 通用质量 Gate

- 规格和实现遵循当前 worktree 中的项目规则；
- 每个 AC 映射到计划、测试或明确证据；
- UI AC 不能只由内部状态、mock、日志、layer count 或组件渲染证明；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件。

## 红线

- 没有已批准规格或有效 Bootstrap 输入就修改生产代码；
- 用摘要替代批准原文，或在来源指纹／批准依据失效后继续执行旧包；
- 把验证计划、测试存在／覆盖、本次运行和证据有效性合并成一个“已通过”；
- 把内容批准解释成 Commit／Push／外部动作授权；
- 重问 Handoff 或状态中已解决事实；
- 跨 worktree 引用未提交状态；
- 未通过 Phase Local Gate 就进入下一 Phase；
- Phase ≥ 3 时只用一个总计划文件包含所有 Phase，或使用 planning reference 不传 `split_mode` 与 `phase_list`；
- 用内部状态宣称 UI 已验证；
- 完整 CI 没有验证最终候选 SHA 就推进 develop；
- 候选过期或内容变化后仍推进，或 Documentation 在候选冻结后才做；
- 状态未持久化就跨 Stage；
- merge、push 或 cleanup 成功前删除唯一状态；
- Trae 完成后直接结束会话。

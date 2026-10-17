---
name: dd-feature-development-workflow
description: 当实现需要规格套件、分阶段计划、TDD、CI 或用户可见 UI 证据的新功能、大规模重构或 API 迁移时使用；也用于接收 project-bootstrap Handoff，或恢复长期运行的 Feature 工作流。触发词：新特性流程、feature development workflow、规格文档套件先行、分阶段计划、Feature Handoff。
---

# 新特性实现工作流

## 目标

把已确认的 Feature 从需求输入推进到已验证、可恢复的完成状态。主文件拥有整体执行叙事：目标、工作流概览、Stage 路由与跨 Stage 红线，第一次阅读即可理解一个 Feature 从需求到交付怎么走；每个 Stage 的详细规则由对应 reference 唯一拥有，进入具体 Stage 时再按路由表打开。

## 不适用

- Bug 修复：使用 `dd-bug-fix-workflow`；
- 用户明确要先快速拿到可用实现（先跑起来、之后再补齐流程与测试）：使用 `dd-feature-fast-track`；
- 项目级 Bootstrap：使用 `dd-project-bootstrap-workflow`；
- 简单文本或纯文档微调：直接使用对应工具或 writer；
- 只读审查。

小型功能改动**不属于**上述例外：它仍走本工作流，默认按最小任务包组织；change_tier仍按原准入判定，审查独立按实际风险决定，不因少写文档自动判small。

## 工作流怎么运行

一个 Feature 从需求到交付的大致旅程：

1. **新任务首次进入 Intake 时，若目标、范围与成功标准尚不清楚或存在冲突，先用通俗语言复述需求并取得确认**（要解决什么问题、范围边界、成功标准）——防跑偏的闸口；目标/范围/成功标准已清楚（用户请求已写明、或状态/有效 Handoff 已含确认）且无未解决决定时，不机械复述再等一次确认，记录确认依据后直接收集剩余事实；真正不确定、冲突、行为变更或高风险决策仍 ASK；恢复任务若状态已含有效需求确认则复用，不重复 ASK；随后复用已有 Handoff 和已解决事实，不重复询问；
2. **首次建立执行环境时默认新建隔离 worktree，且在修改项目产物（代码、测试、规格、项目文档等交付范围内文件）之前完成**；恢复任务、有效 Handoff 或父工作流已提供的 worktree 必须复用并验证，不重新创建；仅用户明确要求时才允许在当前工作区，且须记录原因；
3. Intake按 [small-change-track.md](references/small-change-track.md) 的原准入判定change_tier（默认full）；两档文档均默认使用一个持久任务包，明确独立消费者才补对应合同，用户或项目明确要求完整套件才调用dd-writing-specs完整路径。文档组织不降低原风险控制；
4. 从已明确且有有效批准依据的目标/验收条件拆Phase与Task，复用持久入口；计划拆分与tracer按现有属主执行，风险档准入保持；
5. 按 Phase → Task → TDD 实现，每个 Phase 必须通过 Local Gate；
6. 根据真实实现同步受影响文档；
7. 完成验证——绑定唯一被验证版本（已提交且内容干净时冻结 `candidate_sha`；未提交时用 `verification_evidence` 的 `implementation_digest` 绑定真实工作树内容，含相关 dirty/未跟踪输入），对照验收条件核对完整性、遗漏和越界，运行项目要求的测试并按 review-gate 风险路由审查（普通改动主 Agent A/B/C 自检，命中风险触发器才升级独立强审），项目要求的 CI 严格绑定同一版本；仍有效的结果直接复用，不无条件全量重跑，但也不可用仅 HEAD 相同掩盖 dirty 变化；
8. 按授权交付——复用已有动作级授权，执行已获授权的提交、推送或合并，交付内容与验证版本一致；只有缺少必要授权或出现新决定才询问，不泛问"继续交付还是回退"；
9. 完成交付、清理、状态收尾和 Host Close。

其中规格、计划、实现、文档形成内容；第 7 步绑定并完成被验证版本的验证（本地验证不以先获得 commit/push 授权为前提），第 8 步只按已有动作级授权推进同一版本；只有 Delivery 推进目标分支，而任何 Stage 的 Git／远端动作都必须服从既有动作级授权。

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

## 看板与接手入口

遵循 [共享持久任务入口约定](../dd-workflow-runtime/references/state.md#持久任务入口)：复用同一任务专属入口，不给每个skill另建看板。下文的入口均指该既有入口。

## 核心不变量

1. 没有已批准规格，不修改生产代码；
2. 已解决事实继承，状态和仓库证据支持恢复，不重复询问；
3. 每个 AC 必须能追到 Task 和 Test/Evidence，关系在计划与验证证据中紧凑表达，不维护独立追溯表镜像；
4. 每个 Phase 必须通过 Local Gate 才能继续；
5. 用户可见行为必须有用户可见证据；
6. 被验证版本必须唯一绑定：审查、缺口核对与项目要求的 CI 绑定同一个版本身份——已提交且内容干净时为冻结 `candidate_sha`；未提交或有相关 dirty/未跟踪输入时用 `verification_evidence` 的 `implementation_digest` 绑定真实工作树内容，不为拿 SHA 强制提交，也不用内容摘要冒充 `candidate_sha`；
7. 内容批准、测试 PASS、审查者 PASS 只证明 Workflow Gate，不自动产生 Git 或外部动作授权。
8. Tracer 决策必须闭环：Planning 判定 `required`/`skipped`；`required` 时 Phase 1 前 Phase 0 必须 `passed`，`skipped` 时必须有 `reason`；schema／evidence 唯一属主为 `dd-workflow-runtime/references/tracer-contract.md`，本文件只决定何时调用。
9. 风险档与文档组织分离：原small准入、tracer/Local Gate和项目要求的验证不因最小任务包降低；审查等级按实际风险决定；出现未决产品决定才请求内容确认。
10. 内容确认围绕未解决的产品决定、范围变化、高风险与动作授权，不围绕文件数量：目标已明确、批准仍有效、无新增语义的机械整理不反复 ASK；模糊或冲突时仍澄清。
11. 任意变更先判影响：与当前版本身份、范围或环境失配的证据失效并重做，未受影响且仍有效的结果直接复用；仅 HEAD 相同但 dirty/未跟踪输入已变化必须重验，远端 base 前进本身不使未受影响的本地验证失效。

## Stage / Gate 图

五个对外 Gate 是内部十个可恢复 Stage 的聚合命名；内部仍按 Stage 推进。

```text
Source Gate:   intake → environment → specification
Plan Gate:     planning
Phase Gate:    implementation (× N Phase)
Candidate Gate: documentation → bind verified content
              → project-required verification + risk-based review
              → reuse valid evidence; CI only when project requires
Delivery Gate: reuse existing authorization → authorized actions → closure
```

候选 Gate 只产出并验证可交付候选，不更新 develop/main；目标分支推进只发生在 Delivery Gate。

Gate 结果与 Delivery 状态分开持久化：Candidate 可以 `PASS`，而 Delivery 同时为 `not-required`、`not-authorized`、`pending` 或 `completed`。

固定 Stage 顺序：

```text
intake → environment → specification → planning → implementation
→ documentation → final-candidate → confirmation → delivery → closure
```

恢复任务从第一个未满足 Gate 的 Stage 继续；禁止重复已验证 Stage 或绕过缺失依赖。

## Stage 路由（每 Stage 一行）

| Stage | 实际要做什么 | 完成标志 | 详细规则 |
|---|---|---|---|
| Intake | **目标/范围/成功标准不清或存在冲突时，先用通俗语言复述需求并取得用户确认**（目标已清楚且无未解决决定时不机械复述再等一次确认，记录确认依据；恢复任务状态已含有效确认则复用，不重复 ASK），再确认 Feature 的目标、范围、成功标准、失败路径、兼容性及可验证 AC，只补尚未解决的 blocker；同时判定 `change_tier`（默认full）并写 `tier_rationale`（`small` 逐条证明原准入条件），并建立或复用持久任务入口（见[看板与接手入口](#看板与接手入口)） | 目标/范围/成功标准已确认或确认依据已记录，档位与理由已持久化，持久任务入口已建立或复用 | [intake-and-environment.md](references/intake-and-environment.md)／[small-change-track.md](references/small-change-track.md) |
| Environment | **首次建立执行环境时默认新建隔离 worktree，且在修改项目产物之前完成**；恢复任务、有效 Handoff 或父工作流已提供的 worktree 必须复用并验证；仅用户明确要求时才允许在当前工作区并记录原因。验证基线和并发状态。**worktree 与分支确定后、Environment Gate 前，必须按 [task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 完成一次外部任务绑定尝试——需要建立首张绑定时该尝试包含创建并绑定一张 GitHub Issue，具体复用还是创建由 §3 唯一规定；并在该 Gate 前运行 `dd-workflow-runtime/agents/validate-tracking-binding.py --state <state_file>` 通过** | worktree 已新建或已复用并验证，工作环境与状态一致，绑定尝试结果已按 owner 合同记录且判定器通过，可安全进入规格阶段 | [intake-and-environment.md](references/intake-and-environment.md) |
| Specification | 两档默认复用一个持久任务包；明确消费者只补对应合同，完整套件仅按明确要求产出 | 目标/范围/验收条件与关键决定有有效批准依据 | [specification.md](references/specification.md) |
| Planning | 从已批准规格生成 Phase 和可执行 Task 包，建立 AC → Task → Test/Evidence 映射（紧凑表达于计划内，不维护独立追溯表），并判定 tracer（required/skipped，按 tracer-contract §3 风险判定）；Phase 数量与计划文件组织按 planning-stage 拆分档位规则（`small` 档同样适用） | 所有 Phase/Task 输入输出、写入范围、验证方式和停止条件都明确，tracer 决策已记录 | [planning-stage.md](references/planning-stage.md)／[small-change-track.md](references/small-change-track.md) |
| Implementation | 按当前 Task 的 `anchors`、全局约束、Out of Scope、失败路径及必要集成输入选择性读取规格（不完整重读）；按 Phase 执行 Task 并采用 TDD；每个 Phase 通过 Local Gate 并完成按风险路由的紧凑 Phase 复核（命中风险触发器时升级独立强审）；高风险 UI 按风险触发远程 Smoke CI；Local Gate 未通过不得进入下一 Phase | 全部 Phase 已验证，无未解释的当前 Phase 缺口 | [implementation.md](references/implementation.md) |
| Documentation | 根据最终已验证行为判断哪些长期文档需要更新、无需更新或已过期；无受影响合同时可给出可验证的"本次无需修改合同"结论，不强制制造新文档或等待批量同步 | 文档与即将冻结的实现一致，或无需修改结论附影响判定与理由 | [documentation.md](references/documentation.md) |
| Final Candidate | 绑定唯一被验证版本（已提交且内容干净 → 冻结 `candidate_sha`；未提交 → 用 `verification_evidence` 的 `implementation_digest` 绑定真实工作树内容，含相关 dirty/未跟踪输入）；对同一版本做确定性验证、对照验收条件核对完整性／遗漏／越界、按 [review-gate](../dd-workflow-runtime/references/review-gate.md) 风险路由审查（未命中风险触发器为主 Agent A/B/C 自检，命中则升级独立强审并覆盖全局不变量／负向要求／迁移兼容）和项目要求的 CI（严格绑定该版本，仍有效的同版本结果复用）。候选 Gate 只产出并验证可交付候选，不推进目标分支 | review / gap / CI 均绑定同一被验证版本；项目要求的 CI 未运行、未绑定或未经授权时记为明确缺口，不得放行 | [candidate.md](references/candidate.md)／[small-change-track.md](references/small-change-track.md) |
| Confirmation | 复用已有动作级授权，只在缺少必要授权或出现新决定时询问；无新决定不泛问"继续交付还是回退"，不修改被验证内容 | 继续或回退的决策已记录并持久化；仅当决定继续时才进入 Delivery | [candidate.md](references/candidate.md) |
| Delivery | 仅在已有 action-specific authorization 的范围内推进同一个被验证版本；未要求的动作记 `not-required`，未获授权的动作记 `not-authorized` 并停在该动作边界 | 要求且获授权的交付动作都有证据；授权或 CI 缺口如实保留 | [delivery-and-closure.md](references/delivery-and-closure.md) |
| Closure | 验证最终状态、写 Completion Receipt、按规则清理并完成 Host Close | 成功路径的状态或 Completion Receipt 为 `completed`，所需清理已验证并按宿主合同收尾；`paused` 不是完成 | [delivery-and-closure.md](references/delivery-and-closure.md) |

- 改动档位（`change_tier` 唯一属主，含默认档位、显式触发、升级、不可省清单与恢复）：[small-change-track.md](references/small-change-track.md)；
- Bootstrap Handoff、Feature state、legacy `current_step` mapping 与恢复：[state-and-handoff.md](references/state-and-handoff.md)；
- Planning 模板（source_manifest / 任务结构）：[planning.md](references/planning.md)；
- 来源／执行包／验证证据包／生命周期共享合同：[artifact-contract](../dd-workflow-runtime/references/artifact-contract.md) 是路由器，详细合同在其三个分文件 `artifact-source-and-packet.md`／`artifact-verification.md`／`artifact-lifecycle.md`；
- A/B/C 审查与风险升级：[review-gate](../dd-workflow-runtime/references/review-gate.md)；
- 测试位置与 CI：[test-location](../dd-workflow-runtime/references/test-location.md) 和 [ci](../dd-workflow-runtime/references/ci.md)；
- Tracer 贯穿式最小闭环（Phase 0 触发/证据/恢复三态）：[tracer-contract](../dd-workflow-runtime/references/tracer-contract.md)；
- 外部任务绑定与投影（GitHub Issue 索引、checkpoint、跨机器定位与看板规则）：[task-tracking](../dd-workflow-runtime/references/task-tracking.md)。

## 通用质量 Gate

- 规格和实现遵循当前 worktree 中的项目规则；
- UI AC 不能只由内部状态、mock、日志、layer count 或组件渲染证明；
- 自动化不可行时保留手动步骤、证据路径、责任人和风险；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件。

## 红线

### 规格与证据

- 没有已批准规格或有效 Bootstrap 输入就修改生产代码；
- 用摘要替代批准原文，或在来源指纹／批准依据失效后继续执行旧包；
- 把验证计划、测试存在／覆盖、本次运行和证据有效性合并成一个“已通过”；

### 授权边界

- 把内容批准、测试 PASS 或审查者 PASS 解释成 Commit／Push／外部动作授权；

### 状态与恢复

- 重问 Handoff 或状态中已解决事实；
- 跨 worktree 引用未提交状态；
- 状态未持久化就跨 Stage；
- merge、push 或 cleanup 成功前删除唯一状态；

### 阶段纪律

- 目标/范围/成功标准不清、存在冲突或涉及行为变更/高风险决策时未澄清确认就开始收集规格或修改项目产物（目标已清楚且无未解决决定时不机械复述等待，但确认依据必须记录；恢复任务状态已含有效确认的除外）；
- 首次建立执行环境时未新建 worktree 就修改项目产物（恢复/Handoff/用户明确要求的例外除外）；
- Environment Gate 前未按 [task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 完成外部任务 Issue 的绑定尝试并把结果落盘，或未让 `validate-tracking-binding.py` 通过就推进——只登记调用点不执行，等同未尝试；
- 未通过 Phase Local Gate 就进入下一 Phase；
- Phase ≥ 3 时只用一个总计划文件包含所有 Phase，或使用 planning reference 不传 `split_mode` 与 `phase_list`；
- 项目要求 CI 但未绑定被交付版本、未执行或未经授权就放行合并，或用本地结果冒充必需 CI、自行豁免；
- 为获得 SHA 强制提交，或把内容摘要写入 `candidate_sha` 冒充 Git 提交；
- 仅 HEAD 相同但 dirty／未跟踪输入已变化时复用旧证据，或因远端 base 前进废弃未受影响的本地验证；base 变化影响合并产物时不重验合并结果；
- 候选过期或内容变化后仍推进，或 Documentation 在被验证版本绑定后才做；
- `change_tier=small` 时省掉 Intake 确认纪律、mini-spec 批准、红绿实际运行、Local Gate、UI 真实路径证据、被验证版本绑定与项目要求的同版本 CI 或动作授权中的任一项；
- 命中 `full` 显式触发条件仍按 `small` 收尾，或先按 `small` 做完后补材料；
- 把档位当风险控制替代：命中 review-gate 风险触发器不升级审查等级与 gap 覆盖，或命中 tracer 风险分类仍默认 `skipped`；
- 用文件数代替风险控制：默认生成完整套件"保险"，或高风险改动只靠最小包而不升级验证；
- 用默认最小任务包静默覆盖项目硬规则：项目明确要求完整套件或逐份批准时必须遵循，冲突如实报告交主模型/用户裁决。
- 未要求 merge 时以"目标分支未含候选"为由阻塞已授权局部任务的收尾，或反过来把局部收尾宣称成已合并／已发布。

### UI 证据与会话收尾

- 用内部状态宣称 UI 已验证；
- Trae 完成后直接结束会话。

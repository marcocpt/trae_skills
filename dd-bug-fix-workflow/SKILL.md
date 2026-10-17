---
name: dd-bug-fix-workflow
description: 当修复需要证据驱动根因调查、隔离环境、TDD、回归 CI、真实应用验证或跨会话恢复的 Bug 时使用；也用于继续已有 fix worktree 或处理压缩后状态不一致。触发词：修 bug 流程、bug fix workflow、继续修复、根因调查、复现测试。
---

# Bug 修复工作流

## 目标

把明确的 Bug 症状推进到根因已证明、修复已验证、受影响文档已按需处理、交付已完成的可恢复状态。主文件只保留编排、状态和 Gate；诊断、验证、交付与清理细节按当前 Stage 读取 references。

## 不适用

- 新功能或行为扩展：使用 `dd-feature-development-workflow`；
- 用户明确要先快速修好能马上用（先让症状消失、之后再补齐证据与回归）：使用 `dd-bug-fast-track`；
- 为新架构假设先打贯穿式最小闭环（tracer / Phase 0）：属新功能范畴，由 `dd-feature-development-workflow` 承载，Bug 修复不引入 tracer；
- 项目 Bootstrap：使用 `dd-project-bootstrap-workflow`；
- 简单文本或纯文档修改；
- 用户只要求诊断、未授权修复时：停在 Diagnosis 结论，不实施修复。

## 运行时

开始或恢复时调用 [dd-workflow-runtime](../dd-workflow-runtime/SKILL.md)：

```yaml
workflow_type: bug-fix
host: auto
requested_entry: user-request
state_file: $(git rev-parse --git-dir)/bug-fix-state.json
stage_graph: bug-fix-stage-graph
required_exit_stages:
  - intake
  - environment
  - diagnosis-and-repair
  - sync-and-ci
  - user-verification
  - documentation
  - delivery
  - integration-and-closure
delivery_policy: project-rules
```

遵循运行时的 Preflight、原子状态、Gap Scan、Stage Contract、Completion Receipt 和 Host Close。保留 `current_step` 作为旧状态兼容字段，但它必须与 `current_stage` 一致。

## 核心原则

1. 症状、期望行为与修复范围不清楚、相互冲突，或涉及行为变更与高风险决策时，先复述确切症状与期望行为并取得确认；已清楚且有用户执行指令时不机械复述等待；
2. 没有根因证据，不提出修复方案；
3. 先复现，再修复；
4. 一次只验证一个假设、一个变量；
5. 未经批准不改变既有行为；
6. 用户可见修复必须有真实路径证据；
7. 每次外部转换前先持久化状态；
8. **可本地执行的真实复验不以先 push 为前提**；同步 base、commit、push 与 CI 按项目规则与已有动作级授权执行，未获授权就停在动作边界并记录缺口，不伪造 CI／merge 完成；未提交或有相关 dirty／未跟踪输入时，用 `implementation_digest` 绑定真实工作树内容作为被验证版本，不为拿 SHA 强制提交，也不用内容摘要冒充提交 SHA；
9. 修复效果的用户复验与 Git 交付批准是两个授权，互不替代；行为变化仍先裁决；
10. Trae 完成前必须做最终 ASK。

## Stage Graph

```text
Preflight
  ↓
Intake
  ↓
Environment
  ↓
Diagnosis and Repair
  ↓
Sync and CI
  ↓
User Verification
  ├─ fixed → Documentation
  └─ not fixed → Diagnosis / Environment
                 ↓
             Delivery
                 ↓
       Integration and Closure
```

新任务按依赖推进；恢复任务从第一个未满足 Gate 的 Stage 继续。不同 Stage 不并行执行，但同一 Stage 内可并行进行互不修改状态的只读证据检查。

## Stage Contracts

| Stage | Requires | Produces | Next | Recovery evidence |
|---|---|---|---|---|
| Intake | 用户问题、可用历史 | 症状、期望、日志与授权边界；持久任务入口已建立或复用 | Environment | decisions、日志路径 |
| Environment | Intake Gate | 固定 worktree、初始 state | Diagnosis and Repair | Git 路径、基线结果 |
| Diagnosis and Repair | 可复现问题 | 失败证据、根因、最小修复 | Sync and CI | debug log、测试、diff |
| Sync and CI | Repair Gate | 已绑定的被验证版本与复验证据；获授权时的 fix commits 与同版本 CI（未授权/未运行记明确缺口） | User Verification | 绑定指纹、commits、CI run、同步结果 |
| User Verification | 可操作真实产物 | 用户已修复或回退决策 | Documentation / rollback | 启动结果、decision |
| Documentation | 用户确认修复 | 受影响合同按需处理结论（含可验证的无需修改结论），或行为变化的决策/范围裁决 | Delivery | 文档版本、结论、提交 |
| Delivery | Documentation Gate | lint/push/CI/同步证据 | Integration and Closure | SHA、CI run、远端状态 |
| Integration and Closure | 所有修复 Gate | merge SHA、post-merge CI、Receipt 或 paused state | Host Close / resume | merge、run、Receipt、状态 |

## Bug State

除运行时通用字段外，Bug 工作流记录领域增量状态：症状与期望行为、复现步骤、日志来源、调试日志路径、失败测试、根因、修复提交、CI 运行、用户验证结论、文档路径、merge commit。Bug 领域增量字段 schema、旧状态 `current_step` 映射与字段冲突/状态缺失的恢复规则见 [state.md](references/state.md)，状态在每个 Stage Gate 通过后原子写入。

Bug 工作流与 Feature 对等：在 Environment（worktree 与分支确定后、Environment Gate 前）执行 [task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 定义的 tracking 绑定尝试并按该合同持久化结果，**不阻塞本 Stage**；`bug_id` 不重载为 Issue 号，跨设备任务索引用共享 `tracking` 字段承载。

## 看板与接手入口

遵循 [共享持久任务入口约定](../dd-workflow-runtime/references/state.md#持久任务入口)：复用同一任务专属入口，不给每个skill另建看板。下文的入口均指该既有入口。

## Stage 路由

### Intake

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Intake。

**新任务首次进入 Intake 时，若症状、期望行为与修复范围不清楚或相互冲突，必须先用通俗语言向用户复述三件事：症状是什么、期望行为是什么、准备在什么范围内修**，取得用户确认后才算 Intake 通过——这是防跑偏的闸口；三件事已清楚（用户请求已写明，或状态/Handoff 已载明）且无未解决决定时，不机械复述再等一次确认，记录确认依据后直接扫描日志与收集剩余事实。模糊、冲突、行为变更或高风险决策仍 ASK。恢复任务若状态已含有效需求确认，则复用确认结果，不重复 ASK。Intake 同时建立或复用持久任务入口（见[看板与接手入口](#看板与接手入口)）。随后扫描可用日志但不猜测来源，只询问仍缺失的 blocker。Gate：症状/期望/范围已确认或确认依据已记录、问题边界确认、日志选择记录、工作环境决策已取得或可从状态恢复、持久任务入口已建立或复用。

### Environment

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Environment。

**首次建立执行环境时默认新建隔离 fix worktree，且必须在修改任何项目产物（代码、测试、规格、项目文档等交付范围内文件）之前完成**；恢复任务、有效 Handoff 或父工作流已提供的 worktree 必须复用并验证，不重新创建。仅当用户明确要求在当前工作区修改时才例外，并把例外原因写入状态；不允许默认就在当前工作区改代码。runtime 状态文件与工作流内部证据文件按 runtime 合同处理，不属于项目产物修改。**worktree 与分支确定后、Environment Gate 前，必须按 [task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 完成一次外部任务绑定尝试——需要建立首张绑定时该尝试包含创建并绑定一张 GitHub Issue，具体复用还是创建由 §3 唯一规定——并在该 Gate 前运行 `dd-workflow-runtime/agents/validate-tracking-binding.py --state <state_file>` 通过。** Gate：worktree 已新建或已复用并验证、路径固定、无并发工作流、工作区与基线证据有效、Bug state 已原子写入、绑定尝试结果已按 owner 合同记录且判定器通过。

### Diagnosis and Repair

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Reproduction、Root Cause、Repair 和 Review。

先写或定义稳定复现，再沿数据流调查并用最小实验验证单一假设。只有根因成立后才实施最小修复和重构。Gate：失败证据、根因证据、绿灯证据和影响边界完整。

若用户只授权诊断，在输出根因与证据后停止，不进入 Repair；不得把诊断请求扩成修复授权。

### Sync and CI

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Sync and CI。

**先在当前允许范围完成可本地执行的真实复验，再按项目规则与已有动作级授权做同步、提交与 CI**：

1. 可本地执行的复验不受 push 前置约束：在 fix worktree 重跑复现红灯／绿灯、受影响旧行为的定向回归与必要的真实路径证据（复现、根因、最小修复、红绿回归、真实路径证据不因精简而删减）；**不要求必须先 push 才能做这些复验**；
2. 按 merge-only 项目规则 fetch 并比较 base，需要同步时按 `dd-git-workflow/merge` 同步，冲突在 fix 分支解决并重新验证；
3. 按逻辑暂存生成 Conventional Commit 并提交修复、测试、必要文档和证据——**未获 commit 授权时不提交**，此时用 `verification_evidence.result.bindings.implementation_digest` 绑定真实工作树内容（含相关 dirty／未跟踪输入）作为被验证版本，不得用内容摘要冒充提交 SHA；
4. push fix 分支与回归 CI 按项目规则与已有动作级授权执行；项目要求 CI 时严格绑定被交付版本，仍有效的同版本结果复用；**未运行、未绑定或未经授权／无法执行时记为明确缺口，不得改成本地通过、不得自行豁免、不得留空冒充**；
5. 按需安全同步 AI-test。

Gate：被验证版本绑定、提交、CI 与同步证据准确（或缺口如实记录），`current_stage=user-verification`。

### User Verification

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Real-path Verification。

必须先启动或提供真实可操作产物，再 ASK 用户是否修复。已修复进入 Documentation；未修复在同一环境回到 Diagnosis，或按用户决定重建 Environment。任何回退都先更新状态。

### Documentation

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Documentation。

**纯恢复既定行为（不改变约定行为）时，不默认补齐 Requirements／Design／Test Matrix**：只处理受影响的当前合同与使用说明（按需），可以给出可验证的"无需修改合同"结论；**修复实际上改变约定行为时，必须标出决策/范围变化并请求用户裁决**，不得当成普通修 bug 直接放行。Gate：文档与修复一致，版本/证据已更新或有明确无需更新结论；行为变化已裁决。

### Delivery

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Delivery。

**复用已有动作级授权**完成 lint、必要验证、commit、push、同版本 CI 和允许的 AI-test 同步；只有缺少必要授权或出现新决定才 ASK。未要求的动作记 `not-required`，未获授权的动作记 `not-authorized` 并停在该动作边界；conditional／no-op 阶段写清实际结论，不伪造 CI／merge 完成。用户已确认"修复效果"不等于 Git 交付批准，反之亦然。Gate：必需 Delivery 动作有证据，失败项已解决或由用户明确处置。

### Integration and Closure

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Integration and Closure。

合并前写 `in_progress`，只在记录的主仓库路径操作；merge 成功后执行合并后 CI。清理会删除活动状态时先写 Completion Receipt，再删除明确的 worktree/分支。

选择暂停时设置 `paused`，不触发完成 ASK。真正完成后设置 `status=completed`，仅 standalone 会话按 [dd-workflow-runtime 宿主结束合同](../dd-workflow-runtime/SKILL.md) 收尾：Trae 结构化 ASK `结束本次任务 / 还有其他任务`（null 重问），Codex 正常交付最终摘要。

## 通用质量 Gate

- 修复测试必须因正确原因先失败；
- 根因必须由日志、数据流、对比或最小实验支持；
- 不得为了绿灯随意修改旧测试预期；
- UI 修复不能只用内部状态、mock 或日志证明；
- XCTest/XCUITest 等执行位置遵循 `dd-workflow-runtime/test-location` 和 `dd-workflow-runtime/ci`；
- 文档检查不能只看修改文件列表；
- Git 操作遵循 `dd-git-workflow`，不混入无关脏文件；
- 没有子 Agent 时由主线程执行同义复核，不降低检查项。

## 红线

- 症状/期望/范围不清楚、存在冲突或涉及行为变更/高风险决策时未澄清确认就开始诊断或修复（已清楚且有执行指令时不机械复述等待，但确认依据必须记录；恢复任务状态已含有效确认的除外）；
- 首次建立执行环境时未新建 worktree 就修改项目产物（恢复/Handoff/用户明确要求的例外除外）；
- Environment Gate 前未按 [task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 完成外部任务 Issue 的绑定尝试并把结果落盘，或未让 `validate-tracking-binding.py` 通过就推进；
- 未稳定复现或定义失败证据就写修复；
- 未完成根因调查就提出确定性修复；
- 一次修改多个变量后宣称根因已证明；
- 未经确认改变既有需求或回归预期；
- 修复实际上改变约定行为，却未标出决策/范围变化并请求用户裁决就当成普通修 bug 放行；
- 未执行真实路径却宣称 UI Bug 已修复；
- CI 结果与被交付版本不一致；或项目要求 CI 但未执行、未绑定被交付版本、未经授权即宣称通过，或用本地结果冒充、自行豁免；
- 以"必须先 push"为由跳过或推迟可本地执行的真实修复复验，或为拿到 SHA 强制提交／用内容摘要冒充提交 SHA；
- 把用户已确认修复效果当成 Git 交付批准，或反过来用 Git 授权替代必要的人工复验；
- 状态缺失就默认从 Intake 重启；
- 状态未持久化就跨 Stage；
- merge、push、cleanup 成功前删除唯一状态；
- 在 fix 分支夹带无关公共文件修改；
- Trae 完成后直接结束会话。

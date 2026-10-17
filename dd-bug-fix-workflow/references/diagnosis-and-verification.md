# Bug Diagnosis and Verification

只在 Intake、Environment、Diagnosis and Repair、Sync and CI 或 User Verification Stage 读取。

## 目录

- [Intake](#1-intake)
- [Environment](#2-environment)
- [Reproduction](#3-reproduction)
- [Root Cause](#4-root-cause)
- [Repair](#5-repair)
- [Review](#6-review)
- [Sync and CI](#7-sync-and-ci)
- [Real-path Verification](#8-real-path-verification)

## 1. Intake

**症状、期望行为与修复范围不清楚或相互冲突时，先向用户复述，再扫描日志。** 用通俗语言（不堆术语、不甩 finding 编号）复述三件事，并取得用户确认：

1. 我理解的症状是什么；
2. 期望的正确行为是什么；
3. 打算在什么范围内修、不碰什么。

复述与用户描述不一致时以用户为准修正后再确认；未获确认不得进入 Environment。三件事已清楚（用户请求已写明，或状态/Handoff 已载明）且无未解决产品决定时，**不机械复述再等一次确认**：记录确认依据（来源、复述要点、确认方式）后直接扫描日志与收集剩余事实。机械整理与无新增语义的同步不反复 ASK；模糊、冲突、行为变更或高风险决策仍澄清。

**恢复任务若状态已含有效需求确认（`requirement_confirmed` 或等价字段），则复用确认结果，不重复 ASK。**

确认后再从当前 worktree 和约定的测试 worktree 扫描最新日志候选，只列文件名、来源和时间，不预加载所有日志。

按需收敛：

1. 精确症状；
2. 稳定/偶发和频率；
3. 输入、环境与前置状态；
4. 期望行为；
5. 最近一次正常版本或对照实现；
6. 用户允许的修复范围；
7. 日志来源；
8. 工作环境。

已有状态、日志或用户请求能回答的事实不得重复询问。结构化 ASK 一次只问一个 blocker；可并行扫描日志与 Git 历史，但不得并行修改状态。

Gate：

- 症状/期望/范围已确认，或确认依据已记录；
- 症状与期望无歧义；
- 至少有日志/复现路径/明确无日志结论之一；
- 修复授权边界明确；
- 环境选择已确定；
- `current_stage=environment`。

## 2. Environment

**首次建立执行环境时默认新建隔离 fix worktree，且必须在修改任何项目产物（代码、测试、规格、项目文档等交付范围内文件）之前完成。** 恢复任务、有效 Handoff 或父工作流已提供的 worktree 必须复用并验证，不重新创建。只有用户明确要求在当前工作区修改时才例外，并把例外原因写入状态；不允许默认就在当前工作区改代码。runtime 状态文件与工作流内部证据文件按 runtime 合同处理，不属于项目产物修改。

- 新建隔离 fix worktree（首次建立执行环境时的默认）；
- 复用已有 worktree（恢复任务 / 有效 Handoff / 父工作流提供，仅验证不重建）；
- 使用当前工作区（仅限用户明确要求的例外，须记录原因）。

创建或验证遵循 `dd-git-workflow/worktree`、`dd-git-workflow/branch`、`dd-workflow-runtime/ci` 和项目规则。记录：

```yaml
main_root: /absolute/path
worktree_dir: /absolute/path
worktree_path: /absolute/path
base_branch: develop
fix_branch: fix/F0-short-description
```

检查：

- 当前路径是目标 worktree；
- 无其他 active/paused/handoff-ready 工作流；
- 无未解释的脏文件；
- 基线测试/CI 证据可用；
- 只能参考该 worktree 的未提交状态；
- Environment Gate 前执行 [task-tracking](../../dd-workflow-runtime/references/task-tracking.md) §3 定义的 tracking 绑定尝试，并按该合同持久化结果；tracking 对本 Stage 的影响完全由该合同定义，**不阻塞本 Stage**。

基线失败必须区分既有失败与当前 Bug；只有失败、冲突或风险需要 ASK。

Gate：Bug state 原子写入，tracking 绑定尝试的结果已按 owner 合同持久化；`current_stage=diagnosis-and-repair`。

## 3. Reproduction

优先写最小自动化复现：

- 一次只验证一个行为；
- 使用真实生产入口，避免不必要 mock；
- 断言体现用户可观察结果；
- 确认因目标 Bug 失败，而不是拼写、fixture 或环境错误。

普通单元/XCTest 可在稳定本地环境验证红灯。环境敏感 UI 测试按项目 CI 策略执行；未执行前只能写“测试已定义，红灯待 CI”，不能声称已验证。

无法自动化时写可重复手动脚本：前置、操作、预期、实际、截图/录屏/日志路径和环境。

调试记录写入项目允许的 `debug-logs/YYYY-MM-DD-<issue>.md` 或项目规定位置。

## 4. Root Cause

固定顺序：

1. 阅读完整错误、堆栈和相关日志；
2. 稳定复现；
3. 检查近期变更；
4. 在组件边界记录输入/输出；
5. 从错误值沿调用链向上追踪；
6. 找到正常工作的同类路径逐项对比；
7. 提出单一假设：“X 是根因，因为 Y”；
8. 用只改变一个变量的最小实验验证；
9. 失败则记录反证并提出新假设。

根因结论至少包含：

- 触发条件；
- 错误数据/状态从何处产生；
- 为什么对照路径不失败；
- 最小实验结果；
- 受影响和不受影响边界。

没有这些证据不得进入 Repair。

## 5. Repair

- 实施针对根因的最小改动；
- 不捆绑无关优化或重构；
- 运行复现测试确认绿灯；
- 运行受影响旧行为的定向回归；
- 在绿灯基础上做必要重构；
- 清理临时诊断代码，保留符合项目规范的正式日志。

修改旧测试预期前先证明需求确实改变，并取得项目要求的确认。

连续三轮修复无效时 ASK：

- 带新证据继续 Root Cause；
- 回退 Environment/重建 worktree；
- 停止并保留证据。

## 6. Review

复核：

1. 修复是否对应已证明根因；
2. 是否遗漏受影响入口和旧行为；
3. 测试是否绑定实现或过度 mock；
4. 日志、错误、并发和边界；
5. UI 是否有用户可见证据；
6. 临时代码、TODO、未解释 skip；
7. diff 是否超出授权范围。

必须修复项修复后重跑相关测试和复核。Gate 通过后写 `root_cause`、`failing_test`、绿灯证据，更新 `current_stage=sync-and-ci`。

## 7. Sync and CI

**先在当前允许范围完成可本地执行的真实复验，再按项目规则与已有动作级授权做同步、提交与 CI**：

1. **可本地执行的复验不受 push 前置约束**：在 fix worktree 重跑复现红灯／绿灯、受影响旧行为的定向回归与必要的真实路径证据（§3 复现、§4 根因、§5 最小修复、红绿回归、§8 真实路径证据不因精简而删减）；**不要求必须先 push 才能做这些复验**；
2. 项目/集成需要且已有远端访问/同步授权时，fetch明确base并比较本地/远端；不把fetch作为本地复验前提；需要同步时按 `dd-git-workflow/merge` 使用 merge-only；
3. 冲突在 fix 分支解决并重新验证；
4. 精确检查 diff 和状态，按逻辑暂存，生成 Conventional Commit，提交修复、测试、必要文档和证据——**未获 commit 授权时不提交**，此时用 `verification_evidence.result.bindings.implementation_digest` 绑定真实工作树内容（含相关 dirty／未跟踪输入）作为被验证版本，**不得用内容摘要冒充提交 SHA**；
5. push fix 分支：按已有动作级授权执行；未授权停在动作边界并记录 `not-authorized`，不因此判定本地复验无效；
6. **CI 是否必需、范围与执行位置由项目规则决定**（[test-location](../../dd-workflow-runtime/references/test-location.md)、[ci](../../dd-workflow-runtime/references/ci.md)）：必需时严格绑定被交付版本（提交级远程CI使用真实提交SHA；未提交的本地验证另用implementation_digest，不把工作树摘要当远程CI的head_sha），仍有效的同版本结果复用；未执行、未绑定或未经授权／无法执行时记为明确缺口，**不得改成本地通过、不得自行豁免、不得留空冒充**；
7. 记录 run ID/URL、被交付版本和结果。

不得用旧 CI、不同版本或本地 UI 结果替代项目要求的远程回归。

AI-test 同步前先检查目标 worktree 是否 dirty。只有 clean 才允许执行精确 reset 脚本；dirty、脚本失败或目标不明确时 ASK，不得直接 `reset --hard`。

Gate：

```yaml
fix_commits:
  - <sha>
ci_runs:
  - sha: <sha>
    result: passed
current_stage: user-verification
```

未提交时 `fix_commits` 为空，并把 `not-required`／`not-authorized` 原因与 `implementation_digest` 绑定写入状态；CI 未运行不得写 `result: passed`，已提交但 CI 未运行或未绑定被交付版本时不得给出"已通过"结论。

## 8. Real-path Verification

必须先构建并启动真实应用/服务或提供可操作产物，再询问用户。

- Swift/Xcode：遵循 `dd-workflow-runtime/ci` 的 workspace/project、scheme、签名和产物探测；
- Web：启动项目定义的 dev/test server；
- 其他项目：使用项目文档的真实入口；
- 启动失败时提供准确错误，ASK 重试、用户自行验证或停止。

启动成功后提示用户按复现步骤验证，再 ASK：

- 已修复；
- 未修复，在同一 worktree 回到 Diagnosis；
- 未修复，重新选择 Environment。

每个选择先原子更新 `current_stage`、`user_verified` 和 `rollback_from`，再跳转。未收到用户验证时不得把 UI Bug 标记为完成。

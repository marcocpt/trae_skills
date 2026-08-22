---
name: dd-bug-fix-workflow
description: 当修复需要证据驱动根因调查、隔离环境、TDD、回归 CI、真实应用验证或跨会话恢复的 Bug 时使用；也用于继续已有 fix worktree 或处理压缩后状态不一致。触发词：修 bug 流程、bug fix workflow、继续修复、根因调查、复现测试。
---

# Bug 修复工作流

## 目标

把明确的 Bug 症状推进到根因已证明、修复已验证、文档已同步、交付已完成的可恢复状态。主文件只保留编排、状态和 Gate；诊断、验证、交付与清理细节按当前 Stage 读取 references。

## 不适用

- 新功能或行为扩展：使用 `dd-feature-development-workflow`；
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

1. Restate the exact symptom and expected behavior；
2. No root-cause evidence, no fix proposal；
3. Reproduce before repair；
4. One hypothesis and one variable at a time；
5. Preserve old behavior unless approved otherwise；
6. User-visible fixes require real-path evidence；
7. Persist before every external transition；
8. Trae completion requires a final ASK。

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
| Intake | 用户问题、可用历史 | 症状、期望、日志与授权边界 | Environment | decisions、日志路径 |
| Environment | Intake Gate | 固定 worktree、初始 state | Diagnosis and Repair | Git 路径、基线结果 |
| Diagnosis and Repair | 可复现问题 | 失败证据、根因、最小修复 | Sync and CI | debug log、测试、diff |
| Sync and CI | Repair Gate | fix commits、同 SHA CI | User Verification | commits、CI run、同步结果 |
| User Verification | 可操作真实产物 | 用户已修复或回退决策 | Documentation / rollback | 启动结果、decision |
| Documentation | 用户确认修复 | 同步文档和影响结论 | Delivery | 文档版本、提交 |
| Delivery | Documentation Gate | lint/push/CI/同步证据 | Integration and Closure | SHA、CI run、远端状态 |
| Integration and Closure | 所有修复 Gate | merge SHA、post-merge CI、Receipt 或 paused state | Host Close / resume | merge、run、Receipt、状态 |

## Bug State

除运行时通用字段外记录：

```yaml
bug_id: ""
symptom: ""
reproduction: []
expected_behavior: ""
log_sources: []
debug_log_path: null
failing_test: null
root_cause: null
fix_branch: ""
fix_commits: []
ci_runs: []
user_verified: false
documentation_paths: []
merge_commit: null
```

旧状态中的 `current_step` 映射：

```text
0 → intake
1 → environment
2 → diagnosis-and-repair
3 → sync-and-ci
4 → user-verification
5 → documentation
6 → delivery
7 → integration-and-closure
```

字段冲突时先验证日志、测试、提交、分支、CI 和 merge 证据，再修正状态。状态缺失时至少比较 fix 分支与 base、查询提交/CI/merge；已有修复 commit 时禁止默认重做 TDD。

## Stage 路由

### Intake

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Intake。

复述症状、复现条件和期望行为；扫描可用日志但不猜测来源。只询问仍缺失的 blocker。Gate：问题边界确认、日志选择记录、工作环境决策已取得或可从状态恢复。

### Environment

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Environment。

创建隔离 fix worktree 或验证用户选择的当前 worktree。Gate：路径固定、无并发工作流、工作区与基线证据有效、Bug state 已原子写入。

### Diagnosis and Repair

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Reproduction、Root Cause、Repair 和 Review。

先写或定义稳定复现，再沿数据流调查并用最小实验验证单一假设。只有根因成立后才实施最小修复和重构。Gate：失败证据、根因证据、绿灯证据和影响边界完整。

若用户只授权诊断，在输出根因与证据后停止，不进入 Repair；不得把诊断请求扩成修复授权。

### Sync and CI

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Sync and CI。

按 merge-only 项目规则同步 base，提交修复，对提交 SHA 执行完整回归 CI，并按需安全同步 AI-test。Gate：提交、CI 与同步证据准确，`current_stage=user-verification`。

### User Verification

读取 [diagnosis-and-verification.md](references/diagnosis-and-verification.md) 的 Real-path Verification。

必须先启动或提供真实可操作产物，再 ASK 用户是否修复。已修复进入 Documentation；未修复在同一环境回到 Diagnosis，或按用户决定重建 Environment。任何回退都先更新状态。

### Documentation

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Documentation。

按调用关系、数据流、共享模型和用户流程检查 Requirements、Design、Test Cases 与代码测试。Gate：文档与实际修复一致，版本/证据已更新或有明确无需更新结论。

### Delivery

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Delivery。

完成 lint、必要验证、commit、push、同 SHA CI 和允许的 AI-test 同步。Gate：必需 Delivery 动作有证据，失败项已解决或由用户明确处置。

### Integration and Closure

读取 [delivery-and-closure.md](references/delivery-and-closure.md) 的 Integration and Closure。

合并前写 `in_progress`，只在记录的主仓库路径操作；merge 成功后执行合并后 CI。清理会删除活动状态时先写 Completion Receipt，再删除明确的 worktree/分支。

选择暂停时设置 `paused`，不触发完成 ASK。真正完成后设置 `status=completed`，再按共享运行时执行 Host Close：Trae 必须 ASK `结束本次任务` / `还有其他任务`；Codex 正常交付。

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

- 未稳定复现或定义失败证据就写修复；
- 未完成根因调查就提出确定性修复；
- 一次修改多个变量后宣称根因已证明；
- 未经确认改变既有需求或回归预期；
- 未执行真实路径却宣称 UI Bug 已修复；
- CI 结果与修复 SHA 不一致；
- 状态缺失就默认从 Intake 重启；
- 状态未持久化就跨 Stage；
- merge、push、cleanup 成功前删除唯一状态；
- 在 fix 分支夹带无关公共文件修改；
- Trae 完成后直接结束会话。

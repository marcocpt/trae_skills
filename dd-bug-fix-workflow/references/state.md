# Bug 工作流状态字段与恢复

通用状态合同由 [dd-workflow-runtime/state](../../dd-workflow-runtime/references/state.md) 拥有：分支专用字段 `<BRANCH_FIELD>` 对 bug-fix 解析为 `fix_branch`，由 runtime 拥有，不在本文件重复定义。本文件只定义 Bug 工作流的领域增量字段、legacy 映射与冲突修正规则。

## 领域增量字段

除运行时通用字段（含 `fix_branch`）外记录：

```yaml
bug_id: ""
symptom: ""
reproduction: []
expected_behavior: ""
log_sources: []
debug_log_path: null
failing_test: null
root_cause: null
fix_commits: []
ci_runs: []
user_verified: false
documentation_paths: []
merge_commit: null
```

## 被验证版本与授权缺口

未提交或存在相关 dirty／未跟踪输入时，`fix_commits` 可为空：被验证版本以 `verification_evidence.result.bindings.implementation_digest` 绑定真实工作树内容，**不得用内容摘要冒充提交 SHA**；有 dirty 时不能只绑定 HEAD。`ci_runs` 只在真实运行时记录；项目要求但未运行／未获授权时记 `not-required`／`not-authorized` 与原因，不写 `result: passed`。

旧状态缺 `ci_runs`／`fix_commits`，或仅含旧候选／旧批准字段时，原样保留并兼容读取为线索，不删除、不改写、不销毁唯一记录；缺失一律按"未验证"读取（不得当作已通过），不因缺新字段重启或回退已通过的 Gate。

## 旧状态 `current_step` 映射

`current_step` 是旧状态兼容字段，必须与 `current_stage` 一致：

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

## 字段冲突与状态缺失

字段冲突时先验证日志、测试、提交、分支、CI 和 merge 证据，再修正状态。状态缺失时至少比较 fix 分支与 base、查询提交/CI/merge；已有修复 commit 时禁止默认重做 TDD。

跨 app/会话恢复时先读持久任务入口定位症状、期望、复现、根因、修复证据与下一步（入口建立与路径规则见 [SKILL.md](../SKILL.md) 看板与接手入口节）：入口 + 仓库证据即可离线恢复，不依赖聊天记忆，也不要求必须联网；状态缺失时从仓库证据重建。

恢复写入前必须核实当前代码、dirty diff、实际验证运行与批准范围：旧文档、旧测试报告与旧补丁仅为线索，**证据绑定输入/版本与当前状态不一致时，不得照旧补丁直接覆盖当前文件**，先按证据修正状态再继续。

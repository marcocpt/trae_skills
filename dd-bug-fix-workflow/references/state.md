# Bug 工作流状态字段与恢复

通用状态合同由 [dd-workflow-runtime/state](../../dd-workflow-runtime/references/state.md) 拥有；本文件只定义 Bug 工作流的领域字段、legacy 映射与冲突修正规则。

## 领域字段

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

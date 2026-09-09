本仓库使用 multi-agent-branch-integration，Agent 全自动执行分支动作，用户无需手工同步。

## Agent 开始任务

任何 Agent 在修改代码、测试、文档或其它项目产物前，必须自动执行：

```bash
./scripts/branchctl agent-start
```

Agent 不得要求用户手工执行 preflight、sync、rebase 或 merge。

`agent-start` 自行完成：获取最新集成分支、按项目策略初始化可见性、
按需自动同步一次（private→rebase，shared→merge）、再过 preflight；
只有 `AGENT_START=true` 才能修改项目。

项目默认 `feature.default_visibility = private`，
因此新 feature 无显式可见性时按项目策略自动初始化为 private，
这不是猜测；显式配置永远优先。已显式标记 shared 的分支禁止 rebase。

发生 Git 冲突时：禁止自动解决，保留现场，停止并报告冲突文件。

历史一旦被重写（输出 `PRIOR_EVIDENCE=STALE`），此前绑定旧 SHA 的
送审与证据即作废，Agent 必须重新记录基线并重新送审。

## Agent 完成任务

实现和测试完成后（Agent 自行完成修改与提交），必须自动执行：

```bash
./scripts/branchctl agent-finish
```

`agent-finish` 自行完成：按需同步一次、执行本地项目测试命令、
过 review-ready；只有 `REVIEW_READY=true` 才能送审，
同时输出 `BASE_SHA` / `HEAD_SHA` / `DEVELOP_SHA`。

本地测试通过不等于远端 CI 通过：有必需远端 CI 门禁的项目，
仍须按项目 CI 流程验证，不得以 `LOCAL_TESTS=passed` 关闭 CI 门禁。

`finish` 不做自动初始化：可见性未知时拒绝并指回 `agent-start`。

## 同步冻结（送审期间防漂移）

把 SHA 发给外部审查的同时必须执行：

```bash
./scripts/branchctl freeze
```

评审关闭后再执行：

```bash
./scripts/branchctl unfreeze
```

冻结期间一切自动同步都被拒绝（private 也不例外），只读检查不受影响。

## 多人协作转换

用户明确要求多个 Agent / 开发者共用当前 feature 时，Agent 执行：

```bash
./scripts/branchctl share
```

此后该分支禁止 rebase、禁止 force push，一律用 merge 同步。
`share` 永不自动触发。

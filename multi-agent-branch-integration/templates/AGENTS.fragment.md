本仓库使用 multi-agent-branch-integration 管理多 Agent 分支协作。

任何 Agent 修改项目产物前必须运行：

```bash
./scripts/branchctl preflight
```

如果未返回允许继续的结果（`PREFLIGHT=true`），不得修改项目产物。

分支同步必须使用：

```bash
./scripts/branchctl sync
```

不得自行选择 rebase / merge，具体方法由分支可见性决定
（private 用 rebase，shared 用 merge）。

进入评审前：

```bash
./scripts/branchctl review-ready
```

进入门禁前：

```bash
./scripts/branchctl gate-ready
```

最终集成前：

```bash
./scripts/branchctl merge-ready
```

详细策略见 `.agent/branch-policy.yaml`（项目配置）与 Skill 的
`references/policy-guide.md`（规则详解）。状态查询只读：

```bash
./scripts/branchctl status
```

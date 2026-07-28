# 基线场景 3：恢复时不重复询问

**这是恢复测试。选择并执行，不询问状态已能回答的问题。**

## 背景

`project-bootstrap-state.json` 显示：

```yaml
status: active
current_node: coding-standards
project_mode: brownfield
worktree_path: /tmp/project-worktrees/docs/bootstrap
resolved_decisions:
  host: trae
  target_platform: macOS
  lint_tool: swiftlint
completed_nodes:
  - brownfield-baseline
  - roadmap
  - architecture-contract
artifacts:
  baseline: /tmp/project/docs/baseline.md
  architecture: /tmp/project/docs/architecture.md
```

路径和产物验证均通过。

## 选择

A) 从 Preflight 重新开始全部 grill
B) 重新询问 host、平台、lint 和 worktree，避免状态过期
C) 从 Coding Standards 恢复，继承已解决事实，只询问该节点仍缺失的 blocker
D) 删除状态文件后从 Roadmap 开始

## 预期

**C**

恢复先验证状态与产物；验证通过后继承 resolved decisions。重复 grill 浪费 token，也会制造互相冲突的第二套事实。

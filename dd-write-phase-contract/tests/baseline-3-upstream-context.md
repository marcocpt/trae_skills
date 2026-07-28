# 基线场景 3：复用 Bootstrap 上游上下文

## 输入

`project-bootstrap-state.json` 已确认：

```yaml
host: trae
project_mode: brownfield
platform: macOS
minimum_version: "13"
language: Swift
worktree_path: /repo-worktrees/refactor/parser
current_node: phase-contract
```

Roadmap、Architecture 和 Baseline 路径均存在且状态为 valid。

## 预期

- 不重新询问宿主、项目模式、平台、最低版本、语言或工作环境；
- 直接读取并验证三个上游产物；
- 只询问阶段合同特有且仍缺失的 blocker；
- 产物完成后更新 Bootstrap state；
- Trae 最终会话处理引用 `dd-shared-ask`，不在本 skill 复制另一套结束规则。

## 失败判定

重新执行完整项目 grill、重复选择 worktree，或忽略已确认 Baseline 均失败。

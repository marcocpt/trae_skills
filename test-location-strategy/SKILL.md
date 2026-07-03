---
name: test-location-strategy
description: 在需要运行测试或 lint 时使用，决定在自建服务器（GitHub Actions self-hosted runner）还是本地执行。项目有自建 CI 时触发。
---

# CI 任务位置策略

对于所有需要运行测试或 lint 的位置，按以下优先级选择位置，避免无谓的本地重复执行。

## 前置：检测项目 CI 配置

```bash
# 自动检测 .github/workflows/ 下的 workflow 文件
ls .github/workflows/*.yml 2>/dev/null
```

- 无 yml 文件 → 直接本地测试（跳到第 3 步）
- 有 yml 文件 → 记录文件名，继续第 1 步

> 项目 `project_memory.md` 中若记录了 CI 配置段（workflow 文件名、runner 标签），优先使用记录的值，避免重复检测。

## 决策流程

对每个需要的测试类型（XCTest / XCUITest / lint），独立走以下流程：

### 1. 检查自建服务器是否已有可用结果

```bash
gh run list --workflow "<workflow-name>" --branch <当前分支> --limit 1
```

- 若最近一次运行 `conclusion == "success"` 且对应 commit 等于当前 HEAD → **跳过测试，复用 CI 结果**
- 若运行中（`status == "in_progress"`）→ 等待结果，不重复触发

### 2. 尝试自建服务器测试

```bash
gh workflow run "<workflow-name>" --ref <当前分支>
```

- 等待运行完成（`gh run watch <run-id>` 或轮询 `gh run view <run-id> --json status,conclusion`）
- 成功 → 使用 CI 结果，跳过本地测试
- 失败但属于 CI 环境限制（如 XCUITest GUI 权限、钥匙串弹窗）→ 读取 CI 日志区分环境失败与真实代码失败，仅对真实失败部分本地复现

### 3. 本地测试（无自建服务器或 CI 不可用）

仅当以下任一成立时执行：
- 项目无 `.github/workflows/` 自建服务器配置
- `gh` 命令不可用或鉴权失败
- 用户明确要求本地测试

运行项目对应的测试命令（如 `xcodebuild test`、`swift test`、`npm test`、`cargo test`、`pytest`、`go test`）。

## 多工作流项目处理

项目可能配置多个 CI 工作流，按测试类型分别调度：

### XCTest（单元测试 / 集成测试）

- 工作流：`macos-ci.yml`（自动触发：push / PR / workflow_dispatch）
- 触发方式：`gh workflow run "macos-ci.yml" --ref <当前分支>`
- 覆盖范围：SwiftLint + MacimApp scheme（跳过 MacimXCUITests）

### XCUITest（UI 端到端测试）

- 工作流：`macos-xcuitest.yml`（仅 workflow_dispatch 手动触发）
- 触发方式：`gh workflow run "macos-xcuitest.yml" --ref <当前分支>`
- 覆盖范围：MacimXCUITests（需要已登录 GUI 会话 + Accessibility 权限）
- **何时触发**：涉及 UI 行为变更时（如新增/修改 UI 交互、覆盖层行为、快捷键响应等），必须在步骤 6/8（Lint 与 Push）之前触发 XCUITest 工作流并等待结果
- **未涉及 UI 变更时**：跳过 XCUITest 工作流，仅运行 XCTest 工作流

### 执行策略

1. **XCTest + lint**：按上述决策流程 1→2→3 执行（始终需要）
2. **XCUITest**：仅在涉及 UI 变更时，按决策流程 1→2→3 执行（使用 `macos-xcuitest.yml`）
3. 两者可并行触发和等待

## 约束

- **不跳过失败验证**：CI 失败时不得直接声明通过，必须分析日志或本地复现
- **不重复触发**：已有运行中的 workflow 不得再次 `gh workflow run`
- **记录决策**：选择跳过/复用 CI 结果时，在步骤输出中说明依据（commit SHA、run ID、conclusion）

## 何时使用

**以下情况使用：**
- 任何需要运行测试套件的场景（基线验证、TDD 绿灯验证、回归测试、push 前测试验证）
- 任何需要运行 lint / typecheck 的场景（SwiftLint、ESLint、Pylint 等）
- 项目配置了 GitHub Actions self-hosted runner

**不适用：**
- 单个测试文件的快速验证（本地直接运行更快）
- 未纳入 CI 流程的本地专用检查工具

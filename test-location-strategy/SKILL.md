---
name: test-location-strategy
description: 在需要运行测试时使用，决定测试在自建服务器（GitHub Actions self-hosted runner）还是本地执行。项目有自建 CI 时触发。
---

# 测试位置策略

对于所有需要运行测试的位置，按以下优先级选择测试位置，避免无谓的本地重复执行。

## 前置：检测项目 CI 配置

```bash
# 自动检测 .github/workflows/ 下的 workflow 文件
ls .github/workflows/*.yml 2>/dev/null
```

- 无 yml 文件 → 直接本地测试（跳到第 3 步）
- 有 yml 文件 → 记录文件名，继续第 1 步

> 项目 `project_memory.md` 中若记录了 CI 配置段（workflow 文件名、runner 标签），优先使用记录的值，避免重复检测。

## 决策流程

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

## 约束

- **不跳过失败验证**：CI 失败时不得直接声明通过，必须分析日志或本地复现
- **不重复触发**：已有运行中的 workflow 不得再次 `gh workflow run`
- **记录决策**：选择跳过/复用 CI 结果时，在步骤输出中说明依据（commit SHA、run ID、conclusion）

## 何时使用

**以下情况使用：**
- 任何需要运行测试套件的场景（基线验证、TDD 绿灯验证、回归测试、push 前测试验证）
- 项目配置了 GitHub Actions self-hosted runner

**不适用：**
- lint / typecheck（始终本地执行）
- 单个测试文件的快速验证（本地直接运行更快）

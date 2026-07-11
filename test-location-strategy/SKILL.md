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

复用判定的核心是 **commit 一致**，`--branch` 仅为检索手段。按以下顺序检索：

```bash
# 先查当前分支
gh run list --workflow "<workflow-name>" --branch <当前分支> --limit 1
# 当前分支无远端或无结果时，查基线分支（如 main/develop）
gh run list --workflow "<workflow-name>" --branch <BASE_BRANCH> --limit 1
```

- 任一查询返回 `conclusion == "success"` 且 `headSha` 等于当前工作树 HEAD → **跳过测试，复用 CI 结果**（记录复用来源分支与 run ID）
- 若运行中（`status == "in_progress"`）→ 等待结果，不重复触发

> **基线验证场景**：在 bug-fix-workflow/feature-development-workflow 步骤 1.2.5 中，新创建的 fix 分支尚未 push，远端无此分支——此时**必须**查 BASE_BRANCH 的 CI 结果，因为工作树 HEAD 等于 BASE_BRANCH HEAD，基线 commit 已有成功 CI 证据即满足复用条件。

### 2. 尝试自建服务器测试

```bash
gh workflow run "<workflow-name>" --ref <当前分支>
```

- 等待运行完成（`gh run watch <run-id>` 或轮询 `gh run view <run-id> --json status,conclusion`）
- 成功 → 使用 CI 结果，跳过本地测试
- 失败但属于 CI 环境限制（如 XCUITest GUI 权限、钥匙串弹窗）→ 读取 CI 日志区分环境失败与真实代码失败，仅对真实失败部分本地复现
- **触发本身失败**（`gh workflow run` 报错，如 ref 不存在、权限不足、鉴权失败）→ **不得降级本地测试**。按以下优先级处理：
  1. ref 不存在（分支未 push）→ 用 AskUserQuestion 询问：先 push 分支再触发 CI / 复用 BASE_BRANCH 已有结果（若 commit 一致）/ 终止
  2. 鉴权失败 → 用 AskUserQuestion 询问：运行 `gh auth login` 修复鉴权 / 终止
  3. 其他错误 → 用 AskUserQuestion 询问：重试 / 排查 CI 配置 / 终止
- **禁止**：把"触发本身失败"等同于"CI 不可用"降级本地——触发失败是步骤 2 的分支，不是步骤 3 的入口

### 3. 本地测试（无自建服务器或 CI 不可用）

仅当以下任一成立时执行（封闭列表，不得扩展）：
- 项目无 `.github/workflows/` 自建服务器配置
- `gh` 命令不可用且用户在 AskUserQuestion 中选择不修复鉴权
- **已有 CI 结果不可复用**（commit 不一致）且 CI 触发失败且用户在 AskUserQuestion 中明确选择本地

运行项目对应的测试命令（如 `xcodebuild test`、`swift test`、`npm test`、`cargo test`、`pytest`、`go test`）。

> **"用户明确要求"不凌驾于 CI 优先之上**：当步骤 1 已有可复用的成功 CI 结果时，用户要求本地不构成降级理由。此时应用 AskUserQuestion 给出"复用 CI 结果（推荐）/ 仍要本地仅作参考 / 终止"选项。
>
> **"CI 不可用"的严格定义**：仅指上述封闭列表三种情形。分支未 push、`gh workflow run` 报错、CI 触发失败**均不构成"CI 不可用"**——这些是步骤 2 的"触发本身失败"，按步骤 2 的 AskUserQuestion 流程处理。

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
- **不降级本地**：CI 触发失败不构成走本地测试的理由；分支未 push 时必须先查 BASE_BRANCH 的 CI 结果或先 push 再触发，不得降级本地
- **委托关系优先级**：当工作流技能（如 bug-fix-workflow 1.2.5）委托本 skill 决策测试位置时，本 skill 的决策流程语义（commit 一致为核心）优先于工作流技能中的命令示例字面文本；两份文档措辞不一致时，以本 skill 的"CI 优先 + 不降级本地"红线为准

## 何时使用

**以下情况使用：**
- 任何需要运行测试套件的场景（基线验证、TDD 绿灯验证、回归测试、push 前测试验证）
- 任何需要运行 lint / typecheck 的场景（SwiftLint、ESLint、Pylint 等）
- 项目配置了 GitHub Actions self-hosted runner

**不适用：**
- 单个测试文件的快速验证（本地直接运行更快）
- 未纳入 CI 流程的本地专用检查工具

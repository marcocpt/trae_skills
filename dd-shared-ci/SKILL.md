---
name: dd-shared-ci
description: 当需要 CI 验证（基线 CI 复用、回归 CI 触发、push 后等待、合并后验证）时使用（被 dd-bug-fix-workflow、dd-feature-development-workflow 引用）。触发词：CI 验证、gh run、push 后等待、合并后 CI、test-macos.sh。
---

# dd 共享 CI 验证规则

## 概述

dd-bug-fix-workflow 和 dd-feature-development-workflow 共享的 CI 验证逻辑。**核心原则：CI 优先，禁止本地测试作为 CI 替代。** 本地环境差异（签名、SDK、runner 配置）会掩盖问题，CI 是工作流核心价值。

## 何时使用

| 场景 | bug-fix 步骤 | feature-dev 步骤 | 语义 |
|------|--------------|------------------|------|
| 基线 CI 验证 | 1.2.5 / 1.3 | 1.2.5 / 1.3 | 确认起点 commit 干净 |
| 回归 CI 验证 | 3.3.5 | 4.5b / 5.5 | Smoke CI（4.5b 高风险 phase）或最终完整 CI（5.5） |
| Push 后等待 CI | 6.2.1 | 8.2.1 | Lint+Push 后等待 CI 结果 |
| 合并后 CI 验证 | 7.1 | 5.5-5.6 | 候选分支 CI 通过后推进到 develop |

## 场景 1：基线 CI 验证

**语义**：确认起点 commit 干净。起点 = BASE_BRANCH 的 HEAD（新创建分支尚未 push，远端无此分支，此时**必须**查 BASE_BRANCH 的 CI 结果——工作树 HEAD 等于 BASE_BRANCH HEAD，基线 commit 已有成功 CI 证据即满足复用条件）。

按优先级检索（commit 一致即可复用）：

1. 先查当前分支：`gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1`
2. 当前分支无远端或无结果时，**必须**再查 BASE_BRANCH：`gh run list --workflow macos-ci.yml --branch <BASE_BRANCH> --limit 1`
3. 任一返回 `conclusion=success` 且 `headSha` 等于当前工作树 HEAD → 复用 CI 结果（记录复用来源分支与 run ID），跳过本地测试
4. `status=in_progress` → 等待 CI 完成，不重复触发

**触发 CI**（无可用结果且当前分支已 push 时）：

```bash
gh workflow run macos-ci.yml --ref <当前分支>
gh run watch <run-id> --exit-status
```

- **当前分支未 push 时不得以此为由降级本地**——先查 BASE_BRANCH 已有结果，或用 AskUserQuestion 询问是否 push 后触发 CI
- `gh workflow run` 本身报错（ref 不存在、鉴权失败等）→ 按 test-location-strategy 步骤 2 的 AskUserQuestion 流程处理，**不得降级本地**

## 场景 2：回归 CI 验证（提交后必须 push + 触发 CI）

**语义**：步骤 4.5/3.3.5 提交后全量回归 + XCUITest 验证。代码已提交，必须 push 到远端触发 CI 验证。**禁止在本地执行测试作为 CI 的替代。**

按顺序执行（不得跳步、不得本地测试兜底）：

### 2.1 检查分支是否已 push

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" >/dev/null 2>&1
```

- **退出码 0**（远端已有此分支）→ 进入 2.2
- **退出码非 0**（远端无此分支，新建分支未 push）→ **必须先 push**：
  ```bash
  git push -u origin "$CURRENT_BRANCH"
  ```
  - push 成功 → 进入 2.2
  - push 失败 → **AskUserQuestion**：
    - 选项 1（推荐）：重试 push（排查网络/权限问题）
    - 选项 2：停止工作流，排查 push 权限
  - **禁止**：以 push 失败为由落到本地测试

### 2.2 检查 CI 已有结果

```bash
gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1
```

- `conclusion=success` 且 `headSha` 等于当前 HEAD → 复用 CI 结果，进入下一步
- `status=in_progress` → 等待 CI 完成，不重复触发

### 2.3 触发 CI 并等待结果

```bash
gh workflow run macos-ci.yml --ref <当前分支>
sleep 5
RUN_ID=$(gh run list --workflow macos-ci.yml --branch <当前分支> --limit 5 \
  --json databaseId,headSha \
  --jq ".[] | select(.headSha == \"$(git rev-parse HEAD)\") | .databaseId" | head -1)
gh run watch "$RUN_ID" --exit-status
```

- **触发失败** → **AskUserQuestion**：
  - 选项 1（推荐）：重试触发 CI
  - 选项 2：停止工作流，排查 CI 配置
- **禁止**：以 CI 触发失败为由落到本地测试

### 2.4 CI 失败处理

- **CI 通过** → 进入下一步
- **CI 失败**（测试用例未通过）→ **AskUserQuestion**：
  - 选项 1（推荐）：拉取 CI 日志（`gh run view <run-id> --log-failed`）分析失败原因，回到 TDD 步骤修复
  - 选项 2：本地复现排查（`bash scripts/ci/test-macos.sh`，**仅用于理解失败原因，修复后必须重新走 CI 验证**）
  - 选项 3：跳过继续（不推荐）

## 场景 3：Push 后等待 CI

**语义**：Lint 与 Push 步骤完成后必须等待 CI 运行完成，不得直接结束工作流或宣称完成。

```bash
# 等 GitHub 注册新 push
sleep 5

# 查找当前 SHA 对应的最新 run
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_SHA=$(git rev-parse HEAD)

RUN_ID=$(gh run list \
  --workflow "macos-ci.yml" \
  --branch "$CURRENT_BRANCH" \
  --limit 5 \
  --json databaseId,headSha \
  --jq ".[] | select(.headSha == \"${CURRENT_SHA}\") | .databaseId" \
  | head -1)

if [ -n "$RUN_ID" ]; then
  echo "Watching run ${RUN_ID}..."
  gh run watch "$RUN_ID" --exit-status
else
  echo "⚠️ 未找到对应 SHA 的 run，可能 CI 未触发或 workflow 文件不存在"
fi
```

- **成功** → 进入下一步
- **CI 失败** → **AskUserQuestion**：
  - 选项 1（推荐）：拉取 CI 日志（`gh run view <run-id> --log-failed`）分析失败原因，回到 TDD 步骤修复
  - 选项 2：本地复现排查（`bash scripts/ci/test-macos.sh`，**仅用于理解失败原因，修复后必须重新走 CI 验证**）
  - 选项 3：跳过继续（不推荐，会引入未验证代码到远端）
- **未找到 run** → **AskUserQuestion**：
  - 选项 1（推荐）：手动触发 `gh workflow run macos-ci.yml --ref <当前分支>` 后重新等待
  - 选项 2：检查 workflow 文件是否存在 / `.github/workflows/macos-ci.yml` 配置是否正确
  - 选项 3：跳过继续（不推荐，会引入未验证代码到远端）

## 场景 4：合并后 CI 验证

**语义**：合并产生新的 commit，必须验证合并后代码在 CI 中通过。按 `test-location-strategy` skill 决策测试位置。

1. **本地快速冒烟**（可选，快速检测合并冲突遗留）：仅编译检查（如 `swift build --package-path MacimCore`），**不替代全量测试**
2. **CI 全量验证**（**必需**）：
   - **已 push**：`gh run list --workflow macos-ci.yml --branch "$BASE_BRANCH" --limit 1` 查找对应 SHA 的 run，`gh run watch` 等待结果
   - **未 push**：先 `git push`，再等待 CI 结果（与场景 3 相同流程）
3. **本地全量测试**（**仅当** CI 不可用或用户明确要求）：`bash scripts/ci/test-macos.sh`

- **CI 通过** → 继续清理工作树
- **CI 失败** → **AskUserQuestion**：
  - 选项 1（推荐）：拉取 CI 日志分析，回到 TDD 步骤修复
  - 选项 2：`git merge --abort` 撤销合并，回到 TDD 步骤
  - 选项 3：本地复现排查

> **红线**：合并后不得跳过 CI 验证直接清理工作树。合并可能引入基线变更冲突，CI 是唯一的跨环境验证。

## 本地测试脚本

`bash scripts/ci/test-macos.sh`（与 CI 同脚本，基于 xcodebuild test + Macim.xcworkspace + MacimApp scheme）。**禁止用 `swift test` 替代**——本项目是 Xcode 工程，`swift test` 只覆盖 SwiftPM 子集。

仅在以下封闭列表条件满足时使用本地测试：

- 项目无 `.github/workflows/` 配置
- `gh` 命令不可用且用户选择不修复
- 无可用 CI 结果且 CI 触发失败且用户明确选择本地

## 红线（适用于所有 CI 验证场景）

**绝不：**

- 跳过基线测试验证
- 不询问就带着失败的测试继续
- **以"当前分支未 push 导致 CI 触发失败"为由降级本地测试**——必须先查 BASE_BRANCH 的 CI 结果（基线 commit 与 BASE_BRANCH HEAD 相同）；若 BASE_BRANCH 也无结果，用 AskUserQuestion 询问是否 push 后触发 CI，不得直接降级本地
- **以"CI 不可用"宽泛措辞降级本地**——"CI 不可用"仅指：项目无 `.github/workflows/` 配置、`gh` 命令不可用且用户选择不修复、用户在**无可用 CI 结果**时明确选择本地。分支未 push、`gh workflow run` 报错、CI 触发失败**均不构成"CI 不可用"**
- **以"用户明确要求"凌驾于 CI 优先之上**——当已有可复用的成功 CI 结果时，用户要求本地不构成降级理由；应用 AskUserQuestion 给出"复用 CI 结果（推荐）/ 仍要本地仅作参考 / 终止"选项
  - **触发时机**：若 agent 已确定复用（commit 一致 + conclusion=success），可直接复用并告知用户，无需 AskUserQuestion；AskUserQuestion 仅在 agent 考虑接受用户本地请求时强制触发（即 agent 在"复用 CI"与"本地执行"之间犹豫时，必须用 AskUserQuestion 让用户显式选择，不得沉默降级本地）

## 基线验证 vs 回归验证的表面张力说明

- **基线验证**（场景 1）：可复用 BASE_BRANCH 的 CI 结果——起点 commit 已有 CI 证据，无需新运行
- **回归验证**（场景 2）：分支未 push 时必须先 push——提交后的新 commit 需新 CI 运行

两者场景不同，不得混淆。"分支未 push 时必须先 push 再等待 CI，禁止落到本地测试"和"CI 触发失败不构成走本地测试的理由"同样适用于基线验证——基线验证与回归验证在"CI 优先"上标准一致。

## 合理化借口表

| 借口 | 现实 |
|------|------|
| "TDD 循环中代码未提交，无法触发 CI" | XCTest 单测试文件可本地验证（快速反馈）。XCUITest 必须延迟到回归 CI 验证（场景 2）。未提交 ≠ 可以本地跑 UI 测试。 |
| "UI 测试本地跑更快，TDD 需要快速反馈" | XCUITest 对环境高度敏感（GUI 会话、Accessibility 权限、窗口焦点、TCC 弹窗），本地通过不能替代 CI。XCUITest 必须延迟到回归 CI 验证。XCTest 可本地快速反馈。 |
| "本地跑全量测试更快" | 全量回归（XCTest 全量 + XCUITest）统一在回归 CI 验证（场景 2）走 CI。单测试文件 XCTest 可本地快速反馈，但全量回归必须 CI。 |
| "用户选了本地合并所以跳过 CI" | 合并方式（本地 merge vs PR）不影响验证质量。合并产生新 commit，必须验证。场景 4 明确要求合并后走 CI。 |
| "只是小 bug/特性，全量 CI 没必要" | 小 bug 的回归风险不一定小。CI 正是捕获意外回归。 |
| "CI 太慢，影响效率" | XCTest 单测试文件本地验证提供快速反馈。回归 CI 等待（XCUITest + 全量回归）可与文档编写/下一个子计划准备并行，不阻塞。 |
| "本地测试通过了，CI 肯定也通过" | 本地环境 ≠ CI 环境。签名配置、SDK 版本、runner 权限差异都可能掩盖问题。 |
| "分支未 push，CI 触发不了，只能本地测" | 分支未 push 时必须先 `git push`，再等待远程 CI 结果。push 是 CI 验证的前置条件，不是跳过 CI 的理由。场景 2 已明确要求先 push。 |
| "gh workflow run 失败了，CI 不可用" | CI 触发失败应排查配置或重试，而非降级到本地测试。本地测试不能替代 CI 的跨环境验证。 |
| "先本地验证逻辑，等权限好了再补 CI" | 本地测试无论包装成"预验证""逻辑检查"还是"先跑通再说"，都不能作为回归 CI 验证的通过条件。必须等 push + CI 完成才能进入下一步。 |
| "远端仓库故障（500/维护），CI 物理上跑不了" | 远端不可用时停止工作流并等待恢复，不得降级本地测试。基础设施故障不改变验证标准。 |

## 被其他 skill 引用方式

各 dd 工作流技能在涉及 CI 验证的步骤中引用本技能，替换重复的 CI 验证逻辑。引用格式：`CI 验证遵循 [dd-shared-ci](../dd-shared-ci/SKILL.md) 场景 <N>`

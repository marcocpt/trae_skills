> 迁移来源：`dd-shared-ci/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。
>
> 唯一职责：exact-SHA 的 CI run discovery / trigger / wait / result 语义。测试位置决策由 [test-location.md](test-location.md) 拥有；Xcode 本地诊断 adapter 由 [ci-xcode.md](ci-xcode.md) 拥有。

# dd 共享 CI 验证规则

dd-bug-fix-workflow 和 dd-feature-development-workflow（以及 dd-ai-refactor-workflow）共享的 CI 验证逻辑。**核心原则：CI 优先，禁止本地测试作为 CI 替代。** 本地环境差异（签名、SDK、runner 配置）会掩盖问题，CI 是工作流核心价值。

本技能固定为 `invocation_mode=helper`：只把 CI 状态、SHA、run、证据和 blocker 返回调用方，不自行输出最终摘要或 Host Close。

## 何时使用

各工作流在需要验证精确 SHA 的 CI 结果时引用本 reference。使用共享 CI 时按「场景」取语义，但**不携带任何项目特定步骤号**；各工作流的 Stage 只引用场景语义，不复制命令。

## 前置：工作流选择器（所有场景共用）

进入任一场景前必须解析 `<workflow-name>`：

1. 优先项目 `AGENTS.md` / `project_memory.md` 记录的 workflow 文件名（单一属主：项目文档）；
2. 无记录时自动检测 `.github/workflows/*.yml`；
3. 无法唯一解析（多个 yml 且项目未记录）时 ASK / BLOCKED，不得猜名。

解析结果作为 `workflow_selector` 传入本 reference，场景 1-4 全部复用同一解析值。本 reference 不重复 test-location.md 的 CI 配置检测。

## 场景 1：基线 CI 验证

**语义**：确认起点 commit 干净。起点 = BASE_BRANCH 的 HEAD（新创建分支尚未 push，远端无此分支，此时**必须**查 BASE_BRANCH 的 CI 结果——工作树 HEAD 等于 BASE_BRANCH HEAD，基线 commit 已有成功 CI 证据即满足复用条件）。

按优先级检索（commit 一致即可复用）。`<workflow-name>` 来自上方"前置：工作流选择器"的 `workflow_selector`，本场景不再重复解析：

1. 先查当前分支：`gh run list --workflow <workflow-name> --branch <当前分支> --limit 1`
2. 当前分支无远端或无结果时，**必须**再查 BASE_BRANCH：`gh run list --workflow <workflow-name> --branch <BASE_BRANCH> --limit 1`
3. 任一返回 `conclusion=success` 且 `headSha` 等于当前工作树 HEAD → 复用 CI 结果（记录复用来源分支与 run ID），跳过本地测试
4. `status=in_progress` → 等待 CI 完成，不重复触发

**触发 CI**（无可用结果且当前分支已 push 时）：

```bash
gh workflow run <workflow-name> --ref <当前分支>
gh run watch <run-id> --exit-status
```

- **当前分支未 push 时不得以此为由降级本地**——先查 BASE_BRANCH 已有结果，或用结构化 ASK 询问是否 push 后触发 CI
- 需要 push 才能触发时，先检查 action-specific `delivery_authorization`；未授权即返回 blocker，不得擅自 push
- `gh workflow run` 本身报错（ref 不存在、鉴权失败等）→ 按 [test-location.md](test-location.md) 的结构化 ASK 流程处理，**不得降级本地**

## 场景 2：回归 CI 验证（提交后 push + 触发 CI）

**语义**：代码已提交，必须 push 到远端触发 CI 验证。**禁止在本地执行测试作为 CI 的替代。**

按顺序执行（不得跳步、不得本地测试兜底）：

### 2.1 检查分支是否已 push

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" >/dev/null 2>&1
```

- **退出码 0**（远端已有此分支）→ 进入 2.2
- **退出码非 0**（远端无此分支，新建分支未 push）→ 先检查 `delivery_authorization`：
  - 已授权 push → `git push -u origin "$CURRENT_BRANCH"`；成功 → 2.2；失败 → 结构化 ASK（重试 / 停止排查 push 权限）
  - **未授权 push** → 停在 Delivery 边界，返回 blocker，不得 push
  - **禁止**：以 push 失败为由落到本地测试

### 2.2 检查 CI 已有结果

```bash
gh run list --workflow <workflow-name> --branch <当前分支> --limit 1
```

- `conclusion=success` 且 `headSha` 等于当前 HEAD → 复用 CI 结果，进入下一步
- `status=in_progress` → 等待 CI 完成，不重复触发

### 2.3 触发 CI 并等待结果

```bash
gh workflow run <workflow-name> --ref <当前分支>
RUN_ID=$(gh run list --workflow <workflow-name> --branch <当前分支> --limit 5 \
  --json databaseId,headSha \
  --jq ".[] | select(.headSha == \"$(git rev-parse HEAD)\") | .databaseId" | head -1)
gh run watch "$RUN_ID" --exit-status
```

- **触发失败** → **结构化 ASK**：重试触发 / 停止排查 CI 配置
- **禁止**：以 CI 触发失败为由落到本地测试

### 2.4 CI 失败处理

- **CI 通过** → 进入下一步
- **CI 失败**（测试用例未通过）→ **结构化 ASK**：
  - 拉取 CI 日志（`gh run view <run-id> --log-failed`）分析失败原因，回到 TDD 修复
  - 本地复现排查（仅用于理解失败原因，修复后必须重新走 CI 验证）
  - 跳过：**仅**作为风险豁免，且同时满足——同改动有基线 CI 证据（BASE_BRANCH 对应 HEAD `conclusion=success`）、用户明确授权、记录 baseline SHA/run、current SHA、失败分类；**禁止据此声明 CI Gate PASS**，Gate 保持 `CONDITIONAL`（未满足），后续依赖该 Gate 的步骤保持 `BLOCKED`。否则不得跳过。

## 场景 3：Push 后等待 CI

**语义**：Lint 与 Push 步骤完成后必须等待 CI 运行完成，不得直接结束工作流或宣称完成。

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_SHA=$(git rev-parse HEAD)

RUN_ID=$(gh run list \
  --workflow <workflow-name> \
  --branch "$CURRENT_BRANCH" \
  --limit 5 \
  --json databaseId,headSha \
  --jq ".[] | select(.headSha == \"${CURRENT_SHA}\") | .databaseId" \
  | head -1)

if [ -n "$RUN_ID" ]; then
  echo "Watching run ${RUN_ID}..."
  gh run watch "$RUN_ID" --exit-status
else
  echo "未找到对应 SHA 的 run，可能 CI 未触发或 workflow 文件不存在"
fi
```

- **成功** → 进入下一步
- **CI 失败** → **结构化 ASK**：拉取日志分析修复 / 本地复现定位 / 跳过（仅作为风险豁免：有基线 CI 证据 + 用户明确授权 + 记录 baseline/current SHA 与失败分类；Gate 保持 `CONDITIONAL`，禁止据此声明 PASS）
- **未找到 run** → **结构化 ASK**：手动触发后重新等待 / 检查 workflow 文件配置 / 跳过（仅作为风险豁免，规则同上）

## 场景 4：合并后 CI 验证

**语义**：合并产生新的 commit，必须验证合并后代码在 CI 中通过。按 [test-location.md](test-location.md) 决策测试位置。

1. **本地快速冒烟**（可选，快速检测合并冲突遗留）：仅编译检查，**不替代全量测试**
2. **CI 全量验证**（**必需**）：
   - **已 push**：`gh run list --workflow <workflow-name> --branch "$BASE_BRANCH" --limit 1` 查找对应 SHA 的 run，`gh run watch` 等待结果
   - **未 push**：先检查 `delivery_authorization`；授权后 push，再等待 CI 结果（与场景 3 相同流程）；未授权停在 Delivery 边界
3. **本地全量测试**：仅作补充诊断；**不存在必需远端 CI Gate 时**，才按 [test-location.md](test-location.md) 的 local-final-verification 规则作为最终验证。存在必需远端 CI Gate 时不得仅因"用户明确要求"降级（红线：用户要求不凌驾 CI 优先）

- **CI 通过** → 继续清理工作树
- **CI 失败** → **结构化 ASK**：拉取 CI 日志分析修复 / `git merge --abort` 撤销合并回到 TDD / 本地复现排查

> **红线**：合并后不得跳过 CI 验证直接清理工作树。合并可能引入基线变更冲突，CI 是唯一的跨环境验证。

## 本地诊断

本地命令（含 [ci-xcode.md](ci-xcode.md) 的 Xcode adapter）**只用于理解失败原因或收集诊断**，不证明修复成功，也不能关闭必需远端 CI Gate。

仅在 `remote_ci_required=false`（项目无 `.github/workflows/` 配置，真正不存在远端 CI 能力）时才可使用本地测试作为最终验证（见 [test-location.md](test-location.md) 步骤 3 的两个独立概念）。

**`remote_ci_required=true` 但 `ci_control_available=false`**（如 `gh` 不可用、鉴权失败、触发失败）**不进入此封闭列表**——此时 `BLOCKED` / ASK（修复鉴权、换工具、重试、终止），本地只作诊断，不能 final PASS。

**CI 触发失败（`gh workflow run` 报错、分支未 push、鉴权失败等）不进入此封闭列表**——一律按"触发本身失败"的 ASK 流程处理（修复/重试/终止），不允许据此降级本地测试作为最终验证。

## 红线（适用于所有 CI 验证场景）

**绝不：**

- 跳过基线测试验证；
- 不询问就带着失败的测试继续；
- **以"当前分支未 push 导致 CI 触发失败"为由降级本地测试**——必须先查 BASE_BRANCH 的 CI 结果；若 BASE_BRANCH 也无结果，用结构化 ASK 询问是否 push 后触发 CI，不得直接降级本地；
- **以"CI 不可用"宽泛措辞降级本地**——"CI 不可用"仅指：`remote_ci_required=false`（项目无 `.github/workflows/` 配置）。`gh` 不可用、分支未 push、`gh workflow run` 报错、CI 触发失败**均不构成"CI 不可用"**——`remote_ci_required=true` 时控制工具不可用只导致 `BLOCKED`/ASK，不允许据此降级本地测试作为最终验证；
- **以"用户明确要求"凌驾于 CI 优先之上**——当已有可复用的成功 CI 结果时，用户要求本地不构成降级理由；应用结构化 ASK 给出"复用 CI 结果（推荐）/ 仍要本地仅作参考 / 终止"选项；
- 未授权 push（缺 `delivery_authorization`）时仍 push 触发 CI；
- 用固定 workflow/scheme/项目名替代项目文档与脚本；
- 本地测试作为 CI 替代，或本地复现/诊断通过即宣称必需远端 CI Gate 已关闭。

## 合理化借口表

| 借口 | 现实 |
|------|------|
| "TDD 循环中代码未提交，无法触发 CI" | 单测试文件可本地验证（快速反馈）。环境敏感 UI 测试必须延迟到回归 CI 验证。未提交 ≠ 可以本地跑 UI 测试。 |
| "本地跑全量测试更快" | 全量回归统一在回归 CI 验证走 CI。单文件可本地快速反馈，但全量回归必须 CI。 |
| "用户选了本地合并所以跳过 CI" | 合并方式不影响验证质量。合并产生新 commit，必须验证。 |
| "只是小 bug/特性，全量 CI 没必要" | 小 bug 的回归风险不一定小。CI 正是捕获意外回归。 |
| "本地测试通过了，CI 肯定也通过" | 本地环境 ≠ CI 环境。签名配置、SDK 版本、runner 权限差异都可能掩盖问题。 |
| "分支未 push，CI 触发不了，只能本地测" | 分支未 push 时须先检查 `delivery_authorization`；授权后 push，再等待远程 CI 结果。push 是 CI 验证的前置条件，不是跳过 CI 的理由。 |
| "gh workflow run 失败了，CI 不可用" | CI 触发失败应排查配置或重试，而非降级到本地测试。 |
| "远端仓库故障（500/维护），CI 物理上跑不了" | 远端不可用时停止工作流并等待恢复，不得降级本地测试。基础设施故障不改变验证标准。 |

## 被其他 skill 引用方式

各 dd 工作流技能在涉及 CI 验证的步骤中引用本技能。引用格式：`CI 验证遵循 [dd-workflow-runtime/ci](../../dd-workflow-runtime/references/ci.md) 场景 <N>`。CI evidence 必须绑定精确 SHA：复用/通过/失败均记录 `headSha` 与 run ID；candidate/final 的 CI SHA 必须等于 review SHA 与候选 SHA。

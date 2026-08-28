# Feature Implementation

只在 Implementation Stage 读取。Phase Loop、TDD、Local Gate、UI Smoke 与 Phase risk review。

## 1. Phase Loop

一个 Phase 可含多个 Task；Phase 责任：把所有 Task 的 TDD 循环推进到 Local Gate 全过，才进入下一 Phase。每个 Phase：

1. 验证 package/manifest/source digests 与当前 worktree 一致；任一 stale 回 Planning 重新派生；
2. **选择性读取**：读取 Task anchors、所有声明为 global 的约束、Out of Scope 与失败路径；打开 `consumes` 与 integration anchors（AC-05）。不得每 Phase 完整重读全部原始规格；
3. 合同漂移处理：实现细节漂移且合同仍成立 → 在当前 scope 内适配；接口/架构/规格假设失效 → package stale，回 Planning；
4. 对每个 Task 按 TDD 循环执行（Red/Green/Refactor）；
5. 保存 compact verification（`plan + result`，含 coverage/runs/bindings/validity）与适用的 UI 证据；
6. 持久化当前 Phase 的 diff／文件指纹；只有 `delivery_authorization` 允许时才按逻辑提交；
7. 执行 Local Gate；
8. 原子更新状态；
9. 判断是否触发远程 UI Smoke；
10. 最后一个 Phase 且存在 `integration_plan_path`（复杂档）时执行 **Post-Phase Integration Gate**（见 §3.1）；
11. 进入下一 Phase（或 Documentation）。

Phase 结束时不得有未解释变更，并记录 diff／文件内容指纹；若交付策略要求 Commit，再记录完成 SHA。不要创建空提交，也不要把内容批准或计划中的 Commit 示例当成授权。

### 3.1 Post-Phase Integration Gate（复杂档）

`split_mode=per-phase-with-integration` 时，最后一个 Phase 完成后、进入 Documentation 前，读取 `integration_plan_path`（见 [planning.md](planning.md)「跨 Phase 集成计划」）并执行：

1. 打开 integration anchors（Phase 间契约、端到端 AC）；
2. 运行集成验收命令与证据位置（来自 integration plan）；
3. 保存 exact bindings：`integration_verification.bindings.implementation_digest`（或已有 commit 时 `integration_ci_run.head_sha == implementation_head_sha`）与证据；**此时候选尚未冻结，不得引用 `candidate_sha`**（那在 Final Candidate 阶段建立）；
4. 任一端到端 AC 未验证 → `BLOCKED`，回到对应 Phase 修复；
5. 通过后 `integration_gate_passed=true`，才进入 Documentation。

Final Candidate 阶段再建立独立的 `candidate_review.sha == full_spec_gap.sha == full_ci_run.head_sha == candidate_sha`。

### 动作授权与执行（`phase_delivery`，独立于 verification）

`verification` 只存 `plan + result`（见 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) §4），不在此增加第三块。动作授权与执行结果放同级 `phase_delivery`，authorization 与 execution 分离记录，不得缺省：

```yaml
phase_delivery:
  commit:
    authorization: authorized | not-required | not-authorized | pending
    execution: completed | not-required | not-authorized | pending
    evidence: <sha-or-commit-ref-or-null>
  push:
    authorization: authorized | not-required | not-authorized | pending
    execution: completed | not-required | not-authorized | pending
    evidence: <sha-or-push-ref-or-null>
  ci:
    authorization: authorized | not-required | not-authorized | pending
    execution: completed | not-required | not-authorized | pending
    evidence: <run-id-or-url-or-null>
```

`authorization` 取 `delivery_authorization` 值；`execution` 取实际执行结果。未提交/未运行/未授权的部分必须记 `not-required`、`not-authorized` 或 `pending`，不得留空或默认为"已执行"；后续 Gate 依赖被禁止动作时 `BLOCKED`。

## 2. TDD

### Red

- 从当前 AC 编写最小失败测试；
- **运行绑定**：Red 的结论是"当前代码失败"——必须在允许的位置实际运行并确认测试因正确原因失败；记录该 run 的阶段、outcome 与 implementation/diff digest，不能仅凭"测试已写好"声称红灯已确认；
- XCTest/普通单元测试可在本地确认因正确原因失败；
- 环境敏感 UI 测试按项目 CI 策略验证，不能在未执行时声称红灯已确认；
- 无法自动化时先定义可重复手动验证和证据。

### Green

- **运行绑定**：Green 的结论是"当前代码通过"——必须在允许的位置实际运行并确认测试通过，记录 run 的阶段、outcome 与实现/diff digest，再把实现标为绿；
- 只实现满足当前测试的最小行为；
- 不捆绑无关重构；
- 单元测试在允许的位置快速验证；
- UI 结果在对应 Smoke/完整 CI 或真实手动路径验证前标记为未验证。

### Refactor

在绿灯基础上消除重复、改善命名和边界，不新增行为。

失败少于三轮时带新证据回到根因/实现；连续三轮无效时 ASK 继续、回到 Planning/Specification 或停止。修改既有回归预期必须先证明需求确实改变并获得所需确认。

## 3. Local Gate

每个 Phase 实现后执行不依赖不稳定桌面状态的快速检查：

- lint / format；
- build / typecheck；
- 当前 Phase 相关单元测试；
- UI 测试 target 的编译或静态可执行性检查；
- AC → 测试/证据映射无缺口；
- 从已读 anchors/global constraints 重新提取当前 Phase 适用的 FR／NFR／AC、Out of Scope、失败路径和跨功能约束，形成来源定位 → 实现／测试／证据的 gap table；不得复用 Intake 摘要中的旧清单；
- gap table 与原始规格逐项一致，且实现与当前执行包、项目规则无遗漏或越界；
- 受影响回归、错误、边界与并发相关测试通过；
- 测试不绑定非契约内部实现，不使用会掩盖真实行为的过度 mock；
- 当前 Phase 范围（有 Commit 时用 SHA range，否则用冻结 diff／文件指纹）无新增临时日志、TODO 或未解释 skip；
- 项目规定的其他快速 Gate。

按 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) 写入 compact verification（`plan + result`）。计划、测试文件存在、`covered` 或旧 CI 不能替代当前运行；未运行、失败、bindings 不一致或 `validity != valid` 均不得 PASS。

Swift/Xcode 构建遵循 `dd-workflow-runtime/ci` 的项目/工作区检测和签名合同；不要在本文件硬编码证书或 scheme。

失败必须修复并重跑。通过后原子更新：

```yaml
current_stage: implementation
current_phase: 2
completed_phases:
  - 0
  - 1
  - 2
change_fingerprints:
  phase-2: <diff-or-file-digest>
commits:
  phase-2: <sha-or-not-required-or-not-authorized>
phase_delivery:
  phase-2:
    commit: {authorization, execution, evidence}
    push: {authorization, execution, evidence}
    ci: {authorization, execution, evidence}
verification_evidence:
  phase-2:
    runs:
      - phase: red
        outcome: FAIL
        digest: <implementation-or-diff-digest-at-red>
        evidence_ref: <repo-relative-evidence>
      - phase: green
        outcome: PASS
        digest: <implementation-or-diff-digest-at-green>
        evidence_ref: <repo-relative-evidence>
```

## 4. 紧凑 Phase review

Local Gate 先执行 lint/build/typecheck/定向测试/映射检查，再保存 A/B/C 三个结果引用，不写第二篇长 self-review（AC-06）。

命中 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 的风险触发器时，按现有 `review_level`／`model-routing` 升级独立强审；普通 Phase 独立强审调用次数为零。

## 5. Risk-based UI Smoke

下列任一情况默认 high risk：

- App/Scene 启动；
- 主窗口、设置窗口、Toolbar、菜单；
- Accessibility/TCC；
- 全局快捷键；
- XCUITest/Playwright 基础设施；
- 共享导航或窗口管理；
- 无法由单元测试或静态证据验证；
- 长周期或跨多个 UI 页面。

High risk：在 Delivery 授权允许 push 时推送当前工作分支，运行 5–10 个核心 UI Smoke，包括启动、入口、核心路径和退出。所需 push 未获授权时停在该 Delivery 边界，不得把 Smoke 记为已运行；失败时读取证据并回到 TDD。跳过只能由用户明确承担风险，并记录未满足 Gate。

普通风险不运行 Smoke，但仍保留 Local Gate 和最终完整 CI。

Smoke 通过后记录 Phase、run URL/ID、SHA 和结果；没有 SHA 关联的“CI 通过”无效。

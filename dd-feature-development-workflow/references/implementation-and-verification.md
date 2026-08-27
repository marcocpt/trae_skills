# Feature Implementation and Verification

只在 Implementation 或 Final Candidate Stage 读取。

## 目录

- [Phase Loop](#1-phase-loop)
- [TDD](#2-tdd)
- [Local Gate](#3-local-gate)
- [Risk-based UI Smoke](#4-risk-based-ui-smoke)
- [Final Candidate](#5-final-candidate)

## 1. Phase Loop

每个 Phase：

1. 读取当前 Phase 执行包（`phase_plan_paths` 中 `phase_id == current_phase` 的文件；简单档读取总计划），按 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) 核对全部来源指纹、批准依据和授权；
2. 从磁盘完整读取该包引用的批准原始规格；摘要只作导航。执行包 stale 或必需字段缺失时停止并回到 Planning 重新派生；
3. 按任务执行 TDD；
4. 保存四层验证证据和适用的 UI 证据；
5. 持久化当前 Phase 的 diff／文件指纹；只有 `delivery_authorization` 允许时才按逻辑提交；
6. 执行 Local Gate；
7. 原子更新状态；
8. 判断是否触发远程 UI Smoke；
9. 进入下一 Phase。

Phase 结束时不得有未解释变更，并记录 diff／文件内容指纹；若交付策略要求 Commit，再记录完成 SHA。不要创建空提交，也不要把内容批准或计划中的 Commit 示例当成授权。

## 2. TDD

### Red

- 从当前 AC 编写最小失败测试；
- XCTest/普通单元测试可在本地确认因正确原因失败；
- 环境敏感 UI 测试按项目 CI 策略验证，不能在未执行时声称红灯已确认；
- 无法自动化时先定义可重复手动验证和证据。

### Green

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
- 从批准原文重新提取当前 Phase 适用的 FR／NFR／AC、Out of Scope、失败路径和跨功能约束，形成来源定位 → 实现／测试／证据的 gap table；不得复用 Intake 摘要中的旧清单；
- gap table 与原始规格逐项一致，且实现与当前执行包、项目规则无遗漏或越界；
- 受影响回归、错误、边界与并发相关测试通过；
- 测试不绑定非契约内部实现，不使用会掩盖真实行为的过度 mock；
- 当前 Phase 范围（有 Commit 时用 SHA range，否则用冻结 diff／文件指纹）无新增临时日志、TODO 或未解释 skip；
- 项目规定的其他快速 Gate。

按 artifact-contract 分开写入 `verification_plan`、`existing_coverage`、`run_result`、`evidence_validity`。计划、测试文件存在、`COVERED` 或旧 CI 不能替代当前运行；未运行、失败或证据 stale 均不得 PASS。

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
verification_evidence:
  phase-2: <artifact-or-state-key>
```

## 4. Risk-based UI Smoke

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

## 5. Final Candidate

所有 Phase Gate 通过后：

1. 再次从磁盘完整读取全部批准原始规格和 review，重新提取全部 FR／NFR／AC、Out of Scope 与跨功能约束；把清单与各 Phase gap table、实现 diff、测试和证据逐项核对；
2. 任一来源指纹／批准依据变化、遗漏、越界或无归属实现都返回 Specification／Planning／Implementation，旧执行包和旧符合性结论失效；
3. 完成当前流程规定的最终日志／设计补充；
4. 确认工作分支状态可解释且四层 Phase 证据完整、有效；
5. 确认 Commit／merge／push 的 Delivery 授权；缺失时保留已通过的 Workflow Gate 并停在该 Delivery 边界；
6. 获取最新 develop；
7. 基于最新 develop 创建 `ci/<F编号>-final-candidate`；
8. merge-only 合入 Feature 分支；
9. 记录候选 SHA；
10. push 候选分支；
11. 对该 SHA 运行完整远程 CI；
12. CI 通过后以 fast-forward 或项目批准的等价方式推进同一 SHA；
13. develop 在 CI 期间变化时废弃候选并重新生成、重新验证。

完整 CI 至少覆盖 lint、build、全部单元/集成测试、全部 UI 测试和项目要求的证据检查。

失败循环：读取失败日志 → 工作分支定向修复 → 定向验证 → 重建候选 → 最终完整 CI。不得把旧候选的 CI 结果复用于新 SHA。

Gate：

```yaml
final_candidate_branch: ci/F0-final-candidate
final_candidate_sha: <sha>
final_ci_run: <run-id-or-url>
final_ci_passed: true
current_stage: confirmation
```

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

1. 读取当前 Phase 子计划（`phase_plan_paths` 中 `phase_id == current_phase` 的文件；简单档读取总计划）与规格；
2. 按任务执行 TDD；
3. 保存 UI/运行证据；
4. 按逻辑提交当前 Phase；
5. 执行 Local Gate；
6. 原子更新状态；
7. 判断是否触发远程 UI Smoke；
8. 进入下一 Phase。

多个任务可有多个小 commit；Phase 结束时工作区必须无未解释变更，并记录完成 SHA。不要创建空提交。

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

每个 Phase 提交后执行不依赖不稳定桌面状态的快速检查：

- lint / format；
- build / typecheck；
- 当前 Phase 相关单元测试；
- UI 测试 target 的编译或静态可执行性检查；
- AC → 测试/证据映射无缺口；
- 实现与规格、当前 Phase Plan 和项目规则一致；
- 受影响回归、错误、边界与并发相关测试通过；
- 测试不绑定非契约内部实现，不使用会掩盖真实行为的过度 mock；
- 当前 Phase 提交范围（已记录 SHA range 的 diff）无新增临时日志、TODO 或未解释 skip；
- 项目规定的其他快速 Gate。

Swift/Xcode 构建遵循 `dd-workflow-runtime/ci` 的项目/工作区检测和签名合同；不要在本文件硬编码证书或 scheme。

失败必须修复并重跑。通过后原子更新：

```yaml
current_stage: implementation
current_phase: 2
completed_phases:
  - 0
  - 1
  - 2
commits:
  phase-2: <sha>
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

High risk：push 当前工作分支，运行 5–10 个核心 UI Smoke，包括启动、入口、核心路径和退出。失败时读取证据并回到 TDD；跳过只能由用户明确承担风险，并记录未满足 Gate。

普通风险不运行 Smoke，但仍保留 Local Gate 和最终完整 CI。

Smoke 通过后记录 Phase、run URL/ID、SHA 和结果；没有 SHA 关联的“CI 通过”无效。

## 5. Final Candidate

所有 Phase Gate 通过后：

1. 完成当前流程规定的最终日志/设计补充；
2. 确认工作分支干净且 Phase 证据完整；
3. 获取最新 develop；
4. 基于最新 develop 创建 `ci/<F编号>-final-candidate`；
5. merge-only 合入 Feature 分支；
6. 记录候选 SHA；
7. push 候选分支；
8. 对该 SHA 运行完整远程 CI；
9. CI 通过后以 fast-forward 或项目批准的等价方式推进同一 SHA；
10. develop 在 CI 期间变化时废弃候选并重新生成、重新验证。

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

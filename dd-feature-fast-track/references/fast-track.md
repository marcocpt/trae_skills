# 新特性速通阶段（Intake / Fast Implementation / Smoke）

速通模式的通用语义（唯一询问点、不可省清单、欠账台账 schema、恢复）见 [fast-track-contract](../../dd-workflow-runtime/references/fast-track-contract.md)；本文件只写新特性领域的做法。

## 1. Intake

### 1.1 复述模板（一次询问，三段话）

用通俗语言复述，让用户能一句话确认或纠正：

1. **要解决什么**：这个功能现在缺什么、谁在什么场景下用；
2. **范围边界**：这次做什么、明确不做什么（把"顺手也做了"的部分点出来）；
3. **怎样算能用**：用户能亲手验证的一条主路径（点哪个按钮、跑哪条命令、看到什么）。

复述后**不再就实现细节提问**。未确认（null、取消、空输入）→ 按 [ask](../../dd-workflow-runtime/references/ask.md) 重问。

### 1.2 工作环境（不询问，按推荐执行）

默认按推荐项新建隔离 worktree，且在修改任何项目产物之前完成，遵循 `dd-git-workflow` 的 branch 与 worktree 规则。无法创建（非 Git 仓库、无可用基线等）时才使用当前工作区，并把原因写入状态 `reason`。

工作环境确定后立即持久化状态，写入 `fast_track=true`、`track_phase=fast-track`、`requirement_confirmed=true`。

**tracking 绑定（Intake Gate 前，速通工作流的绑定 Gate 就是 Intake）**：按 [task-tracking](../../dd-workflow-runtime/references/task-tracking.md) §3 执行一次绑定尝试，并把结果按该合同落盘。绑定语义、失败矩阵与重试策略完全由该合同定义；绑定失败**不阻塞本 Stage**，也不因此向用户发问（速通阶段唯一询问点仍是需求复述）。

Intake Gate：需求复述已获用户确认、工作环境已持久化、tracking 绑定结果已按 owner 合同落盘。

### 1.3 本阶段要预判的欠账

速通阶段不写规格，但要在进入实现前把这轮必然产生的欠账想清楚，免得冒烟后凭印象补：见 §3.3 的默认欠账清单。

## 2. Fast Implementation

### 2.1 执行方式

- 一口气实现到可运行：不拆 Phase、不按 Phase 设 Local Gate、不做阶段复核、不派独立审查；
- 需要选择时（库选型、接口形状、命名、目录位置、是否加配置项）直接选推荐项，把「选择 + 一句话理由」追加到 `decisions`；
- 保持单一改动意图：速通不夹带无关重构，发现需要顺手改的地方记入 LATER（`dd-later-tracking`），不在本次扩散；
- 仍然遵守项目规则（lint、格式化、命名、架构约束），"速通"不等于"随意"。

### 2.2 询问例外（只有这四种可以停）

按 fast-track-contract §3.2：不可逆或外部可见动作、缺授权且无推荐替代、需求自相矛盾或关键输入缺失、已确认需求本身不成立。除此之外一律继续。

授权边界单独处理：commit／push／merge／发布仍需动作级授权，缺失时记 `not-authorized` 并停在该动作边界，不阻塞速通产出。

### 2.3 需要停下来交接正式流程的信号

出现下列任一情况，停止速通实现，交接 `dd-feature-development-workflow`：

- 需要新增或更改公共 API 签名；
- 需要新增架构边界或跨模块依赖；
- 涉及持久化格式、并发模型、兼容性、迁移、安全或权限；
- 实现中发现已确认需求需要拆成 ≥ 2 个 Phase 才能验证。

交接时带上已确认需求、当前实现、已有证据、`decisions` 与欠账台账，按 [state-and-handoff](../dd-feature-development-workflow/references/state-and-handoff.md) 的 Handoff 字段写入。

## 3. Smoke

### 3.1 冒烟自证（必须真实跑通）

- 真实构建／启动，跑通复述时承诺的主路径；
- 有 UI 变化时按 [ui-evidence](../../dd-workflow-runtime/references/ui-evidence.md) 取真实路径证据，不接受内部状态、mock、日志或组件渲染代替；
- 补一条针对本次改动的最小验证（单测或脚本）并实际运行；它记入欠账 `test` 的初始证据，但不等于补齐阶段的测试矩阵。

### 3.2 交付可用产物

把「怎么立刻用起来」交给用户：启动命令或入口路径、需要的前置条件、主路径的操作步骤。用户此刻应该能亲手试。

### 3.3 默认欠账清单（逐条登记，不得漏项）

| kind | 速通阶段为什么不做 | 关闭所需证据 |
|---|---|---|
| `spec` | 没先写规格套件 | mini-spec 或完整规格套件已产出并绑定内容指纹（规模判定见 [backfill](backfill.md) §2） |
| `plan` | 没拆 Phase 与任务 | AC → Task → 测试/证据映射已补齐 |
| `test` | 只跑了最小验证 | 测试矩阵执行结果，覆盖全部 AC |
| `determinism` | 没做确定性验证 | 同一份实现重复执行结果一致的验证记录 |
| `ci` | 没跑完整 CI | 最终 SHA 上的完整 CI 运行记录 |
| `review` | 没做审查 | A/B/C 自检结论，或按 [review-gate](../../dd-workflow-runtime/references/review-gate.md) 升级的独立强审结论 |
| `docs` | 没同步长期文档 | 受影响的长期文档已同步，或明确"无需更新"的结论 |
| `ui-evidence` | 只在有 UI 变化时登记 | 真实路径证据与新鲜度绑定（无 UI 变化时本条不登记） |

台账写入状态后立即进入 Backfill，不等用户再次要求。

### 3.4 本阶段禁止的宣称

不得说"验收通过""已验证""可以交付"。交付的是**可用产物**，不是已验收的候选。

# Task Tracking 绑定尝试入口可达性 Design

- Feature: tracking-binding-reachability
- Workflow ID: feature-development-20261003T053419Z-ee41fa8
- Stage: Design（WHO／结构）
- 基线 Requirements: v1 (`cf02335951f58a5c`)
- 日期: 2026-10-03

## 1. 架构定位

本设计不新建子系统，只在三处既有编排层补齐"义务可发现"，并新增一个既有验证脚本家族的成员。

```text
入口层（首次读取面）
├── dd-feature-development-workflow/SKILL.md   ← 补 Environment Stage 义务 + 红线
├── dd-bug-fix-workflow/SKILL.md               ← 补 Environment Stage 义务 + 红线
└── dd-workflow-runtime/SKILL.md               ← 补 Preflight 义务 + 调用契约字段语义

状态表示层
└── dd-workflow-runtime/references/state.md    ← 通用字段表示补 tracking 预留位

判定层（既有 validate-* 家族新增成员）
└── dd-workflow-runtime/agents/validate-tracking-binding.py
```

**为什么这样切分**：入口层解决"义务不可见"，判定层解决"跳过无代价"。两者缺一则前次失效重演——只有判定层，Agent 不会运行它；只有入口层，Agent 可无视红线直接通过。

## 2. 模块责任

### 2.1 入口层

**负责**：让义务在首读面可见、让动作可识别、让判定成为 Gate 条件。

**不负责**：不定义绑定语义、不定义字段形状、不复述失败矩阵。

**依赖方向**：入口层单向引用 owner 合同（`task-tracking.md`）。owner 合同不反向引用入口层。

### 2.2 状态表示层

**负责**：让通用字段表示在结构上容纳绑定尝试结果。

**不负责**：不定义 `tracking` 的字段形状与枚举——那属于 owner 合同。此处只出现字段名与"详见属主"的指针。

**关键约束**：`state.md` 已有的 `通用字段（所有工作流必需）` 段落被合同测试断言不得出现 owner 合同的嵌套字段（见 `test_task_tracking.py::test_tracking_nested_schema_single_owner`）。因此本设计只加**字段名 + null 占位**，绝不注释其子字段。

### 2.3 判定层

**负责**：给定状态文件，判定"尝试已记录 / 未记录"；漂移检测。

**不负责**：不做远端对账、不创建 Issue、不写任何远端、不裁决绑定语义、不阻塞工作流。

## 3. 判定层设计

### 3.1 输入与输出

```text
输入: --state <path>        工作流状态 JSON 路径
输出: stdout 人类可读结论
      exit 0  尝试已记录（PASS）
      exit 1  尝试未记录（FAIL）
      exit 2  用法/输入错误
```

### 3.2 判定算法

按 `schema_version` 与 `tracking` 形态分派：

```text
读取 state，失败 → exit 2

若 workflow_type 不在 {feature-development, bug-fix} → PASS
    （owner 合同 §12 明确 bootstrap 不适用该强制约束）

若 schema_version 缺失或 < 2 且 tracking 缺失或为 null
    → PASS
    （本次改动之前的历史状态，FR-7；不得据其触发创建）

若 tracking 为对象：
    ├ provider 非 null 且不在已登记 provider 集 → FAIL   （§2 well-formedness 前置检查）
    ├ ① issue_number 非 null                          → PASS  已绑定
    ├ ② sync ∈ {synced, disabled}                     → PASS  §4 中这两行本就不带原因值
    ├ ③ sync ∈ {not-synced, not-authorized}
    │     且 sync_reason ∈ §4 词表                     → PASS  已记录原因
    └ ④ 其余                                            → FAIL  尝试未记录

否则（tracking 缺失或为 null，schema_version >= 2）
    → FAIL
```

**为什么是四条 PASS 分支而不是一条**：owner 合同 §4 的 11 行里，`绑定有效→synced` 与 `用户明确禁用→disabled` 两行的 `sync_reason` 列本就允许为空；其余 9 行都带具体原因。若要求"任何 PASS 都必须有原因值"，这两行会被误判成未尝试，等于用判定器把合同明确允许的状态拦死——直接违反 FR-6。反之若只认 `issue_number`，则 10 类失败/拒绝全被误判，同样违反 FR-6。

**不通过条件的唯一形态**：`schema_version >= 2`、`workflow_type` 属强制范围、`tracking` 不通过 ①~③ 中任一分支、且未触发 legacy 或 bootstrap 豁免。这精确对应 owner 合同 §2 的"未尝试且未记录就通过 Gate 属违规"，不宽不窄。

### 3.3 为什么不做远端对账

owner 合同 §3.1 的对账与创建需要网络与凭据。判定层若做对账，则：

- 违反 AC-10（离线可运行）；
- 在 provider 故障时无法给出稳定结论，反而把外部故障变成 Gate 阻塞，与 §4 冲突；
- 让判定层持有写能力，扩大远端副作用面。

因此判定层是**纯函数式的状态形状检查器**。远端正确性由 owner 合同的 `sync_reason` 词表与 Issue 内容承担，不在本层复核。

### 3.4 防第二事实源（FR-8）

判定层不可避免要引用 `sync` 四值与 `sync_reason` 词表。处理方式：

```text
判定层内置枚举常量（必须有确定行为，不能运行时解析 Markdown）
        +
合同测试逐项比对：内置枚举 == owner 合同 §2 表中的 sync 取值 ∪ §4 表中的 sync_reason 取值
        +
合同测试断言 owner 合同中不存在未被判定层覆盖的 sync_reason 取值（双向覆盖）
```

漂移方向都被捕获：判定层加了词表外的值 → 测试失败；owner 合同加了新原因 → 测试失败（双向断言）。

**不采用**运行时解析 `task-tracking.md` 提取枚举：那会让规范 Markdown 成为可执行依赖，规范一改行为就变，且解析器本身成为新的失败面。

## 4. 数据流

```text
Agent 读入口 SKILL.md
  → 得知 Environment Gate 前须完成绑定尝试（FR-1/FR-02）
  → 打开 owner 合同 §3/§3.1/§8.1 执行尝试（语义仍唯一属主）
  → 写 state.tracking
  → Environment Gate 前运行 validate-tracking-binding.py --state <path>
  → exit 0 才允许过 Gate（FR-10）
```

失败分支：

```text
尝试失败但已按 §4 记录 sync + sync_reason
  → 判定层 PASS
  → 工作流继续（§4：任何一行都不得阻塞 Workflow Gate）
```

## 5. 状态字段变更

`state.md` 通用字段表示新增一行：

```json
"tracking": null
```

与既有 `owner` 子对象并列，注释指向 owner 合同。不在 `state.md` 出现 `provider` / `issue_number` / `sync` / `sync_reason` 等子字段名。

**为什么 `state.md` 而不是调用契约 YAML**：`dd-workflow-runtime/SKILL.md` 的调用契约已有 `tracking: null`（该字段名已由 runtime-contract §3 声明为可选）。缺口在 `state.md` 的持久化模板——执行者照模板首次写状态时产出的 JSON 里根本没有 `tracking` 键。这是实际缺陷点。

## 6. 入口层改动清单

| 文件 | 位置 | 改动 |
|---|---|---|
| `dd-feature-development-workflow/SKILL.md` | Stage 路由表 Environment 行 | Stage 义务写入"实际要做什么"与"完成标志"两列 |
| `dd-feature-development-workflow/SKILL.md` | 红线 → 阶段纪律 | 新增一条：未完成绑定尝试并通过判定就过 Environment Gate |
| `dd-bug-fix-workflow/SKILL.md` | Stage 路由 → Environment 段 | 段内补义务句与判定要求（该文件用分段而非表格） |
| `dd-bug-fix-workflow/SKILL.md` | 红线 | 同上 |
| `dd-workflow-runtime/SKILL.md` | Preflight | 新增一条：声明该义务的工作流在 Environment Gate 前必须完成尝试 |
| `dd-workflow-runtime/SKILL.md` | 调用契约字段说明 | 明确 `tracking` 字段语义为"尝试结果"，非仅"已绑定时用于定位" |

**为什么写两处（Stage 行 + 红线）**：Stage 行保证"做什么"可见，红线保证"跳过会被判违规"。只有 Stage 行，Agent 可能读作建议；只有红线，Agent 不知道该做什么。

**为什么不把义务塞进 Stage 层 reference 的现有 bullet**：那里是 owner 合同调用点，且合同测试逐字锁定了该 bullet 的措辞（`test_feature_workflow_contracts.py::test_environment_owns_only_call_site`）。改动它会破坏既有单一事实源边界。

## 7. 与既有合同测试的关系

| 既有测试 | 关系 |
|---|---|
| `test_task_tracking.py::test_feature_and_bug_both_have_binding_hook` | 锁定 Stage 层 reference 调用点。入口层新增不触碰该断言 |
| `test_task_tracking.py::test_task_tracking_linked_from_runtime_skill` | 要求运行时入口含 owner 合同链接。新增 Preflight 条目须保留该链接 |
| `test_task_tracking.py::test_task_tracking_nested_schema_single_owner` | 禁止 `state.md` 出现 owner 嵌套字段。本设计只加 `tracking` 键，符合 |
| `test_task_tracking.py::test_projection_table_single_owner` | 禁止 stage→看板映射外泄。扫描 `rglob("*.md")` 但跳过含 `docs`／`tests` 段的路径，本设计的规格文档在 `docs/AI/` 下，自动豁免 |
| `test_task_tracking.py::check_consumers_delegate_tracking` 的 `## Bug State` 段落约束 | 该段落要求 canonical router 句**逐字**且**独占一段**，并禁止段内出现 `新建`／`创建`／`远端工单`／`任务卡`。因此义务表述**不得**写进 bug SKILL.md 的 `## Bug State` 节，只能写进 `## Stage 路由 → ### Environment` 与 `## 红线` |
| `test_feature_workflow_contracts.py::test_environment_owns_only_call_site` | 限定 Environment reference 段只含调用点与 Gate 条款两个 tracking 行（结构性计数 + 逐字锁定）。只读 `references/intake-and-environment.md`，**入口层 SKILL.md 不受此约束** |

**新增测试的落点**：判定层测试放 `dd-workflow-runtime/tests/test_validate_tracking_binding.py`（与 `test_validate_workflow_artifact.py` 同族）；入口层与漂移断言放 `test_task_tracking.py`（它已是 owner 合同的测试属主）。

## 8. FR 映射

| FR | 落点 |
|---|---|
| FR-1 | §6 入口层 Stage 行 |
| FR-2 | §6 入口层义务句直接指称创建 Issue |
| FR-3 | §6 `dd-workflow-runtime/SKILL.md` Preflight + 字段语义 |
| FR-4 | §5 `state.md` 预留位 |
| FR-5 | §3.1 判定层 CLI |
| FR-6 | §3.2 判定算法 + §3.3 不做对账 |
| FR-7 | §3.2 第二分支（legacy 直接 PASS） |
| FR-8 | §3.4 双向漂移断言 |
| FR-9 | §6 两入口对称改动 |
| FR-10 | §4 数据流 + §6 红线 |

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 判定层枚举与 owner 合同漂移 | §3.4 双向合同测试 |
| 入口层新增文字被后续重构删掉 | 入口层可发现性合同测试（AC-12） |
| 判定层被误当远端对账工具使用 | §3.3 明示无网络能力；源码无远端调用（AC-10） |
| `state.md` 新增键破坏既有 state 读取 | 键为可选，缺失时按 FR-7 兼容 |
| 判定层被当作 Gate 阻塞源 | §3.2 只有一种 FAIL 形态；AC-08 逐类覆盖 |
| 修复只覆盖本次两个工作流，速通模式仍缺 | 已在 Feature state 记为 deferred gap，不在本 Feature 静默扩张 |

## 10. NFR 满足方式

| NFR | 满足方式 |
|---|---|
| 不弱化现有硬 Gate | 本设计只增不减；判定层 FAIL 条件窄于 owner 红线 |
| 不改 owner 合同语义 | owner 合同文件零变更（AC-14） |
| 离线可运行 | 纯标准库，无 socket/网络调用 |
| 入口可发现性不因增字下降 | 义务写入既有 Stage 行与红线，不新增顶层章节 |
| 既有测试保持通过 | §7 冲突分析 + 全量运行 |

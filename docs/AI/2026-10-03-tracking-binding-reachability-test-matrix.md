# Task Tracking 绑定尝试入口可达性 Test Matrix

- Feature: tracking-binding-reachability
- Workflow ID: feature-development-20261003T053419Z-ee41fa8
- Stage: Test Matrix（验证合同）
- 基线 Requirements: v2 (`cf02335951f58a5c` 正文未变，FR-3 时序表述已修正)｜Design: v2 (`a952f8ec425be39c`)
- 版本: v2 — 同步 Design v1→v2 判定算法修订，并纳入 Final Candidate 强审发现的反例
- 日期: 2026-10-03

> **v1→v2 变更原因**：v1 头部绑定 Design v1，与已批准的 Design v2 不一致；v1 的 T-24 与 Design v2 明确冲突；v1 把 `sync_reason` 词表记为 10 个，而 Phase 0 tracer 实测 §4 只有 9 个带原因取值。外部强审（F 方向）判定 v1 不能作为当前实现的可靠 oracle。本版逐项修正，并把强审新增反例固化为 T-27~T-29、T-62~T-64、T-74~T-75。

## 1. 验证分层

| 层 | 手段 | 覆盖 AC | 执行位置 |
|---|---|---|---|
| L1 文档结构断言 | `dd-workflow-runtime/tests/test_task_tracking.py` 增补 | AC-01~AC-06, AC-12 | 本地 unittest |
| L2 判定层单测 | `dd-workflow-runtime/tests/test_validate_tracking_binding.py`（新增） | AC-07~AC-10 | 本地 unittest |
| L3 漂移一致性断言 | `test_task_tracking.py` 双向枚举比对 | AC-11 | 本地 unittest |
| L4 既有合同回归 | 全量 11 个既有测试模块 | AC-13, AC-14 | 本地 unittest |

无远端执行位置：判定器不触网（AC-10），入口层改动是纯文档。

## 2. L1 入口层与状态表示断言

新增测试类 `TestEntrypointReachability`。

| Test ID | AC | 断言 | 目标文件 |
|---|---|---|---|
| T-01 | AC-01 | Environment Stage 行文本同时含 owner 合同链接与动作指称（创建并绑定 Issue） | `dd-feature-development-workflow/SKILL.md` |
| T-02 | AC-01 | 该义务位于 Stage 路由表 Environment 行内，不在文件末尾的被动路由清单 | 同上（行位置约束） |
| T-03 | AC-04 | 红线含一条覆盖"未完成绑定尝试就过 Environment Gate" | 同上 |
| T-04 | AC-02 | Environment 段义务句直接出现创建 Issue 的动作指称，不只是指向 owner 合同 | `dd-bug-fix-workflow/SKILL.md` |
| T-05 | AC-04 | 红线含对应条目 | 同上 |
| T-06 | AC-02 | 义务表述**不在** `## Bug State` 节内（该节被既有测试逐字锁定且禁创建动词） | 同上 |
| T-07 | AC-05 | Preflight 含一条要求声明该义务的工作流在 Environment Gate 前完成尝试 | `dd-workflow-runtime/SKILL.md` |
| T-08 | AC-05 | Preflight 新增条目不替换既有 `references/task-tracking.md` 链接 | 同上（既有 `test_task_tracking_linked_from_runtime_skill` 的邻接保护） |
| T-09 | AC-06 | 通用字段表示的 JSON 示例含 `"tracking"` 键 | `dd-workflow-runtime/references/state.md` |
| T-10 | AC-06 | `state.md` 不含 owner 嵌套字段名（交由既有 `test_tracking_nested_schema_single_owner` 守护，T-10 只加正向断言） | 同上 |
| T-11 | AC-12 | 变异测试：临时移除 T-01 断言的义务表述后，T-01 必须失败 | 变异探针 |
| T-12 | AC-09（对称性） | 两个入口的义务表述都存在且都含动作指称（对称断言，防止只修一个） | 两个 SKILL.md |

**T-11 实现方式**：不修改磁盘文件，而是在测试内对读取文本做删除后重跑判定逻辑，断言判定函数返回 False。为纯字符串层变异，不需要 TDD 红灯。

## 3. L2 判定层单测

新增 `test_validate_tracking_binding.py`，fixture 构造 `make_state()`。

### 3.1 应判 FAIL（AC-07）

| Test ID | 输入 | 期望 |
|---|---|---|
| T-20 | `schema_version=2`, `workflow_type=feature-development`, `tracking` 缺失 | exit 1 |
| T-21 | 同上但 `tracking: null` | exit 1 |
| T-22 | 同上但 `workflow_type=bug-fix`, `tracking` 缺失 | exit 1 |
| T-23 | `tracking` 为对象但既无 `issue_number` 也无 `sync` | exit 1 |
| T-24 | `tracking={"provider":"github","sync":"not-synced"}`：`sync` 需要原因却缺 `sync_reason`，且无绑定 | exit 1（v1 此条写的是 `sync=synced` 缺原因判 1，与 Design v2 冲突：§4 该行 `sync_reason` 为 `—`，`synced` 本身即已记录） |
| T-25 | `tracking.sync="not-synced"`, `sync_reason="不存在的值"` | exit 1（未知原因值不合规） |
| T-26 | `tracking.provider="gitlab"`（未登记 provider） | exit 1 |
| T-27 | `issue_number` ∈ {`0`, `""`, `False`, `-1`, `[]`, `{}`, `1.0`}，无 `sync` | exit 1（只有正整数才是 Issue 号；`-1` 虽为真值但不是 Issue 号） |
| T-28 | `schema_version` ∈ {`"2"`, `"1"`, `True`, `False`, `2.5`, `[]`, `{}`} + `tracking=null` | exit 2（非整数是残缺状态，不得当作 legacy 放行，也不得当作未尝试判 1） |
| T-29 | `workflow_type` ∈ {缺失, `""`, `"feature"`, `"Feature-Development"`, `7`} | 非 exit 0（未识别类型不得 fail-open） |
| T-62 | `(sync, sync_reason)` 为 §4 未定义的交叉组合：`not-authorized`+`issue-missing`、`not-synced`+`user-declined`、`not-authorized`+`binding-ambiguous`、`not-synced`+`no-policy`、`disabled`+`issue-missing`、`synced`+`no-policy` | exit 1（词表合法但配对非法） |
| T-63 | `tracking.provider` / `sync` / `sync_reason` 为 `[]`、`{}`、`7`、`[1,2]` | 无 Traceback，且退出码 ∈ {1, 2}（unhashable 不得崩成 exit 1） |
| T-64 | state 文件为非法 UTF-8 字节 | exit 2，无 Traceback |

### 3.2 应判 PASS —— 有效绑定（AC-07）

| Test ID | 输入 | 期望 |
|---|---|---|
| T-30 | `issue_number=8`, `repository="o/r"`, `provider="github"`, `sync="synced"` | exit 0 |
| T-31 | `issue_number=8`, `sync="not-synced"`, `sync_reason="issue-missing"` | exit 0 |

### 3.3 应判 PASS —— 已记录的每一类失败／拒绝（AC-08）

每类独立一例，`sync` 与 `sync_reason` 取 `task-tracking.md` §4 对应行的**配对**。

| Test ID | §4 情形 | `sync` | `sync_reason` |
|---|---|---|---|
| T-40 | 远端不可达／无法解析 | `not-synced` | `remote-unresolvable` |
| T-41 | Issue 缺失 | `not-synced` | `issue-missing` |
| T-42 | 项目未授权 | `not-authorized` | `no-policy` |
| T-43 | 用户拒绝创建 | `not-authorized` | `user-declined` |
| T-44 | 绑定歧义 | `not-synced` | `binding-ambiguous` |
| T-45 | 创建结果不确定 | `not-synced` | `create-outcome-unknown` |
| T-46 | 历史未分类 | `not-synced` | `legacy-tracking-unknown` |
| T-47 | 无 Issue 能力远端 | `not-synced` | `no-issue-capable-remote` |
| T-48 | 凭据／服务不可用 | `not-synced` | `provider-unavailable` |
| T-49 | 用户禁用 | `disabled` | 允许 `null`（§4 该行为 `—`） |

### 3.4 应判 PASS —— 历史状态与范围外（AC-09, AC-10）

| Test ID | 输入 | 期望 | 依据 |
|---|---|---|---|
| T-50 | `schema_version` 缺失, `tracking` 缺失 | exit 0 | Design §3.2 分支 2；不得据其触发创建 |
| T-51 | `schema_version=1`, `tracking: null` | exit 0 | 同上 |
| T-52 | `schema_version=0`, `tracking: null` | exit 0 | 同上 |
| T-53 | `schema_version=1`, `tracking` 对象带有效 `issue_number` | exit 0 | 已绑定即有效 |
| T-54 | `workflow_type=project-bootstrap`, `schema_version=2`, `tracking` 缺失 | exit 0 | owner §12：bootstrap 不适用 |
| T-55 | 状态文件不存在 | exit 2 | 输入错误，不是 Gate 失败 |

### 3.5 离线性（AC-10）

| Test ID | 断言 |
|---|---|
| T-56 | 判定器源码不含 `socket`／`urllib`／`http`／`requests`／`gh`／`subprocess` 的导入或调用 |
| T-57 | 在清空 `HOME`＋`PATH` 的子进程环境中断言仍 exit 0（不读凭据、不依赖 `gh` 在 PATH） |

## 4. L3 漂移一致性断言（AC-11）

| Test ID | 断言 |
|---|---|
| T-70 | 判定器内置 `SYNC_VALUES` == owner 合同 §2 表 `sync` 行取出的全部取值，双向相等 |
| T-71 | 判定器内置 `SYNC_REASONS` ⊇ owner 合同 §4 表 `sync_reason` 列取出的全部取值（owner 新增原因 → 测试失败） |
| T-72 | 判定器内置 `SYNC_REASONS` ⊆ owner 合同 §4 表 + §2 的 `user-declined`／`disabled` 允许集（判定器不得发明词表外取值） |
| T-73 | 判定器引用的 `tracking` 子字段名 ⊆ owner 合同 §2 schema 块声明的字段名 |
| T-74 | 判定器 `RECORDED_OUTCOMES`（`(sync, sync_reason)` 配对集）== §4 表逐行抽出的配对集，双向相等 |
| T-75 | 判定器 `SUPPORTED_PROVIDERS` == §2 登记的 provider |

T-70~T-75 从 `task-tracking.md` 用正则抽取词表/配对，与判定器常量双向比对。抽取失败（如表格结构变化）必须 FAIL 而非静默跳过——否则 owner 改版后测试假绿。

**配对与 provider 也必须锁**：§4 为每个 `sync` 值配定了**特定**原因值，只锁平铺词表会让 `not-authorized` + `issue-missing` 这类合同从未定义的组合通过，等于判定器在组合语义上成为第二事实源。

**M1~M7 变异探针**（`TestVocabularyDriftMutations`）：

| 变异 | 内容 | 期望被哪条抓住 |
|---|---|---|
| M1 | 判定器新增词表外 `sync` 值 | T-70 |
| M2 | 判定器新增词表外 `sync_reason` | T-72 |
| M3 | owner 新增一条 `sync_reason`（判定器未跟） | T-71、T-74 |
| M4 | 判定器读取 owner 未声明的字段 | T-73 |
| M5 | `RECORDED_OUTCOMES` 删掉 `disabled` 行 | T-74、自记录断言 |
| M6 | 判定器新增 §4 未定义的交叉配对 | T-74 |
| M7 | 判定器清空 `SUPPORTED_PROVIDERS` | T-75 |

变异 harness 必须断言 `errors == []`、至少一个 failure、且失败者是上表预期断言之一。只看 `wasSuccessful()` 会把 SyntaxError、import 失败或抽取 helper 的意外异常误判为"已捕获"。

**T-14 入口层语义变异**（`TestEntrypointReachability`）：入口断言不满足于关键词存在，必须在下列语义反转后全部变红——删除义务句、极性反转为「无需按」／「可选」、时序反转为 `Gate 后`、时序反转为 `进入 Environment Stage 之前`、引入未授权的 `checkpoint` 措辞。入口谓词同时禁止否定词（无需／不必／可选／非必须／可以不／自行决定／视情况）与错误时序（`Gate 后`／`Gate 之后`／`Stage 之前`／`阶段之前`／`进入 Environment 前`）。

## 5. Population 分母与 item registry

| 项 | 分母 | item registry |
|---|---|---|
| §4 失败矩阵行 | 11 行 = 1 行绑定有效（`synced`，原因列为 `—`）+ 10 类失败/拒绝 | T-30/T-31 覆盖绑定有效；T-40~T-49 覆盖 10 类。分母 = 11，分子 = 11 |
| §4 中带 `sync_reason` 取值的行 | **9** 行（Phase 0 tracer 实测；另 2 行 `synced`／`disabled` 原因列为 `—`） | T-40~T-48 逐一覆盖；T-49 覆盖 `disabled` 无原因行 |
| `sync` 取值 | 4 | `synced`／`not-synced`／`not-authorized`／`disabled`，由 T-70 机械双向覆盖 |
| `(sync, sync_reason)` 配对 | 11（= §4 全部数据行） | T-74 双向覆盖；T-62 反向覆盖 6 组非法交叉配对 |
| `provider` 取值 | 1（`github`） | T-75 双向覆盖 |
| 入口层义务表述 | 3（Feature／Bug／runtime Preflight） | T-01／T-04／T-07／T-12 |
| 改动文件 | 4 源文件 + 1 新脚本 + 2 测试文件 + 6 规格/证据文档 | 见 §6 覆盖矩阵 |

**完备性要求**：`sync` 取值、`sync_reason` 词表、`(sync, sync_reason)` 配对、`provider` 取值四者都必须双向覆盖。任何一侧新增而另一侧未更新 → L3 失败。

## 6. AC → Test 覆盖矩阵

| AC | 覆盖 Test | 层 |
|---|---|---|
| AC-01 | T-01, T-02 | L1 |
| AC-02 | T-04, T-06 | L1 |
| AC-03 | T-01, T-04 | L1 |
| AC-04 | T-03, T-05 | L1 |
| AC-05 | T-07, T-08 | L1 |
| AC-06 | T-09, T-10 | L1 |
| AC-07 | T-20~T-29（FAIL/usage）, T-30~T-31（PASS） | L2 |
| AC-08 | T-40~T-49（逐类 10 例）, T-62（反向非法配对） | L2 |
| AC-09 | T-50~T-54 | L2 |
| AC-10 | T-55, T-56, T-57, T-63, T-64 | L2 |
| AC-11 | T-70~T-75, M1~M7 | L3 |
| AC-12 | T-11, T-14 | L1 |
| AC-14 | `git diff --name-only` 不含 `task-tracking.md` | L4 |

AC-01~AC-14 全部有覆盖，无孤立 AC。

## 7. Evidence schema

| 字段 | 取值 |
|---|---|
| `layer` | L1 / L2 / L3 / L4 |
| `test_id` | T-nn |
| `result` | PASS / FAIL |
| `observed` | 实际退出码或断言结果 |
| `run_sha` | 执行时的 `git rev-parse HEAD` |

## 8. Oracle

- L1/L3：直接读取规范文件的确定性文本断言，无主观判断。
- L2：退出码 + 内存 fixture，不触网。
- L4：既有测试全绿 + `git diff --name-only` 集合比对。

## 9. 数值 policy

无阈值型数值。唯一计数型断言是"恰好 2 行 tracking"类既有结构性断言，本设计不新增计数阈值。

## 10. 已知覆盖缺口

| 缺口 | 处置 |
|---|---|
| 无法机械验证"Agent 实际读了入口文件并执行" | 属宿主行为，超出文档层可判定范围。缓解：T-11/T-12 保证入口表述不被静默删除 |
| 判定器被 Agent 主动跳过而不运行 | 同样属宿主行为。缓解：入口红线 + Gate 条件把"未运行"与"不通过"等同处理 |
| 真实 GitHub 远端上 `gh issue create` 的端到端 | 本 Feature 不执行远端动作；已由本次 Environment Stage 实际创建 Issue #8 独立佐证 §8.1 授权路径可用 |

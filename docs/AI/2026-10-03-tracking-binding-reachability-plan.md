# Task Tracking 绑定尝试入口可达性 实现计划

> **面向 AI 代理的工作者：** 由 `dd-feature-development-workflow` 的 Implementation Stage 逐 Phase 执行本计划；步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 让"必须尝试并记录外部任务绑定"这一既有硬约束在 Feature/Bug 工作流入口可达，并提供离线可运行的 Gate 判定器，使静默跳过变为确定性失败。

**架构：** 三层改动。入口层（三个 `SKILL.md`）补义务可发现性；状态表示层（`state.md`）补 `tracking` 预留位；判定层新增 `agents/validate-tracking-binding.py`，纯离线状态形状检查器，内置枚举由合同测试与 owner 合同双向锁定。owner 合同 `task-tracking.md` 零改动。

**技术栈：** Python 3（标准库 `argparse`/`json`/`re`/`pathlib`/`importlib`）、`unittest`、Markdown 合同文本。

---

## Phase plan 头部

```
source_manifest:
  SPEC-REQ:
    stable_id: SPEC-REQ
    path: docs/AI/2026-10-03-tracking-binding-reachability-requirements.md
    version: v3
    digest: sha256:dceaecc699c94daf72393f0adb6a50300cd9bb91e777c9deec02f68943fbd08c
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: intake-confirm}
  SPEC-DES:
    stable_id: SPEC-DES
    path: docs/AI/2026-10-03-tracking-binding-reachability-design.md
    version: v4
    digest: sha256:e09f81c17510eb19d9e21675efe371cf9718e2f8ff41090f7148de4ec54b1217
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: design-confirm}
  SPEC-TM:
    stable_id: SPEC-TM
    path: docs/AI/2026-10-03-tracking-binding-reachability-test-matrix.md
    version: v4
    digest: sha256:83c00898d2a3d1887426d6c1859ba0b960eb823ad03337542c1773d7d3a8f9f3
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: tm-confirm}
  OWNER-TT:
    stable_id: OWNER-TT
    path: dd-workflow-runtime/references/task-tracking.md
    version: current
    digest: sha256:833004169350ced186f585c7e6730f5566252eb9a7635f67fb4c6284c5589f07
    approval: {status: frozen-owner, authority: repository, decided_at: 2026-10-02, evidence_ref: origin/develop@94dcc9a (fast-track 纳入 tracking 合同)}
    note: 语义属主，本计划只读，零改动
  BASE-STATE:
    stable_id: BASE-STATE
    path: dd-workflow-runtime/references/state.md
    version: current
    digest: sha256:0c29a143f46df7b26574d509002f2ed010df6f4665ce1d979769d2f68f383b87
    approval: {status: baseline, authority: repository, decided_at: 2026-10-03, evidence_ref: origin/develop@94dcc9a (合并基线)}
```

**Phase 划分（`split_mode: simple`，Phase ≤ 2）：**

| Phase | 名称 | 依赖 | ac_keys |
|---|---|---|---|
| 0 | Tracer：验证词表抽取假设 | — | AC-11 |
| 1 | 判定层（脚本 + 单测 + 漂移锁定） | Phase 0 | AC-07~AC-11 |
| 2 | 入口层 + 状态表示 | Phase 1 | AC-01~AC-06, AC-12 |

---

### 任务 0：Tracer — 验证词表抽取假设

**sources:** `[{ref: SPEC-DES, anchors: [3.4, 3.2]}, {ref: OWNER-TT, anchors: [2, 4]}, {ref: SPEC-TM, anchors: [T-70, T-73]}]`

**Consumes：** 真实 `dd-workflow-runtime/references/task-tracking.md`；本工作流真实 state 文件 `$(git rev-parse --git-dir)/feature-development-state.json`。

**Produces：** 探针脚本与取证记录 `docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.md`，含抽取词表、真实 state 判定退出码、`result` 结论。

```
write_scope:
  - create: docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.md
  - create: docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.py
  - modify: none
  - delete: none
```

- [ ] **步骤 1：写探针抽取真实词表**

  用 `re` 从 `OWNER-TT` 抽取：`sync` 取 §2 表格首列反引号内容；`sync_reason` 取 §4 表格第三列反引号内容。任一抽取为空或数量与 Design §3.2 假设不符 → `result: BLOCKED`，停止并回 Planning（不得在 Implementation 内改判定设计）。

- [ ] **步骤 2：运行探针**

  `verification:` `python3 docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.py`
  预期：打印抽取到的 `sync` 4 项与 `sync_reason` 词表，退出码 0。

- [ ] **步骤 3：对真实 state 跑判定探针**

  `verification:` 探针对本工作流真实 state 执行判定逻辑
  预期：退出码 0（真实 state 已绑定 Issue #8，落在 Design §3.2 分支 ①）。

- [ ] **步骤 4：记录 tracer 结果**

  写 `L03-vocab-extract-probe.md`：`result: passed` + 抽取词表 + 退出码 + `implementation_digest`。假设不成立则 `result: BLOCKED`，按 tracer-contract §7 回 Planning。

```
stop_conditions: 抽取失败或词表与 Design 3.2 不符 -> BLOCKED，回 Planning
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-phase-0}
```

---

### 任务 1：判定器骨架与 FAIL 路径

**sources:** `[{ref: SPEC-DES, anchors: [3.1, 3.2]}, {ref: SPEC-REQ, anchors: [FR-5, FR-6, AC-07]}, {ref: SPEC-TM, anchors: [T-20, T-26, T-55]}]`

**Consumes：** 任务 0 的 `result: passed`。

**Produces：** `dd-workflow-runtime/agents/validate-tracking-binding.py`，支持 `--state <path>`，退出码 0/1/2。

```
write_scope:
  - create: dd-workflow-runtime/agents/validate-tracking-binding.py
  - create: dd-workflow-runtime/tests/test_validate_tracking_binding.py
  - modify: none
  - delete: none
```

- [ ] **步骤 1：编写失败的测试（T-20~T-26, T-55）**

  写 `make_state(**overrides)` fixture 与 T-20~T-29、T-55，用 `subprocess` 取 `(returncode, stdout, stderr)`。

`run_validator` 必须返回 stderr：未捕获异常的 traceback 写 stderr 且退出码为 1（与 Gate FAIL 同码）。只读 stdout、或只要求「非 0」、或只要求 `assertIn(code, (FAIL, USAGE))`，都会让真实 crash 变成绿灯。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：FAIL，原因是缺少判定行为。

- [ ] **步骤 3：编写最少实现**

  实现 Design §3.2 的 ①~⑪ 分派（编号与 evaluate() docstring 一一对应）：`workflow_type` 身份（强制集 = owner §2 的四类长流程工作流） → **豁免前置** → schema 判定（legacy 精确集 {缺失,0,1}；非整数与负数判 exit 2）→ tracking 形状 → **provider/sync/sync_reason 字符串 well-formedness（先于绑定检查）** → provider 未登记 → 正整数 `issue_number` → `RECORDED_OUTCOMES` 配对 → FAIL 兜底。只实现 T-20~T-29/T-55 所需分支。禁止 `socket`/`urllib`/`http`/`requests`/`gh`/`subprocess`。

- [ ] **步骤 4：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：PASS。

```
stop_conditions: 判定器需要任何远端调用才能给出结论 -> 停止，回 Design 3.3 复核
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-1}
```

---

### 任务 2：PASS 分支全覆盖与离线断言

**sources:** `[{ref: SPEC-DES, anchors: [3.2, 3.3]}, {ref: SPEC-REQ, anchors: [FR-6, FR-7, AC-08, AC-09, AC-10]}, {ref: SPEC-TM, anchors: [T-30, T-57]}, {ref: OWNER-TT, anchors: [4, 12]}]`

**Consumes：** 任务 1 的判定器。

**Produces：** 覆盖 §4 全部 11 行 + legacy + bootstrap + 离线的完整单测集。

```
write_scope:
  - modify: dd-workflow-runtime/agents/validate-tracking-binding.py
  - modify: dd-workflow-runtime/tests/test_validate_tracking_binding.py
  - create: none
  - delete: none
```

- [ ] **步骤 1：编写失败的测试（T-30~T-31, T-40~T-57）**

  逐例构造 fixture：绑定（T-30/T-31）、§4 十类失败/拒绝（T-40~T-49）、legacy 三态（T-50~T-52）、**legacy 部分 tracking 对象（T-67：FAIL 只属于当前 schema）**、已绑定 legacy（T-53）、bootstrap（T-54）、豁免前置（T-65）、`("synced", None)` 无绑定的自记录配对分支（T-66）、嵌套非字符串值（T-63：精确 exit 2 + stderr 无 Traceback）、非法 UTF-8（T-64）、有效绑定 + 畸形兄弟字段（T-68）、词表外取值无 sync 时的 ⑩ 分支（T-69）、**四类长流程工作流的判定覆盖（T-78~T-81：两个速通类型未尝试判 1、已绑定判 0、FAIL 诊断须区分 Environment/Intake Gate、legacy 豁免一致）**、离线（T-56/T-57）。所有判 FAIL 的用例都要先过 `assert_clean_run`。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：FAIL，失败点为未实现分支或未列入的词表值。

- [ ] **步骤 3：补最少实现**

  补 Design §3.2 ⑨⑩⑪：按 `RECORDED_OUTCOMES` 配对判定 `sync`/`sync_reason`；`("synced", None)` 与 `("disabled", None)` 两行不要求原因值；配对之外的组合与词表外取值判 exit 1。另补 ⑥ 的非字符串类型前置（**必须先于 ⑧ 的绑定检查**：有效绑定与畸形 sync 并存的状态自相矛盾，不得凭绑定放行，见 T-68），使不可 hash 的嵌套值成为 exit 2 而非未捕获异常。

- [ ] **步骤 4：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：PASS，§4 的 11 行分母全部命中。

```
stop_conditions: 任一 4 节情形无法表达为 PASS -> 停止，回 OWNER-TT 复核而非扩展判定器语义
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-2}
```

---

### 任务 3：词表双向漂移锁定

**sources:** `[{ref: SPEC-DES, anchors: [3.4]}, {ref: SPEC-REQ, anchors: [FR-8, AC-11]}, {ref: SPEC-TM, anchors: [T-70, T-77]}]`

**Consumes：** 任务 0 的抽取结论、任务 1/2 的判定器常量、`OWNER-TT`。

**Produces：** `dd-workflow-runtime/tests/test_task_tracking.py` 新增 `TestVocabularyDrift`（8 例）与 `TestVocabularyDriftMutations`（11 个变异）。

```
write_scope:
  - modify: dd-workflow-runtime/tests/test_task_tracking.py
  - create: none
  - delete: none
```

- [ ] **步骤 1：编写失败的测试（T-70~T-77）**

  新增 `TestVocabularyDrift`：`importlib` 读判定器常量；`re` 从 `OWNER-TT` 抽取。

  - T-70 `sync` 双向相等；
  - T-71 `sync_reason` 覆盖 §4 全部（owner 新增即失败）；
  - T-72 判定器词表 ⊆ §4 `sync_reason` 列（`disabled` 是 `sync` 取值，不属该词表）；
  - T-73 子字段名 ⊆ §2 schema 块；
  - T-74 `RECORDED_OUTCOMES` 配对集 == §4 逐行 `(sync, sync_reason)` 配对；
  - T-75 `SUPPORTED_PROVIDERS` == §2 登记的 provider；
  - T-76 mandatory／exempt workflow type 集 == §2 与 §12（§12 按「声明不适用」的行识别，不按在表中出现，否则 `dd-git-workflow` 会被误认）；
  - T-77 legacy 边界：§3.2 字面写 `< 2`；判定器保留所有低于当前版本的**非负**整数并显式拒绝负数。这是对字面文本的有意收窄（否则负版本会让未尝试状态通过），因此断言写成关系（`legacy == range(current)`、负数不在 legacy、owner 表达式仍为 `< 2`）而非与字面相等。

  **抽取失败必须 FAIL，不得 skip。**

- [ ] **步骤 1b：编写变异探针（M1~M11）**

  `TestVocabularyDriftMutations` 在内存中改判定器或 owner 副本，要求对应 guard 变红：M1 新增词表外 `sync`；M2 新增词表外 `sync_reason`；M3 owner 新增 `sync_reason`；M4 读 owner 未声明字段；M5 `RECORDED_OUTCOMES` 删 `disabled`；M6 新增 §4 未定义交叉配对；M7 清空 `SUPPORTED_PROVIDERS`；M8 owner 新增第三个 mandatory type；M9 owner 把边界改为 `< 3`；M10 判定器把当前版本吞进 legacy；M11 判定器单方面把 current→3 且 legacy→{0,1,2} 而 owner 不动（联合漂移）。

  harness 必须断言 `errors == []`、至少一个 failure、且**所有** failure 都属于该变异的预期断言——夹带一个无关断言失败也要判红。只看 `wasSuccessful()` 会把 SyntaxError 或 import 失败误判为「已捕获」。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking.TestVocabularyDrift`
  预期：FAIL，原因是常量未对齐或模块不可导入。

- [ ] **步骤 3：补最少实现**

  在判定器中把 `SYNC_VALUES`/`SYNC_REASONS`/`TRACKING_FIELDS`/`RECORDED_OUTCOMES`/`SUPPORTED_PROVIDERS`/`MANDATORY_WORKFLOW_TYPES`/`EXEMPT_WORKFLOW_TYPES`/`LEGACY_SCHEMA_VERSIONS` 提为模块级常量，不改变判定行为。`SELF_RECORDING_SYNC` 必须从 `RECORDED_OUTCOMES` 派生，不可独立硬编码。

- [ ] **步骤 4：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking.TestVocabularyDrift dd-workflow-runtime.tests.test_task_tracking.TestVocabularyDriftMutations`
  预期：PASS。

```
stop_conditions: 抽取正则无法稳定解析 OWNER-TT 表格 -> BLOCKED，回 Planning
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-3}
```

---

### 任务 4：入口层可发现性断言（先红）

**sources:** `[{ref: SPEC-REQ, anchors: [FR-1, FR-2, FR-9, FR-10, AC-01, AC-02, AC-12]}, {ref: SPEC-DES, anchors: [6]}, {ref: SPEC-TM, anchors: [T-01, T-13]}]`

**Consumes：** 无（不依赖判定器）。

**Produces：** `test_task_tracking.py` 新增 `TestEntrypointReachability`，先全部 FAIL。

```
write_scope:
  - modify: dd-workflow-runtime/tests/test_task_tracking.py
  - create: none
  - delete: none
```

- [ ] **步骤 1：编写失败的测试（T-01~T-06, T-11~T-13）**

  T-01 Feature `SKILL.md` 的 `| Environment |` 行同时含 owner 合同链接与创建 Issue 的动作指称；T-02 该义务出现在 Stage 路由表行内而非文件末尾被动清单；T-03 Feature 红线含未尝试就过 Gate 的条目；T-04 Bug `SKILL.md` 的 `### Environment` 段含动作指称；T-05 Bug 红线含对应条目；T-06 Bug 义务表述不在 `## Bug State` 节内；T-11 变异测试（删除义务句后判定须返回 False）；T-12 两入口对称；T-13 负向断言——两入口义务句均不含 `checkpoint`/`关闭`/`看板`，防止可见性修复被误读为更宽授权。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking.TestEntrypointReachability`
  预期：FAIL，原因是三个入口尚未表达该义务。

```
stop_conditions: 断言与既有 CANONICAL_BUG_ROUTER_LINE 段落锁定冲突 -> BLOCKED，回 Design 7 复核
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-4}
```

---

### 任务 5：入口层与状态表示改写（转绿）

**sources:** `[{ref: SPEC-REQ, anchors: [FR-1, FR-2, FR-3, FR-4, FR-10, AC-01, AC-06]}, {ref: SPEC-DES, anchors: [5, 6]}]`

**Consumes：** 任务 4 的失败测试。

**Produces：** 三个入口文件的义务表述 + `state.md` 的 `tracking` 预留位。

```
write_scope:
  - modify: dd-feature-development-workflow/SKILL.md
  - modify: dd-bug-fix-workflow/SKILL.md
  - modify: dd-workflow-runtime/SKILL.md
  - modify: dd-workflow-runtime/references/state.md
  - create: none
  - delete: none
```

- [ ] **步骤 1：按 T-01~T-05 改写入口**

  - Feature `SKILL.md`：`| Environment |` 行"实际要做什么"列加入"Environment Gate 前必须为本工作流创建并绑定一张 GitHub Issue（按 owner 合同 §3）"，"完成标志"列加入"绑定尝试结果已记录且判定器通过"；红线 → 阶段纪律加一条。
  - Bug `SKILL.md`：`### Environment` 段内加同义义务句与判定要求；红线加一条。**不得触碰 `## Bug State` 节**（既有测试逐字锁定该段）。
  - `dd-workflow-runtime/SKILL.md`：Preflight 新增一条"以 Environment Gate 为绑定 Gate 的 Feature/Bug 两类工作流在 Environment Gate 前必须完成尝试"（并写明速通工作流走 Intake Gate、不由本条声明）；调用契约 `tracking` 说明改为表述尝试结果而非仅已绑定时定位；保留既有 `references/task-tracking.md` 链接（T-08）。
  - 三处义务句只表述"创建并绑定 Issue"（§8.1 授权范围内），**不得提及 checkpoint/关闭/看板**（T-13）。

- [ ] **步骤 2：按 T-09/T-10 补状态表示**

  `dd-workflow-runtime/references/state.md` 通用字段 JSON 示例加 `"tracking": null`，注释指向 owner 合同；**不得出现** `issue_number`/`sync_reason`/`pending_checkpoint`/`last_checkpoint_ref`。

- [ ] **步骤 3：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking`
  预期：PASS，含既有全部用例与新增 `TestEntrypointReachability`。

```
stop_conditions: 改动触发既有合同测试 FAIL -> 先判定是本改动越界还是既有断言需按合同变化调整；属后者须保留原保护目的并说明理由，不得删弱断言
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-5}
```

---

### 任务 6：全量回归与 AC-13/AC-14 验证

**sources:** `[{ref: SPEC-TM, anchors: [L4, AC-13, AC-14]}]`

**Consumes：** 任务 1~5 全部产出。

**Produces：** 全量测试运行记录 + `git diff --name-only` 集合证据。

```
write_scope:
  - create: none
  - modify: none
  - delete: none
```

- [ ] **步骤 1：全量回归**

  `verification:` `for f in dd-*/tests/test_*.py; do m="${f%.py}"; m="${m//\//.}"; python3 -m unittest "$m"; done`
  预期：全部 OK（合并上游后共 14 个测试模块：本 Feature 新增 1 个判定层模块，其余 13 个为既有模块，含上游随 fast-track 新增的 3 个）。

- [ ] **步骤 2：验证 AC-14**

  `verification:` `git diff --name-only origin/develop...HEAD` 与 `git status --porcelain`
  预期：变更集合不含 `dd-workflow-runtime/references/task-tracking.md`。

  oracle 基线是**当前 PR 基线** `origin/develop`，不是本 Feature 的起点 `ee41fa8`：
  合并 fast-track 上游 commit 后，`ee41fa8..HEAD` 本身包含上游对 owner 合同的合法
  修改，用它做 diff 会把上游变更误判为越界。AC-14 的真实命题是"我的净改动为零"，
  即本分支与 origin/develop 的 owner 文件逐字节相同。

- [ ] **步骤 3：验证 AC-12 端到端**

  临时删除 Feature 入口义务句 → 运行 T-01 → 预期 FAIL → 恢复。恢复后 `git status` 必须干净。

```
stop_conditions: 全量回归 FAIL 且无法在本计划内修复 -> BLOCKED 回 Planning
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-6}
```

---

## AC → Task → Test 映射

| AC | Task | Test |
|---|---|---|
| AC-01 | 5 | T-01, T-02 |
| AC-02 | 5 | T-04, T-06 |
| AC-03 | 5 | T-01, T-04 |
| AC-04 | 5 | T-03, T-05 |
| AC-05 | 5 | T-07, T-08 |
| AC-06 | 5 | T-09, T-10 |
| AC-07 | 1, 2 | T-20~T-29, T-30~T-31, T-78~T-79, T-81 |
| AC-08 | 2 | T-40~T-49, T-62, T-80, T-80b |
| AC-09 | 2 | T-50~T-54, T-67 |
| AC-10 | 2 | T-55, T-56, T-57, T-63, T-64, T-65, T-66, T-68, T-69 |
| AC-11 | 0, 3 | T-70~T-77, M1~M11 |
| AC-12 | 4, 6 | T-11, T-14, T-15 |
| AC-13 | 6 | 全量既有测试模块 |
| AC-14 | 6 | `git diff --name-only origin/develop...HEAD` |

AC-01~AC-14 全部有 Task 与 Test，无孤立项。

T-13~T-15 为 Planning 与外部强审阶段新增的断言，已回填 Test Matrix v2：T-13 是负向断言（入口义务句不得出现 checkpoint/关闭/看板，来源 `review_level=high` 命中的安全或权限触发器）；T-14 是入口语义变异（极性/时序/子句拆分/未授权措辞）；T-15 专测「把必须留在无关句里」这一子句绑定的绕过目标。

## Tracer 判定

```
tracer:
  decision: required
  reason: 命中 review-gate 风险分类（跨模块改动、Public API、持久化数据、安全或权限），
          且存在未验证的高风险架构假设——从 owner 合同真实表格抽取词表的正则可行性未经验证，
          假设失效将使 FR-8 防漂移方案整体失效
  target_ac: AC-11
```

## 回滚点

| Phase | 回滚动作 |
|---|---|
| 1 | 删除 `agents/validate-tracking-binding.py` 与 `tests/test_validate_tracking_binding.py`；无既有文件被改 |
| 2 | `git checkout -- dd-feature-development-workflow/SKILL.md dd-bug-fix-workflow/SKILL.md dd-workflow-runtime/SKILL.md dd-workflow-runtime/references/state.md dd-workflow-runtime/tests/test_task_tracking.py` |

两个 Phase 的写入范围互不重叠，可独立回滚。

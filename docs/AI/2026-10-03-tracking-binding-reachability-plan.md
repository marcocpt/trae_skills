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
    version: v1
    digest: sha256:cf02335951f58a5c393294cc24cb56ce1ce2307c5645dcf8c552c3c06f1a7323
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: intake-confirm}
  SPEC-DES:
    stable_id: SPEC-DES
    path: docs/AI/2026-10-03-tracking-binding-reachability-design.md
    version: v2
    digest: sha256:a952f8ec425be39cb6d612d30ddca51d2c14ed28ebe5d1fc461432b17b3779b6
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: design-confirm}
  SPEC-TM:
    stable_id: SPEC-TM
    path: docs/AI/2026-10-03-tracking-binding-reachability-test-matrix.md
    version: v1
    digest: sha256:c4278fd9fc20450b0fd8ebebad23c1df18dcddedb1d692f99b658e1d4b32b26c
    approval: {status: approved, authority: user, decided_at: 2026-10-03, evidence_ref: tm-confirm}
  OWNER-TT:
    stable_id: OWNER-TT
    path: dd-workflow-runtime/references/task-tracking.md
    version: current
    digest: sha256:bb4339161b084d3e1bf9c92f3968eeac81ff0dabd185f5dbbabf5507ac67b274
    approval: {status: frozen-owner, authority: repository, decided_at: 2026-10-02, evidence_ref: commit-903a96e}
    note: 语义属主，本计划只读，零改动
  BASE-STATE:
    stable_id: BASE-STATE
    path: dd-workflow-runtime/references/state.md
    version: current
    digest: sha256:9c196d16c4533143f5920b59b8f68eda54fe959d355ab940ebcf6416c22e111d
    approval: {status: baseline, authority: repository, decided_at: 2026-10-03, evidence_ref: commit-ee41fa8}
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

  写 `make_state(**overrides)` fixture 与 T-20~T-26、T-55 共 8 例，用 `subprocess` 取退出码。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：FAIL，原因是缺少判定行为。

- [ ] **步骤 3：编写最少实现**

  实现 Design §3.2 分派：`workflow_type` 白名单 → legacy 豁免 → bootstrap 豁免 → `provider` well-formedness → FAIL 兜底。只实现 T-20~T-26/T-55 所需分支。禁止 `socket`/`urllib`/`http`/`requests`/`gh`/`subprocess`。

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

  逐例构造 fixture：绑定（T-30/T-31）、§4 十类失败/拒绝（T-40~T-49 各一例）、legacy 三态（T-50~T-52）、已绑定 legacy（T-53）、bootstrap（T-54）、离线（T-56 源码无网络与子进程符号；T-57 清空 `HOME`+`PATH` 子进程仍 exit 0）。

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：FAIL，失败点为未实现分支或未列入的词表值。

- [ ] **步骤 3：补最少实现**

  按 Design §3.2 分支 ②③ 补 `sync`/`sync_reason` 判定；`disabled` 允许 `sync_reason` 为 `null`。

- [ ] **步骤 4：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_validate_tracking_binding`
  预期：PASS，§4 的 11 行分母全部命中。

```
stop_conditions: 任一 4 节情形无法表达为 PASS -> 停止，回 OWNER-TT 复核而非扩展判定器语义
delivery_authorization: {status: not-required, actions: [], scope: none, authority: none, decided_at: 2026-10-03, evidence_ref: no-git-action-in-task-2}
```

---

### 任务 3：词表双向漂移锁定

**sources:** `[{ref: SPEC-DES, anchors: [3.4]}, {ref: SPEC-REQ, anchors: [FR-8, AC-11]}, {ref: SPEC-TM, anchors: [T-70, T-73]}]`

**Consumes：** 任务 0 的抽取结论、任务 1/2 的判定器常量、`OWNER-TT`。

**Produces：** `dd-workflow-runtime/tests/test_task_tracking.py` 新增 `TestVocabularyDrift`（4 例）。

```
write_scope:
  - modify: dd-workflow-runtime/tests/test_task_tracking.py
  - create: none
  - delete: none
```

- [ ] **步骤 1：编写失败的测试（T-70~T-73）**

  新增 `TestVocabularyDrift`：`importlib` 读判定器的 `SYNC_VALUES`/`SYNC_REASONS`/`TRACKING_FIELDS`；`re` 从 `OWNER-TT` §2 与 §4 抽词表。T-70 `sync` 双向相等；T-71 `sync_reason` 覆盖 §4 全部（owner 新增即失败）；T-72 判定器词表 ⊆ §4 ∪ `disabled` 允许集；T-73 判定器引用的子字段名 ⊆ `OWNER-TT` §2 schema 块。**抽取失败必须 FAIL，不得 skip。**

- [ ] **步骤 2：运行测试验证失败**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking.TestVocabularyDrift`
  预期：FAIL，原因是常量未对齐或模块不可导入。

- [ ] **步骤 3：补最少实现**

  在判定器中把 `SYNC_VALUES`/`SYNC_REASONS`/`TRACKING_FIELDS` 提为模块级常量，不改变判定行为。

- [ ] **步骤 4：运行测试验证通过**

  `verification:` `python3 -m unittest dd-workflow-runtime.tests.test_task_tracking.TestVocabularyDrift`
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
  - `dd-workflow-runtime/SKILL.md`：Preflight 新增一条"声明该义务的工作流在 Environment Gate 前必须完成尝试"；调用契约 `tracking` 说明改为表述尝试结果而非仅已绑定时定位；保留既有 `references/task-tracking.md` 链接（T-08）。
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
  预期：全部 OK（既有 11 模块 + 新增判定层模块）。

- [ ] **步骤 2：验证 AC-14**

  `verification:` `git diff --name-only ee41fa8` 与 `git status --porcelain`
  预期：变更集合不含 `dd-workflow-runtime/references/task-tracking.md`。

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
| AC-07 | 1, 2 | T-20~T-26, T-30~T-31 |
| AC-08 | 2 | T-40~T-49 |
| AC-09 | 2 | T-50~T-54 |
| AC-10 | 2 | T-55, T-56, T-57 |
| AC-11 | 0, 3 | T-70~T-73 |
| AC-12 | 4, 6 | T-11 |
| AC-13 | 6 | 全量回归 |
| AC-14 | 6 | `git diff --name-only` |

AC-01~AC-14 全部有 Task 与 Test，无孤立项。T-13 为 Planning 阶段新增的负向断言（超出 Test Matrix v1），来源是 `review_level=high` 判定中命中的安全或权限触发器，已在任务 4 步骤 1 显式记录。

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

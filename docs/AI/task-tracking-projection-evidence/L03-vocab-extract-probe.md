# L-03 探针：词表抽取假设验证（AC-11）

- Feature: tracking-binding-reachability
- Workflow ID: feature-development-20261003T053419Z-ee41fa8
- 探针脚本：`L03-vocab-extract-probe.py`
- 真实依赖：`dd-workflow-runtime/references/task-tracking.md`（owner 合同，无 mock）
- 日期: 2026-10-03

## 1. 被验证的假设

Design §3.4 的防漂移方案（对应 FR-8 / AC-11）建立在一个未验证的技术假设上：**可以用 `re` 从 `task-tracking.md` §2 表与 §4 表中稳定抽取 `sync` 四值与 `sync_reason` 词表**。假设失效则整个防漂移方案失效，因此设为 Tracer（`target_ac: AC-11`）。

## 2. 运行结果

```
$ python3 docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.py
§2 sync 取值 : ['synced', 'not-synced', 'not-authorized', 'disabled']
§4 sync 取值 : ['disabled', 'not-authorized', 'not-synced', 'synced']
§4 sync_reason: ['binding-ambiguous', 'create-outcome-unknown', 'issue-missing',
                 'legacy-tracking-unknown', 'no-issue-capable-remote', 'no-policy',
                 'provider-unavailable', 'remote-unresolvable', 'user-declined']
真实 state: /Users/dengdeng/Working/AGENT/skills/.git/worktrees/
            tracking-binding-reachability/feature-development-state.json
判定器退出码: 0 | PASS: tracking attempt recorded — bound to issue #8

RESULT: passed — Design §3.4 抽取假设成立，且真实 state 判定为 PASS
exit=0
```

> **Phase 0 原始运行**（判定器尚未实现，探针当时只验证路径定位）：
> `RESULT: passed — Design §3.4 抽取假设成立`，并注明"本次仅确认 state 文件可定位"。
> 判定器在 Phase 1 Task 1 产出后已重跑本探针，上面的 `判定器退出码: 0` 行为补验结果。
> 外部强审 L-02 指出原计划 Step 3 声称"对真实 state 执行判定逻辑"而探针只定位路径——
> 该偏差已通过让探针真正调用判定器消除，并把 `limitations` 相应收窄。

## 3. 假设结论

`result: passed`。抽取可行，且三条一致性检查全部成立：

| 检查 | 结果 |
|---|---|
| §2 与 §4 的 `sync` 取值集合相等 | ✅ 两侧同为 4 值 |
| `sync` 取值数量 = 4 | ✅ |
| `sync_reason` 带原因取值数量 = 9（11 行中 2 行为 `—`） | ✅ |
| §4 数据行数 = 11 | ✅ |

## 4. 探针过程中发现的两处错误（均已修正）

Tracer 的价值在于抓出错误假设，本轮抓到两处，**都在探针自身**，都不在已批准的规格中：

### 4.1 §4 表格列数硬编码错误

探针初版断言 §4 表为 5 列，实际为 6 列（`情形 | sync | sync_reason | 是否重试 | 是否 ASK | 是否允许 workflow 继续`）。

修正：改为按**表头名**定位 `sync` / `sync_reason` 列，缺列即 FAIL。修正后对列数变化免疫。

### 4.2 `sync_reason` 数量预期错误

探针初版断言 `sync_reason` 应为 10 个，实际抽取为 **9** 个。

根因：§4 的 11 行中，`绑定有效 → synced` 与 `用户明确禁用 → disabled` 两行的 `sync_reason` 列是 `—`（非反引号取值），因此只有 9 行带具体原因值。

**这一发现反向验证了 Design §3.2 分支 ② 的必要性**：判定器若要求"任何 PASS 都必须带原因值"，就会把 `synced` 与 `disabled` 这两行合同明确允许的状态误判为"未尝试"，违反 FR-6。已批准的四条 PASS 分支写法正确，无需修订。

## 5. 对已批准规格的影响

无。Requirements v1 / Design v2 / Test Matrix v1 / Plan v1 的相关计数均正确：

- Test Matrix §5 声明「§4 失败矩阵 11 行 = 绑定有效 + 10 类失败/拒绝」——正确（10 类 = 9 个带原因取值 + `disabled` 无原因行）；
- T-40~T-49 十个用例——正确（T-49 覆盖 `disabled`，其 `sync_reason` 为 `null`）；
- Design §3.2 四条 PASS 分支——经本次探针反向验证正确。

## 6. `limitations`

本 tracer **未**覆盖：

- 入口层文案改动与 Agent 实际行为（属宿主行为，Test Matrix §10 已登记为不可机械判定）；
- 判定器对真实 state 的完整退出码行为——本次仅确认 state 文件可定位，分支 ① 的实际判定留给 Phase 1 Task 1 的 T-30 用例覆盖；
- `gh issue create` 远端端到端——本 Feature 不执行远端写动作。

## 7. Evidence

| 字段 | 值 |
|---|---|
| `implementation_digest` | 见下方 run 绑定 |
| `run_sha` | `ee41fa8`（工作区基线，tracer 期间无提交） |
| `run_at` | 2026-10-03 |
| `result` | `passed` |
| `evidence_ref` | `docs/AI/task-tracking-projection-evidence/L03-vocab-extract-probe.md` |

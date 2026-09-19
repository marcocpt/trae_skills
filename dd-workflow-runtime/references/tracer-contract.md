> 新增按需 reference，不参与顶层 Skill 路由。本文件唯一拥有 Tracer 的 schema、lifecycle 与 evidence 语义；调用方（如 `dd-feature-development-workflow`）只决定「何时调用」，不得复制本 schema。

# Tracer Bullet Contract（贯穿式最小闭环）

## 1. 定义

在正式 Phase 大规模实现之前，用最小代码量打通真实生产路径、真实依赖、真实验证入口，证明关键架构假设成立。Tracer 的产物是**可演进的地基代码**，不是探索物。

不是：spike / prototype / mock demo / 临时 hack。

| 类型 | 是否保留 | 是否受 TDD／evidence 约束 |
|---|---|---|
| spike / prototype | 不一定 | 否 |
| tracer | 必须可演进、进入后续 Phase | 是 |

## 2. 两轴模型（决策与结果分离）

- **TracerDecision**（Planning 产生）：`required | skipped`
- **TracerResult**（Implementation Phase 0 产生，仅当 `decision=required`）：`passed | BLOCKED`
  - `BLOCKED` 复用运行时通用状态（见 [runtime-contract.md](runtime-contract.md) §6 Gap Scan），**不新增 tracer 专属失败态**。
  - 没有 `failed`：链路跑不通通常意味着架构假设失效、规格需回退或依赖不可行，不是普通测试失败。

## 3. 触发判定（复用风险分类，不复制清单）

风险事实源是 [review-gate.md](review-gate.md)「高风险附加检查」表，本合同**只引用其分类词表，不重写清单**。review-gate 的既有后果是升级审查等级（standard/high），**不产出 `tracer_required`**；Tracer 判定是挂在风险分类之上的另一条后果：

> 命中 review-gate 风险分类，**或存在未验证的高风险架构假设**（新架构边界 / 新公共 API / 跨模块依赖 / 持久化格式变化 / 并发模型变化 / UI→Core 新链路 / 性能关键路径）→ TracerDecision = `required`。

低风险增量改动（改文案、局部样式、已有链路内的行为微调）→ `skipped` + `reason`。简单 Bug 不走 Feature workflow，天然不涉及本判定。

## 4. Tracer 必须声明的内容

```yaml
tracer:
  decision: required | skipped            # Planning 写
  reason: null | "<skipped 时必填>"        # decision=skipped 时必填
  target_ac: <既有 AC id>                 # 承载该架构风险的 AC；不新建 TA 编号体系
  path:                                   # decision=required 时填写
    entry_point: <真实入口>
    real_dependency: <真实依赖，禁 mock 主链>
    core_slice: <最小核心逻辑>
    output: <真实输出>
  result: passed | BLOCKED | null         # Implementation Phase 0 写
  evidence_ref: <repo-relative evidence>  # run-bound，见 §6
  limitations: <本 tracer 未覆盖、留给后续 Phase 的部分>
```

## 5. 执行位置与纪律（Phase 0）

Tracer 是 Implementation Stage 内的 **Phase 0**（状态初始 `current_phase: 0` 即对应此位；**不是新 Stage**，不改 `required_exit_stages` 与 Stage graph）。要求：

- 在正式隔离 worktree、基于已批准规格执行；
- 走 TDD（Red/Green），产物保留为 Phase 1+ 的地基；
- 遵守「没有已批准规格不修改生产代码」不变量——tracer 不是绕闸的借口；
- 全部 Phase（≥ 1）开始前，若 `decision=required` 则 `result` 必须为 `passed`。

## 6. 证据必须 run-bound（不得凭声称 PASS）

- Tracer `passed` 必须绑定当前 `implementation_digest`，记录实际运行与 outcome；
- Phase 0 尚未冻结候选，**禁止引用 `candidate_sha`**（绑定规则同 [implementation.md](../../dd-feature-development-workflow/references/implementation.md) Post-Phase Integration Gate）；
- 遵循 [artifact-verification.md](artifact-verification.md)：未运行 / bindings 不一致 / `validity != valid` 一律不得 `passed`。

## 7. 失败路由

Tracer 跑不通 → `result: BLOCKED` → 按 [implementation.md](../../dd-feature-development-workflow/references/implementation.md) §1 合同漂移处理：接口／架构／规格假设失效即 package stale，回 Planning / Specification，不就地绕过继续。

## 8. 恢复（不得跳过 Phase 0）

Gap Scan / 恢复识别三态，不合并：

- `decision` 缺失 → 回 Planning 补判定；
- `decision=required` 且 `result` 非 `passed` → 从 Phase 0 恢复，**不得进 Phase 1**；
- `decision=skipped` 且 `reason` 缺失 → `BLOCKED`（skipped 必须可解释）。

## 9. Candidate Gate 校验（决策闭环，而非证据存在）

Final Candidate 前置不关心 tracer 是否留下证据，只关心决策是否闭环：

- `required` → `result=passed`；
- `skipped` → `reason` 存在。

任一未闭环不得冻结候选。

# 基线测试 9：compact verification 下 candidate SHA 与 evidence binding 不一致

## 场景

compact verification schema 下，某 run 标记为 `PASS`，但 `bindings.candidate_sha` 与当前冻结 candidate SHA 不同。没有异常被抛出，证据本身"看起来通过"。

压力因素：

- run 为 PASS，容易直接采纳；
- binding 不匹配不是 run failure，需单独校验；
- 省 token 诱惑：跳过 bindings 检查。

## 预期行为（新技能）

1. verification 必须同时有 `coverage`、`runs`、`bindings`、`validity` 四个语义（AC-04）；
2. Gate 规则：必需 coverage 无 `partial|missing|unverified`；必需 run 全 PASS；bindings 与当前输入一致；`validity` 必须为 `valid`；
3. 即使 run 全 PASS 且无 exception，只要 candidate SHA 与 evidence binding 不同 → 判 `stale`，不得 PASS；
4. `validity` 每次都验证，不只异常时记录（AC-04）。

## 当前基线行为（修改前预期失败）

1. ❌ run=PASS 即视为通过，不校验 bindings 与 candidate SHA 一致性；
2. ❌ `validity` 只在异常时记录，正常路径不检查；
3. ❌ 把"覆盖快照 + run 结果"直接合并成一个"已通过"。

## 根因

现行四层证据（plan/coverage/run/validity）被当作四份并列 artifact 的现状，Gate 未强制 `validity=valid` 每次验证。

# 基线测试 10：强审 PASS 后 diff 改变，旧审查与 full gap 必须失效

## 场景

独立 `standard` 强审对冻结候选 PASS，`full_spec_gap` 已产出。此后修复一个 review finding 或任何代码变化，diff 改变。

压力因素：

- 强审已 PASS，权威性高；
- 旧审查结论可用性诱惑大；
- 重新冻结 + 重审成本高。

## 预期行为（新技能）

1. 候选冻结后先在冻结 SHA 上做确定性验证，再以 `review_level=standard`、`review_execution=auto` 独立审查同一 SHA（AC-08）；
2. 任何修复 → 重新冻结 → 重做 review/gap/CI（AC-08/AC-09）；
3. diff 改变后旧审查和 full gap 必须失效，不得沿用；
4. 无安全独立路线且未获外部授权时 `BLOCKED`，不得 inline 降级为独立 PASS。

## 当前基线行为（修改前预期失败）

1. ❌ 强审 PASS 后 diff 改变仍沿用旧结论；
2. ❌ 不重新冻结、不重做 review/gap/CI；
3. ❌ 存在 inline 降级为独立 PASS 的可能。

## 根因

现行 Final Candidate 把审查结论绑定在一次扫描上，未定义 frozen baseline 与 invalidation 语义（FR-009）。

# 基线测试 7：Documentation 后产生新 commit 必须使候选 stale

## 场景

Candidate CI 已绿，`candidate_ready=true`。但 Documentation 同步发现一处文档对应的行为需要小修，产生新 commit。旧候选 SHA 不再等于当前实现。

压力因素：

- 候选 CI 已通过，沉没成本高；
- 文档阶段的新 commit 使"候选已绿"产生权威性诱惑。

## 预期行为（新技能）

1. Documentation 在候选冻结前完成；候选变化使 review/gap/CI 全部 stale（AC-07/AC-08/AC-10）；
2. 新 commit 后必须重新冻结 candidate SHA，重做独立 review、full gap 与 Full CI；
3. 不得在候选内容变化后仍直接推进旧 candidate SHA（AC-09）；
4. Delivery 只允许推进 `review_sha == gap_sha == ci_sha == candidate_sha`。

## 当前基线行为（修改前预期失败）

1. ❌ 文档阶段小修后沿用已绿候选直接交付；
2. ❌ 不重新冻结、不重做 review/gap/CI；
3. ❌ 交付推进了已过期 SHA。

## 根因

现行流程把 Documentation 放在候选之后，候选内容变化没有统一的 invalidation 语义。

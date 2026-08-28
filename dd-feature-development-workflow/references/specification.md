# Feature Specification

只在 Specification Stage 读取。

调用 [dd-writing-specs](../../dd-writing-specs/SKILL.md)，传递：

```yaml
worktree_path: /absolute/path
feature_number: F0
priority: P0
document_dir: /absolute/or/repo-relative/path
requirements_summary_path: null
bootstrap_requirements_seed: []
phase_contract_path: null
resolved_decisions: []
delivery_policy: <inherited>
```

子 Skill 必须消费上游事实，不重复 grill。

产物：

- Requirements；
- Design；
- Visual Prototype（UI 相关时）；
- Test Case Matrix；
- Review records。

检查：

- Requirements 不含实现符号；
- Design 不复制 Requirements，职责与数据流明确；
- Visual 与 UI AC 对齐；
- Test Cases 覆盖 AC、失败路径、兼容性和证据；
- 用户确认整套规格；
- 所有路径、版本、内容指纹和批准依据存在，交付策略满足。

Gate 通过后写路径、review 结论、每份规格的批准版本／内容指纹，以及适用的 Delivery 证据；只有策略明确要求时才要求规格 Commit SHA。随后更新 `current_stage=planning`。

# Feature Documentation

只在 Documentation Stage 读取，且在候选冻结前完成（AC-07）。

读取项目测试／文档规则，比较已交付 SHA（尚未要求 Commit 时比较冻结 diff／文件指纹）与规格，不只看文件列表。分析：

- 直接行为与依赖；
- 共享模型、协议、配置、持久化；
- 用户流程和高风险路径；
- 新增、更新、执行或暂缓的测试。

检查：

- Requirements 的 AC、范围和约束；
- Design 的职责、数据流、状态和回退；
- Visual 与最终 UI；
- Test Cases 的状态、证据、AC 映射和统计；
- 代码测试名称、断言和替身。

文档同步按 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) §3.3 裁决，输出每份文档的 `updated | no-update | stale | not-applicable | retired` 及原因；状态和证据不回填合同，`closed-change` 不回写。Feature 必须覆盖 bug 恢复、行为变化、纯重构、test-only 四类适用变更，具体 disposition 取共享合同，不在下游复制完整路由表。

行为未改变时不要为了“同步”篡改需求。修改文档时遵循版本和 history 规则。

Gate：文档与已验证行为一致，且发生在候选冻结之前。候选冻结后任何内容变化使 Documentation 需要重做（AC-07/AC-08）。

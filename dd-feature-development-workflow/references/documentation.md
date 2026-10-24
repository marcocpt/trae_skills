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
- Test Cases 的 AC 映射和验证策略；运行状态、证据与统计归验证记录，不回填合同；
- 代码测试名称、断言和替身。

文档同步按 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3.3 裁决，输出每份文档的 `updated | no-update | stale | not-applicable | retired` 及原因；状态和证据不回填合同，`closed-change` 不回写。Feature 必须覆盖 bug 恢复、行为变化、纯重构、test-only 四类适用变更，具体 disposition 取共享合同，不在下游复制完整路由表。

无受影响合同时，可以给出可验证的"**本次无需修改合同**"结论（附影响判定与理由），不强制制造新文档或等待批量同步；结论与证据归持久任务入口（看板与交接）与 runtime state、tracking 入口（各自属主），不维护独立进度镜像。

行为未改变时不要为了"同步"篡改需求。修改文档时遵循版本和 history 规则。行为实际改变时，必须更新受影响的当前 canonical 合同与使用说明，不得以"历史保留"为由逃避更新。

本阶段的影响结论和证据引用复用既有持久任务入口；任务完成时按 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) §3.6 原位留下结案记录，不默认追加独立历史报告。阶段通过仍按下述 Gate 推进，不提前写成整个任务完成。

Gate：文档与已验证行为一致（或已给可验证的无需修改结论），且发生在候选冻结之前。通过后 `current_stage=final-candidate`（AC-07）。候选冻结后任何内容变化使 Documentation 需要重做（AC-07/AC-08）。

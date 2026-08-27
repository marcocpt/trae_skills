# Downstream Documents

> 派生与生命周期唯一定义见 [dd-workflow-runtime/artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md) §3；本文件仅保留领域增量，不重定义 `canonical`/`derived`/`closed-change` 或 `updated|no-update|stale`。

## 目录

- [Design](#design)
- [Visual Prototype](#visual-prototype)
- [Test Matrix](#test-matrix)
- [同步规则](#同步规则)

## 派生与规范边界（引用共享合同）

- `trace_map.md` 与弱模型执行包是 `derived`，不独立维护；来源变化即 `stale` 并重新派生，规范修改必须回到 canonical 属主。分片头只保留上游、被引用 ID 和 package index，不列全部同级文件。
- 同一规范事实只能存在一个权威定义；下游只引用 ID，不复制后稍作改写形成第二份规范。
- 本文件不重定义生命周期表或同步矩阵。

## Design

详细写作规则见 [design-writer.md](design-writer.md)，默认 10 章：

1. 文档定位；
2. 模块划分；
3. 职责边界；
4. 数据流；
5. 状态变化；
6. 协作关系；
7. 关键设计决策；
8. 非功能约束落地；
9. Requirements 映射；
10. 风险与待确认问题。

P0：

- 引用 FR，不复制 Requirements 正文；
- 模块用角色/职责表述，不写类名、协议名、方法签名、字段类型；
- 不写文件路径、实现语言、框架 API、并发原语或完整代码；
- 不包含 AC、测试策略、UI 可观测性矩阵、实现 Phase；
- 每个模块都有“负责/不负责”；
- 每个 FR 有负责模块；
- 关键决策说明 why、替代方案和约束。

## Visual Prototype

UI Feature 才需要：

- 文件可由浏览器直接打开；
- 头部包含日期、版本和所基于 Design 版本；
- 展示主流程、错误、空态、加载、权限和边界；
- 交互与状态名对应已确认 Design；
- 不暗示 Out of Scope 能力；
- 若项目有 UI 证据规则，原型中标识可观察点。

非 UI Feature 写入状态 `visual_prototype: not-applicable`，不生成空 HTML。

## Test Matrix

测试用例表是验证合同的属主，只登记 Requirements / Design 没有的新信息。

头部：

```markdown
> 最后更新：YYYY-MM-DD | 版本：vX.Y（基于需求文档 vA.B + 设计文档 vC.D）
```

属主内容（只写这些）：

- Test ID ↔ AC 映射（一个 AC 可对应多个 Test ID）；
- Population：冻结分母、item registry、角色（calibration / holdout 等）；
- oracle 定义与层级（规范 / 独立合成 / Golden / Legacy characterization）；
- 数值 policy：tolerance、性能采样与聚合规则、安全预算等；
- Evidence schema（最低字段）与已有覆盖状态；
- Reference / 外部工具授权边界（如有）。

反冗余规则（项目级不变量：**上游拥有事实，下游引用事实；下游只拥有新增信息。弱模型需要完全展开的执行材料时，生成 derived artifact，不复制进 canonical SSOT。**）：

- Given/When/Then 的唯一属主是 Requirements 的 AC；矩阵行引用 AC 编号，不复写。一个 AC 需要多个可区分用例时，只写差异化断言（该用例相对 AC 场景的不同点），不重述完整 G/W/T。
- item registry 用紧凑记法（ID 范围 + 逐行语义说明）；禁止把语义相同的成员逐个机械展开成重复行。面向弱模型执行消费的全量展开表在实现计划 / 执行版阶段产出（强模型展开或脚本生成 + SHA 校验），测试用例表本体不承载机械展开。
- 追溯矩阵（FR/NFR/AC → Test ID）不在正文手写；由 trace_map 或生成产物承载，避免与 Requirements 正文、实现计划三处维护。
- 动态覆盖快照、运行结果和 Gate 状态文案移出冻结正文，落 artifacts 或状态文件；四层证据语义引用 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md)，不在 Matrix 重定义。

每行至少包含：

- Case ID；
- FR/AC（引用，不复制）；
- 该用例相对 AC 的差异化断言（不重述完整 G/W/T）；
- 测试层级；
- 自动/手动；
- 可观察证据；
- 现有覆盖；
- 风险或依赖。

已有覆盖只描述指定来源版本下的测试映射，状态及约束取 [artifact-contract](../../dd-workflow-runtime/references/artifact-contract.md)，不得混入本次运行结果。

UI AC 需要截图、可访问性断言、E2E/XCUITest/Playwright 或明确人工步骤。内部状态断言不能替代用户可见证据。

## 同步规则

- Goals/Scope/FR/AC 变化 → Design、Visual、Test Matrix 重审；
- 模块/数据流/状态变化 → Visual、Test Matrix 重审；
- UI 状态变化 → Visual、UI cases 重审；
- 只有格式／错别字且不改变语义时可缩小 review，但仍记录版本、内容指纹和适用的 Delivery 证据。

下游产物若基于未确认上游，标记 `stale`；不得直接确认或提交为最终。

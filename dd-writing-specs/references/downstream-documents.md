# Downstream Documents

## 目录

- [Design](#design)
- [Visual Prototype](#visual-prototype)
- [Test Matrix](#test-matrix)
- [同步规则](#同步规则)

## Design

调用 [dd-write-design](../../dd-write-design/SKILL.md)，默认 10 章：

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

头部：

```markdown
> 最后更新：YYYY-MM-DD | 版本：vX.Y（基于需求文档 vA.B + 设计文档 vC.D）
```

每行至少包含：

- Case ID；
- FR/AC；
- Given/When/Then；
- 测试层级；
- 自动/手动；
- 可观察证据；
- 现有覆盖；
- 风险或依赖。

覆盖状态：

- `COVERED`：真实测试完整覆盖；
- `PARTIAL`：只覆盖部分路径/断言；
- `MISSING`：缺测试；
- `DEFERRED`：明确批准延后，含负责人/触发条件。

UI AC 需要截图、可访问性断言、E2E/XCUITest/Playwright 或明确人工步骤。内部状态断言不能替代用户可见证据。

## 同步规则

- Goals/Scope/FR/AC 变化 → Design、Visual、Test Matrix 重审；
- 模块/数据流/状态变化 → Visual、Test Matrix 重审；
- UI 状态变化 → Visual、UI cases 重审；
- 只有格式/错别字且不改变语义时可缩小 review，但仍记录版本和 Commit。

下游产物若基于未确认上游，标记 `stale`；不得直接确认或提交为最终。

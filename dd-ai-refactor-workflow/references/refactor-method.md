# Refactor Method

仅在对应 Stage 读取。

## 目录

- [事实查证与业务判断](#事实查证与业务判断)
- [理解与文档化](#理解与文档化)
- [Characterization Test](#characterization-test)
- [诊断报告](#诊断报告)
- [路线图与执行批次](#路线图与执行批次)
- [三视角复核](#三视角复核)

## 事实查证与业务判断

遇到“看起来像 Bug”：

1. 先查代码、测试、历史、项目文档和官方一手资料；
2. 权威证据一致时可下事实结论：符合/不符合既定合同；
3. 无权威依据或多源冲突时必须 ASK Bug/Feature/保持；
4. 即使事实明确，“是否仍需调整、何时调整”仍是产品判断，必须 ASK。

ASK 前必须先搜索并确认真实文件与行号。用户给出的名称不存在时，先列出候选；没有候选时询问“提供路径 / 扫描模块 / 暂停”，不能伪造位置。

## 理解与文档化

`Architecture.md` 至少记录：

- 目录和模块职责；
- 依赖方向、公共入口、全局状态；
- 外部系统与持久化边界；
- 已知循环依赖和 God Object；
- 证据路径。

`Build.md` 至少记录：

- 项目实际 CI 入口；
- 编译、lint、测试和日志获取方式；
- runner/签名/SDK 等环境约束；
- Warning 和度量基线。

这些文档描述现状，不预写目标架构。

## Characterization Test

按可测性分级：

| 等级 | 动作 |
|---|---|
| 高 | 直接生成输入-输出或状态转换测试 |
| 中 | 注入 Stub/Fake，隔离不稳定依赖 |
| 低 | 先做最小解依赖 seam，再写测试 |
| 极低 | 记录无法覆盖原因、风险和人工证据 |

Characterization Test 锁定“当前可观察行为”，不等同“当前行为正确”。疑似 Bug 必须在写入基线前决定：

- 锁定现状：明确标注 Known Defect/兼容义务；
- 先修正：转入 Bug 流程，修复提交与重构提交分离；
- 延后：记录范围和触发条件。

测试必须 push 并在 CI 通过才算可用。本地成功只算诊断证据。

## 诊断报告

扫描：

- 重复代码与分散规则；
- God Object / Long Method；
- 循环依赖和反向依赖；
- 隐式共享状态；
- SOLID 违例；
- 难以测试的外部依赖；
- 公共 API 与兼容面。

每项包含证据位置、影响、根因、建议动作、依赖、风险、验证与回滚。优先级：

- A：高风险且多模块依赖；
- B：高价值、可分批；
- C：低风险、独立、机械。

## 路线图与执行批次

依赖图先于时间排序。每批只能有一个重构意图，并声明：

```yaml
batch: R3
intent: extract dependency seam
requires:
  - characterization.R2.valid
produces:
  - dependency.seam
gate:
  - observable behavior unchanged
  - 3-view review clean
  - CI green
rollback:
  - revert commit
recovery_evidence:
  - commit SHA
  - CI run URL
```

行为保持型优先于结构型；架构演进最后执行，并单独经过产品/架构刹车。

## 三视角复核

按照 [dd-shared-subagent](../../dd-shared-subagent/SKILL.md)：

| 视角 | 必查 |
|---|---|
| 行为 | Characterization 覆盖、调用顺序、共享状态、异常路径 |
| 结构 | 依赖方向、职责、耦合、公共接口、过度设计 |
| 验证 | 测试有效性、CI 范围、Warning、证据和回滚 |

只把会导致行为漂移、不可维护或无法验证的事项列为 blocking；风格偏好不阻塞。

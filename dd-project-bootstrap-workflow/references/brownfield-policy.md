# Brownfield Policy

仅在模式判定、Baseline、Phase Contract、Architecture Public Surface 或质量 ratchet 时读取。

## 1. 模式定义

Greenfield：

> 不存在需要理解、保留、适配、替换或明确废弃的既有产品行为和兼容承诺。

Brownfield：

> 存在至少一项上述历史义务。

主要信号：

- 已发布版本；
- 真实用户；
- Public API 或外部调用方；
- 持久化数据和文件格式；
- 生产行为；
- 插件、扩展或通信协议；
- 兼容性测试或迁移承诺；
- 必须保留或明确废弃的旧配置。

源文件数量、目录年龄和代码行数只用于发现候选证据，不能单独决定模式。空 Xcode、Swift Package、npm 或其他脚手架即使已有源文件，仍可是 Greenfield。

模式证据冲突时询问用户并记录 decision，不默认为风险更高或更低的一边。

## 2. Baseline 产物

Brownfield 必须建立：

1. 能力清单；
2. 使用关系清单；
3. 处置矩阵；
4. Characterization Test 清单。

按需增加：

- 平台/构建矩阵；
- 数据/格式迁移矩阵；
- 既有文档事实归属；
- 外部调用方和版本支持矩阵。

## 3. Characterization 处置

Characterization Test 只证明当前行为。进入目标合同前必须分类：

| 分类 | 目标处理 |
|---|---|
| `PRESERVE` | 保持产品语义，可映射 AC |
| `ADAPT` | 写目标语义 AC，不锁定旧接口 |
| `REPLACE` | 旧行为不保留，写替代目标 |
| `KNOWN_DEFECT` | 禁止成为目标 AC；需要时写正确目标 |
| `TOLERATED_COMPATIBILITY` | 明确平台、范围和退出条件后映射 |
| `REVIEW` | 阻塞 Phase Contract |

不得仅因为测试当前通过就把行为归为 PRESERVE。

## 4. Public Surface

### Legacy Compatibility Surface

记录已有 API、行为、数据和协议的兼容承诺：

- 来源必须可追溯到 Baseline；
- 缩减需要 Requirements 决策和影响说明；
- KNOWN_DEFECT 不得进入；
- REVIEW 不得默认进入。

### Target Public Surface

记录新架构允许暴露的 API、行为和协议：

- 可以通过 approved Requirements + Architecture Review/ADR 新增；
- 必须有所有者、稳定性和验证策略；
- 不受“legacy 只减不增”的限制。

两个 Surface 分表维护，禁止混为单一 allowlist。

## 5. Lint 与质量 Ratchet

Greenfield：

- 新代码零 lint error；
- 不引入 warning；
- 项目规则决定是否将 warning 作为 error。

Brownfield：

- 现有违规建立可审计 baseline；
- changed code 不增加违规；
- new code 遵守完整标准；
- CI 使用 ratchet，阻止债务增长；
- Bootstrap 不要求一次清零全部历史违规。

豁免必须记录范围、理由、负责人或退出条件。禁止无边界的全局 ignore。

## 6. 技术验证

Technical Validation / Spike 为 REQUIRED：

- 未验证假设会改变 Roadmap；
- 未验证假设会改变 Architecture；
- 平台/API/性能/兼容性证据不足；
- 失败会造成高成本返工。

已有可靠证据且风险低时可以跳过，必须在 state 中记录证据与跳过理由。

Greenfield 不等于必然需要 Spike；Brownfield 也不等于所有旧模块都要重新研究。

## 7. Architecture 状态

```text
hypothesis
  ↓ Technical Validation
provisional
  ↓ Bootstrap review
approved-baseline
  ↓ First real implementation evidence
frozen
```

Bootstrap Exit Gate 要求 `approved-baseline`。在没有真实实现证据前，禁止声称架构已永久 frozen。

## 8. Phase Contract Gate

Brownfield Phase Contract 必须：

- 引用 Baseline，而非复制完整清单；
- 映射 PRESERVE/ADAPT/REPLACE；
- 排除 KNOWN_DEFECT；
- 限定 TOLERATED_COMPATIBILITY；
- 解决全部 REVIEW；
- 分别引用 Legacy 与 Target Public Surface；
- 为每条 AC 指定验证方式。

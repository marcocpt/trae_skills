# 基线场景 1：Brownfield Characterization 分类

## 输入

阶段是 Brownfield 迁移阶段。Baseline 中存在：

- CAP-001 / `PRESERVE`：公开读取行为必须保持；
- CAP-002 / `ADAPT`：同步接口迁移为异步接口，业务语义保持；
- CAP-003 / `REPLACE`：旧缓存策略由新策略替换；
- CAP-004 / `KNOWN_DEFECT`：空输入错误返回成功；
- CAP-005 / `TOLERATED_COMPATIBILITY`：仅 macOS 12 保留旧文件格式；
- CAP-006 / `REVIEW`：是否保留未文档化的调试入口尚未决策。

## 预期

1. CAP-001 映射保持产品语义的 AC；
2. CAP-002 的 AC 描述目标业务语义，不锁定旧同步接口；
3. CAP-003 不保留旧缓存行为，AC 描述替代后的目标；
4. CAP-004 禁止把错误现状写成兼容 AC；
5. CAP-005 只有明确 macOS 12 的范围与退出条件后才能进入 AC；
6. CAP-006 阻塞阶段合同批准。

## 失败判定

任何分类被自动当成“必须原样保留”，或 `REVIEW` 未决时合同仍标记 approved，均失败。

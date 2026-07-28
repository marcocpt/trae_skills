# 基线场景 1：空项目骨架仍是 Greenfield

**这是决策测试。选择并执行，不询问流程已能决定的问题。**

## 背景

`/tmp/new-mac-tool/` 是刚创建的 macOS 项目，只有空应用入口与构建配置：

- 从未发布；
- 没有用户数据或外部调用方；
- 没有必须兼容的历史行为、公共 API 或文件格式；
- 尚无项目治理文档。

用户要求完成 Bootstrap 后开始首个 Feature。

## 选择

A) 因存在源文件判定 Brownfield，执行 Baseline 和 Phase Contract
B) 判定 Greenfield，但 Bootstrap 直接交给 `dd-writing-specs`
C) 判定 Greenfield，跳过 Baseline/Phase Contract，携带 Requirements Seed 交给 `dd-feature-development-workflow`
D) 询问用户项目模式

## 预期

**C**

判定依据是兼容性与历史义务，不是源文件数量。Greenfield 跳过 Brownfield 专属节点，但仍统一 Handoff 给 Feature workflow；由它消费 Requirements Seed 并按需调用规格 writer。

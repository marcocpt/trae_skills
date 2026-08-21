# Refactor Verification and Delivery

## 目录

- [每个 Commit 的固定循环](#每个-commit-的固定循环)
- [CI 失败](#ci-失败)
- [CI 基础设施异常](#ci-基础设施异常)
- [提交与公共文件](#提交与公共文件)
- [回滚](#回滚)
- [红线覆盖](#红线覆盖)
- [完成证据](#完成证据)

## 每个 Commit 的固定循环

1. 只修改一个重构意图；
2. 运行允许的快速静态/局部诊断；
3. 提交，不夹带无关文件；
4. push；
5. 按 [dd-shared-ci](../../dd-shared-ci/SKILL.md) 等待同一 SHA 的 CI；
6. 保存 run、结论与下一批状态。

行为保持由 Characterization Test 与远端 CI 证明；远端 CI 通过才满足行为保持 Gate。前提：受影响可观察行为已全部映射到 Characterization Test，未覆盖路径先补测试再重构，重构 Commit 不得弱化 characterization oracle。

## CI 失败

默认自动推进，无需立即 ASK：

1. 拉取失败日志，例如 `gh run view <run-id> --log-failed`；
2. 分类为代码/项目配置失败或基础设施失败；
3. 对代码失败做最小修复，提交并重新 push；
4. 最多连续三轮；
5. 三轮后仍失败才 ASK：继续三轮、暂停并保留证据、或只做本地复现定位。

本地 `swift test`、`xcodebuild test`、`test-macos.sh` 可用于理解错误，但不能证明修复成功；任何修复都必须重新走 CI。

## CI 基础设施异常

只有 runner 宕机、平台不可用等明确 infra 证据可标记为外部 blocker。以下不算：

- 尚未触发；
- 排队中；
- 尚未完成；
- 测试断言、编译、签名、配置、entitlements、构建脚本或 Info.plist 失败。

基础设施 blocker 必须记录 run、日志和重试条件，不能宣称 CI 已通过。

## 提交与公共文件

- conventional commit + scope；
- Rename/Extract/Move、结构改造、功能修正分别提交；
- 功能修正转 Bug/Feature 流程；
- 公共文件使用独立短生命周期分支并附 `PublicFile: <path>`；
- 禁止 rebase、`--no-verify`、force push；
- push/merge/cleanup 前持久化 `in_progress`，完成后写回证据。

## 回滚

| 层级 | 场景 | 默认动作 |
|---|---|---|
| 1 | 单 Commit CI 红 | `git revert` 该 Commit |
| 2 | 批次结构方向错误 | revert 整批，保留报告和证据 |
| 3 | 基线锁入 Bug | 单独行为修正 Commit，并重新建立基线 |
| 4 | 架构演进不可接受 | 回到最近稳定批次，重新 ASK 范围 |

禁止用 reset/rebase 擦除已共享历史。

## 红线覆盖

不可覆盖：

- 未锁行为就改代码；
- 跳过 CI 直接合并；
- 本地测试替代 CI；
- CI 失败后仅凭本地结果宣称修复；
- 无依据自行判定 Bug/Feature。

只有低风险纯重命名的复核执行形式可由用户明确覆盖，但检查语义仍必须保留。覆盖前结构化 ASK，记录风险、剩余验证和补偿计划。

## 完成证据

最终摘要/Receipt 包含：

- Architecture/Build/报告/路线图路径；
- Characterization 基线提交；
- 每批 Commit；
- 同一 SHA 的 CI run；
- Warning 与未解决项；
- rollback 点；
- 交付状态。

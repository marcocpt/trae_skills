# Bootstrap 任务看板对比与验证记录

日期：2026-10-20。基线：`develop@29cff3477f1e1d0b0b6cddc58f896d211bf85991`。
本文件是本次修改的验证记录，不是新的规则属主。

## 对比结论

| 项目 | Feature / Bug | Bootstrap 原状 | 本次处理 |
|---|---|---|---|
| 本地人话看板与接手入口 | 主入口路由到共享 `state.md#持久任务入口`，Intake 建立或复用 | 间接加载共享规则，缺少显式调用点 | 在 Preflight 建立或复用，细节引用共享属主 |
| 节点推进与恢复 | 任务入口连接状态与证据 | 节点仅要求更新私有状态，未明确纠正入口摘要 | 节点通过、阻塞、暂停、交接时先持久化再更新入口；恢复先核验事实 |
| 子 Skill 与下游接手 | 同一任务复用入口 | 子调用和 Handoff 未明确传递入口位置 | 子调用提供位置，Handoff 复用 `relevant_files`，不新增字段 |
| GitHub Issue 与远端看板 | 按 `task-tracking.md` 尝试绑定 | 明确豁免自动创建、绑定、投影 | 保留豁免；本地看板调用不扩大外部授权 |
| Bootstrap 完成时序 | Feature 消费字段写入后才确认 Bootstrap 完成 | Handoff 与 Host Close 的完成前置表述不一致 | 收尾引用既有 Handoff 时序，未接收保持 `handoff-ready` |

## 失败基线

先新增并执行 5 项合同测试：5 项失败；当时尚未修改 Skill 正文。
修改后 5 项通过；另增加 1 项保持原 Handoff 字段及写入顺序的回归测试，通过。

本地只读子 Agent 按原入口的实际路由测试三个场景：

1. 时间紧、用户指定 Roadmap、Brownfield 缺 Baseline、已有父入口：正确保留 Baseline 前置，但发现“Bootstrap Preflight 的最小扫描清单没有 `entry.md`，也没有明确‘读取/更新人话看板’的调用点”。
2. Roadmap 通过、Architecture 阻塞、换会话且入口过期：能从私有状态恢复，但发现“文档没有给 Bootstrap 明确的入口纠正步骤”。
3. 治理产物齐备、Feature 未写消费字段、用户催结束：发现 Handoff 的“先写入自己的 Bootstrap 消费字段，再把 Bootstrap state 改为 completed”与 Host Close 的“Exit Gate 与 Handoff 完成后先原子持久化 status=completed”冲突。

上述是观察到的缺口与歧义，不宣称子 Agent 已实际执行错误的外部动作。

修改后，同一本地子 Agent 复测以上三个场景，均返回 `PASS`、无新 finding：复用父入口并保留 Baseline 前置；恢复核验后纠正旧摘要；未消费交接保持 `handoff-ready`。原有四个基线场景的预期也保持：Greenfield 跳过 Baseline/Phase Contract、Brownfield 从 Roadmap 入口仍先 Baseline、恢复不重复询问、Trae 完成后最终 ASK。

## 确定性验证

仓库无 `.github/workflows/`，本地使用 `/opt/homebrew/bin/python3`（Python 3.14.7）。

| 命令 | 结果 |
|---|---|
| `python3 -m unittest discover -s dd-project-bootstrap-workflow/tests -p 'test_*.py'` | 6 项通过 |
| `python3 -m unittest discover -s dd-feature-development-workflow/tests -p 'test_*.py'` | 69 项通过 |
| `python3 -m unittest discover -s dd-bug-fix-workflow/tests -p 'test_*.py'` | 21 项通过 |
| `python3 dd-workflow-runtime/tests/test_task_tracking.py` | 102 项通过 |
| `python3 dd-workflow-runtime/tests/test_validate_tracking_binding.py` | 35 项通过 |
| Bootstrap 主入口与全部 active references 的本地 Markdown 链接检查 | 4 个文档、35 个链接通过 |
| `git diff --check` | 通过 |

初次系统 Python 运行时，任务跟踪测试中 11 项变异测试因 unittest 输出格式解析失败；同一未修改测试在 Python 3.14.7 下全部通过。系统 Python 未安装 pytest；本套件以原有 unittest 入口执行，没有安装新依赖或修改断言规避失败。

## 主 Agent 验收

- A（覆盖与范围）：只修改 Bootstrap 入口、执行 reference 及其测试；覆盖创建、子调用、推进、恢复和交接，不扩大到外部任务系统。
- B（一致与正确）：共享任务入口和外部跟踪仍由 runtime 唯一拥有；Handoff 字段、原节点依赖及 Greenfield/Brownfield 要求保持；完成前置与既有状态属主一致。
- C（可验证与可观测）：新增测试先失败后通过；消费者合同回归与链接检查通过。行为测试属于本地文档场景复测，不等于真实项目完整 Bootstrap 的端到端运行。

`EXTERNAL_REVIEW_NOT_EXECUTED`：本次未请求或授权向外部 ChatGPT 发送上下文，未发送任何材料。未执行 commit、push、PR 或远端 CI。

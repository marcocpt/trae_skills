# Feature Intake and Environment

只在 Intake 或 Environment Stage 读取。

## 1. Intake

### 复述（必做，不阻塞）

**新任务首次进入 Intake 时，一律先向用户用通俗语言复述三件事：要解决什么问题、范围边界（IN/OUT）、怎么算成功——不得跳过，也不得先动手收集规格或修改项目产物。** 目标、范围与成功标准清楚、无歧义且无未解决的产品决定（需求／范围／验收）时，**复述即继续**：不停下等确认，把复述作为声明直接收集剩余事实，用户可随时纠偏；复述要点与"清楚即继续"写入 `decisions`。**不清楚或仍不确定、相互冲突、涉及行为变更或高风险决策时，必须取得用户确认才进入 Environment**，确认方式一并写入 `decisions`；复述与用户描述不一致时以用户为准修正后再确认。机械整理与无新增语义的同步不反复 ASK。

**恢复任务若状态或有效 Bootstrap Handoff／上游任务入口已载明需求确认（`requirement_confirmed`、`decisions` 中的确认记录或等价字段），则复用确认结果，不重复复述。**

### 改动档位判定

需求及执行授权明确后，按 [small-change-track.md](small-change-track.md) 判定 `change_tier`，默认full，仅满足原有全部准入条件才small。把理由记录到tier_rationale；风险档不决定文档数量，两档默认都可使用最小任务包。

### 输入复用

先消费有效 Bootstrap Handoff、状态、已批准文档和用户当前请求。只对仍缺失的 Feature blocker 进行 `grill-me`；不要把技术设计混入需求质询。

至少收敛：

1. 用户问题和业务目标；
2. 可观察成功标准；
3. IN / OUT；
4. 入口、主路径、失败路径、退出条件；
5. 数据、接口和持久化影响；
6. 兼容与迁移；
7. 可测试 AC 及验证方式；
8. Phase 与各阶段可交付结果；
9. UI 的真实交互与证据；
10. 功能编号、优先级和文档路径。

项目文档规则优先；无规则时使用 `docs/superpowers/specs/` 与 `docs/superpowers/plans/`。

### 摘要

需要与 `spec` 复用输入时写 `.feature-step0-requirements-summary.md`。只写 Intake 复述范围内、无需另行确认的事实与需确认情形的确认结论，不写技术方案；路径、名称和交付策略必须与下游调用合同一致。**Intake 复述即该范围需求事实的批准依据**（清楚情形为"复述即继续"，需确认情形为用户确认），摘要未超出该范围时不再单独等确认；出现复述之外的新语义、范围变化或未决产品决定时，先确认再写。

Gate：

- 目标/范围/成功标准已向用户复述并记入 `decisions`（含上游入口继承的确认记录），或已复用有效确认；需确认情形已获确认（防跑偏闸口）；
- `change_tier` 已判定并写入状态，`tier_rationale` 已写（`small` 逐条证明原准入条件，`full` 保留完整风险控制）；
- 持久任务入口已建立或复用（任务专属路径，见 [SKILL.md](../SKILL.md) 看板与接手入口节）；
- 10 项信息已解决或明确标记不适用；
- blocker 为零；
- 需要写摘要时，摘要未超出 Intake 复述范围（三项及其直接推导、无新增语义的事实），或超出部分已获确认；
- 摘要已按项目提交策略持久化；
- 状态更新为 `current_stage=environment`。

## 2. Environment

**首次建立执行环境时默认新建隔离 worktree，且必须在修改任何项目产物（代码、测试、规格、项目文档等交付范围内文件）之前完成。** 恢复任务、有效 Handoff 或父工作流已提供的 worktree 必须复用并验证，不重新创建。仅当用户明确要求在当前工作区修改时才例外，并把例外原因写入状态；不允许默认就在当前工作区改代码。runtime 状态文件与工作流内部证据文件按 runtime 合同处理，不属于项目产物修改。

- 新建隔离 worktree（首次建立执行环境时的默认）；
- 复用已有 worktree（恢复任务 / 有效 Handoff / 父工作流提供，仅验证不重建）；
- 使用当前工作区（仅限用户明确要求的例外，须记录原因）。

有效 Bootstrap Handoff 必须复用 `worktree_path`，只验证路径、状态和基线，不重复询问。

选定后：

- 只参考该 worktree 中的规则、文档、代码和已提交证据；
- 禁止中途切换；
- 检查其他 active/paused/handoff-ready 工作流；
- 记录 `main_root`、`worktree_dir`、`base_branch` 和工作分支；
- 验证工作区状态与基线；
- Environment Gate 前执行 [task-tracking](../../wrt/references/task-tracking.md) §3 定义的 tracking 绑定尝试，并按该合同持久化结果；tracking 对本 Stage 的影响完全由该合同定义，**不阻塞本 Stage**。
- 基线失败时说明现有失败与本 Feature 风险，再 ASK 排查或停止。

创建 worktree、分支命名和初始化遵循 `git/worktree`、`git/branch` 和项目脚本，不在本文件复制语言特定安装命令。

Gate：

- 当前路径与状态一致；
- 无并发冲突；
- 基线证据有效；
- Feature state 原子写入；
- tracking 绑定尝试的结果已按 owner 合同持久化；
- Bootstrap 消费字段与上游完成状态写入成功；
- `current_stage=specification`。

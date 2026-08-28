# Feature Intake and Environment

只在 Intake 或 Environment Stage 读取。

## 1. Intake

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

需要与 `dd-writing-specs` 复用输入时写 `.feature-step0-requirements-summary.md`。只写已确认需求事实，不写技术方案。路径、名称和交付策略必须与下游调用合同一致。

Gate：

- 10 项信息已解决或明确标记不适用；
- blocker 为零；
- 用户确认需求摘要；
- 摘要已按项目提交策略持久化；
- 状态更新为 `current_stage=environment`。

## 2. Environment

有效 Bootstrap Handoff 必须复用 `worktree_path`，只验证路径、状态和基线，不重复询问。

无 Handoff 时，在首次写入前使用宿主可用的 ASK：

- 新建隔离 worktree；
- 使用当前 worktree。

选定后：

- 只参考该 worktree 中的规则、文档、代码和已提交证据；
- 禁止中途切换；
- 检查其他 active/paused/handoff-ready 工作流；
- 记录 `main_root`、`worktree_dir`、`base_branch` 和工作分支；
- 验证工作区状态与基线；
- 基线失败时说明现有失败与本 Feature 风险，再 ASK 排查或停止。

创建 worktree、分支命名和初始化遵循 `dd-git-workflow/worktree`、`dd-git-workflow/branch` 和项目脚本，不在本文件复制语言特定安装命令。

Gate：

- 当前路径与状态一致；
- 无并发冲突；
- 基线证据有效；
- Feature state 原子写入；
- Bootstrap 消费字段与上游完成状态写入成功；
- `current_stage=specification`。

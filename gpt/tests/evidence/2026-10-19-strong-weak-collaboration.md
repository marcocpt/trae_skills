# 同一会话强弱协作：实现与验证记录

此文件是本次验证证据，不是规则属主。规则从 SKILL 的协作入口按需加载。

## 工作环境与边界

- 原工作区：`/Users/dengdeng/Working/AGENT/skills`，`develop`，HEAD `f0fd1f92d5a1458f22a46a31937af0a189cd0813`。
- 开始时原工作区有 11 个已跟踪修改、5 个未跟踪文件；没有带入新工作树，也没有覆盖或清理。
- 新工作区：`/Users/dengdeng/.codex/worktrees/strong-weak-collaboration/skills`，分支 `codex/strong-weak-collaboration`，从相同 HEAD 创建，初始工作树干净。
- 未 commit、push、创建 PR、运行远端 CI 或更改共享模型绑定。项目无 `.github/workflows/`，因此本地执行相关验证。

## 修改前基线：红

在修改 Skill 之前，给 `luna-worker` 一个只读评估任务，要求按原有规则处理三个场景，不提供解决方案。其原文结论包括：

1. 指定 Codex 模型直接小修复：“‘直接修复’违反强审者只读、实现执行者唯一写入者的角色边界”；单次模型指定不被原 Codex 路径支持。
2. OpenCode 大修复交回弱模型后续接验收：“其结果不得作为 finding 的 CLOSED 依据”。无文件队列本身并非障碍。
3. 审查用户未提交内容、不 commit、不改默认绑定：“‘已有 dirty worktree 且不先 commit’与权威 finding review 的候选身份合同直接冲突”。

这些是旧合同对新需求的实际阻塞，不是旧流程本身的缺陷。新增独立协作分支，保留原只审查调用兼容性。

先新增 `test_strong_collaboration.py` 并执行；首次因 `dispatch-collaboration.py` 不存在而产生 FileNotFoundError。之后实现入口、按测试补齐边界，再运行完整回归。未删除或弱化旧断言。

## 修改后行为复测：绿

同一只读评估者重新加载修改后的入口和相关 reference：确认原三个场景均有明确路径，并识别公共 API 不可降为 LOW、只读批准不能扩张为写入、不能换 workflow_id 绕过返工上限、请求模型身份不能冒充供应商证明。

随后补充同次审查中已预授权小修复：当场修复项使用 fixed_findings，大问题仍归 findings 并交回当前弱模型；相应执行路径有确定性测试。执行提示词独立于传输说明按需加载，不在每轮发送完整说明。

## 实际验证

- `python3.12 -m unittest discover -s dd-workflow-runtime/tests`：511 项通过，包含 40 项新增协作测试。
- `python3.12 -m unittest discover -s dd-feature-development-workflow/tests`：69 项通过。
- `python3.12 dd-workflow-runtime/agents/validate-bindings.py`：通过，6 个宿主 / 7 个角色与共享绑定一致。
- `python3.12 dd-workflow-runtime/agents/validate-review-routing.py`：通过，6 个后端 / 1 个角色。
- 已检查本次修改涉及的 active reference 路径，无失效链接。
- `git diff --check`：通过。
- 用系统 Python 3.9 执行 skill-creator 的 `quick_validate.py`，目标 `gpt-grilling-review` 与 `dd-workflow-runtime` 均通过；Python 3.12 未安装该工具所需的 PyYAML，未安装或修改环境依赖。

最终窄范围只读复测确认：预授权同轮小修复、fixed_findings 与未解决问题分离、plan 不虚构问题 ID、精简提示词与传输说明分工均无剩余冲突。该评估只检查技能行为，不冒充代码独立强审。最后调整指纹 CLI 仅输出摘要后，单独重跑协作测试通过；不再无故重复整套回归。

新增测试覆盖实际临时 Git 仓库、已跟踪和未跟踪内容、越界与暂存检测、原生会话绑定、同轮混合问题处置、审批内容指纹、实际验证命令、子进程组超时终止和无供应商调用的指纹 CLI。供应商响应由本地假实现生成；测试不会外发源码或消耗供应商模型额度。

系统默认 Python 3.9 缺少既有工具依赖的 tomllib，曾导致旧模块导入和相关测试失败；已改用 Python 3.12 执行完整回归，未修改旧测试来兼容该环境。

## 未执行与限制

`EXTERNAL_REVIEW_NOT_EXECUTED`：没有对外发送本次代码、差异或任务上下文；尚未取得该具体外发上下文的批准。此记录不把本地行为复测称为外部代码审查。

未执行真实供应商端到端调用。已从本机 CLI help 核对 initial/resume、模型、推理参数及 OpenCode variant 的调用形态；真实服务端可用性、实际模型身份和实际 token 用量仍未验证，不宣称具体节省比例。轮前轮后指纹是后置核对，不能证明逐文件隔离或覆盖外部系统。

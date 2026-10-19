# 同一会话强模型调用合同

本文件拥有 `agents/dispatch-collaboration.py` 的输入、输出和调用语义；用户意图与问题处置由 [协作流程](../../gpt-grilling-review/references/strong-weak-collaboration.md) 拥有，问题分类、风险下限与 CLOSED 判据仍由 [gpt-grilling-review](../../gpt-grilling-review/SKILL.md) 拥有。CLI 仅加载下文引用的精简执行提示词。

## 模型职责

按需读取 [collaboration-prompt.md](../agents/collaboration-prompt.md)。它拥有 plan/review/repair 的执行约束和模型输出格式；本文件拥有调用者输入与工具回执，不重复模型合同。

## 输入：`dd-collaboration-request/1`

请求为单个 JSON 对象，通过 stdin 交给 `python3 <runtime>/agents/dispatch-collaboration.py`。不使用 shell 字符串拼接命令。

| 字段 | 合同 |
|---|---|
| `schema` | `dd-collaboration-request/1` |
| `workflow_id` | 当前父工作流的稳定标识；不另造工作流状态 |
| `backend` | 显式 `codex-cli` 或 `opencode-cli`；不自动降级 |
| `model`, `effort` | 本次明确选择的模型和推理档位；不修改 共享默认绑定；OpenCode `effort=default` 表示不添加 variant |
| `repo` | 仓库根目录绝对路径；用于本地 CLI 调用，不发送给 ChatGPT |
| `operation` | `plan` / `review` / `repair` |
| `scope` | 已授权、规范化的仓库相对文件清单；不得用目录代替；相关规格文件也列入 |
| `write_scope` | 本轮可写文件清单，必须为 scope 子集；plan 必须为空，review 默认空；已明确预授权小修复的 review 可非空，同时必须带 repair 策略 |
| `context` | 目标、验收条件、必要依据锚点、原 finding ID、裁决和风险说明；续接仅提供变化，但关键约束不能省略 |
| `baseline` | 本工具 `--snapshot <repo>` 输出的 `digest`；绑定 tracked、非忽略 untracked、删除、权限、HEAD 与 index，允许 未提交内容 |
| `verification` | `{command: [argv...]}` 列表；父会话自行审核命令并纳入授权；review 调用前执行，repair 成功后执行，plan 可为空 |
| `authorization` | `{approved: true, context_digest: <hash>}`，hash 由 `--context-digest` 绑定不含 authorization 的完整请求、执行提示词和 registry 内容；批准时一并展示这些指令与访问范围。只有人类已批准实际外发内容和访问范围后父会话才能写入 approved，不允许自动批准或由模型生成批准 |
| `session` | 续接时传入上轮工具确认的原生 session；不得用最近会话、别名、其他工作流或模型的 session |
| `repair` | 任何可写轮次均必需：`risk=LOW`、`behavior_defined=true`、`bounded=true`、非空 `rationale`、`finding_ids` 列表。repair 操作须有已核实的原 ID；预授权可写 review 可为空，供强模型当场发现小问题并登记。声明不能替代实际风险判断 |

来源与批准沿用父任务的 [执行包合同](artifact-source-and-packet.md)。`tasks` 是返回给当前执行者的任务视图，不是新的批准入口；不复制 source_manifest 或另建任务台账。真实用户数据、不可逆操作及 Git 交付授权不在此通道内。

## 强模型输出

输出字段与模型职责的唯一详细属主是 [collaboration-prompt.md](../agents/collaboration-prompt.md)，工具只发送该文件及本轮请求，不发送本调用说明全文。

## 工具回执与恢复

工具返回 `dd-collaboration-result/1`，附加真实 session、请求的 backend/model/effort、修改前后指纹、实际 changed_paths、命令退出码和输出摘要，以及供应商提供的 usage（没有则 null）。模型身份标为请求身份，不声称有供应商实际模型证明。

`closure_candidate=true` 仅可能出现在完整 review 的 PASS 或通过实际验证的 REPAIRED；当轮发生授权修改时标记 `closure_basis=strong-self-fix`。`closure_candidates` 仅列验证通过、覆盖完整的 fixed_findings ID；混合批次仍返回 FINDINGS，未修复大问题保持 OPEN。这不等于 CLOSED，父会话仍按四项关闭判据登记。本工具不直接关闭 finding。

CLI 命令形态只由 `agents/review-backends.yaml` 的 `collaboration` 字段拥有。`--snapshot` 与 `--context-digest` 均只读，不调用供应商。会话绑定元数据默认在 `~/.cache/dd-strong-collaboration/`，可用 `--state-dir` 指定仓库外目录；它仅绑定原生会话、身份和续接计数，不拥有工作流或 finding 状态。父会话在既有状态中保存回执。

`--snapshot` 只输出候选摘要、HEAD、index 指纹和文件数，不将全仓逐文件指纹打印进模型上下文。

续接严格绑定仓库、父工作流、backend、model、effort 和实际原生 session；默认最多两次续接。模型或身份变化须由父会话显式建立新审查轮次并重新读取真实材料，不继承旧关闭权。失败会话标为不可自动续接，保留原生句柄与当前改动，父会话核对后决定下一轮；不得删元数据绕过返工上限。

父会话调用期间暂停自己的写入并持有现有写者租约。本工具仅提供进程组终止、仓库调用互斥和轮前轮后核对；**不是逐文件沙箱**。Codex 使用 workspace-write；OpenCode 使用可写 build agent。越界写入、HEAD/index 变化、超时、输出或身份校验失败均 BLOCKED，不回滚用户文件、不自动换后端。忽略文件、仓库外文件、外部系统和修改后恢复原状的中途操作不在内容指纹的机械保证内；不能把这些后置检查称为只读或安全隔离证明。

当前指纹工具遇到子模块目录或特殊文件时保守阻塞；不把无法覆盖的候选当成已冻结。供应商实际可用性与输出形态须通过获批的真实调用另行验证，本地假供应商测试不能冒充服务端验证。

验证命令须将缓存留在忽略目录或仓库外；review 验证改变候选即阻塞，repair 后验证改变候选也须重新审查。缓存及状态不是验收证据；只有实际执行的结果可以报告。

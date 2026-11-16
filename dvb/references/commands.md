# Devboard 命令与模式

按需读取：入口选择、GitHub 模式缺命令、换机接手。产品接口以部署版本和 Devboard 仓库合同为准。

## 判断当前能力

| 模式 | 权威与入口 | 失败处理 |
|---|---|---|
| `github-decentralized` | 本机协调服务访问同一私有 `board` 分支，本机缓存可重建 | 未发现启用能力就停止该写动作；不启动直连 SQLite 的旧 MCP 来写 |
| `central` | 经已配置设备身份访问中央服务 | `central-unavailable` 时只读旧缓存 |
| `local-only` | 已明确使用的单机数据集与既有 MCP | 不宣称跨机认领或同步，不作为 GitHub 模式失败时的可写后备 |

M5 日常命令已交付并合入 develop（2026-11-16，含通用 `devboard` CLI 与 board 模式写入器）。board 模式写动作按 `BOARD_WRITE_ACTIONS` 逐动作 opt-in（服务端白名单覆盖 `register_session`、`claim_task`、`heartbeat`、`release_task`、`append_checkpoint`、`create_task`、`update_task`、`create_project`、`reconcile_worktree`、`bind_worktree`、`unbind_worktree`、`decide_task_proposal`、`pause_task`、`resume_task`、`add_dependency`、`remove_dependency`、`accept_handoff`、`request_task_completion`、`decide_task_completion`；`decide_task_completion` 另需 coordinator 凭据）。服务未启用某动作时，该写动作仍不可用。后续版本一律以 `/api/v1/capabilities` 与实际响应核实为准。

没有安全写客户端仍可查询。先确认 `DEVBOARD_URL` 是配置好的本机地址，未配置时从可信本机配置查，不猜端口。**查询 `/api/v1/board` 建议带 `project_id`**：数据集只有 1 个项目时，不带参数也返回 200；多于 1 个项目时服务端返回 400（`INVALID_INPUT`）。因此始终先从项目列表取得真实 ID 再查询，既避免歧义也不依赖项目数量。实测记录（2026-11-11，单项目实验数据集）：`/api/v1/projects` → 200、`/api/v1/board?project_id=trial` → 200、`/api/v1/board` → **200**。只读例子：

```bash
curl --fail --silent --show-error "${DEVBOARD_URL:?需要已配置的本机 Devboard 地址}/api/v1/meta"
# 先取项目列表，从响应里选一个真实 project_id（不要从目录名猜）
curl --fail --silent --show-error "${DEVBOARD_URL:?}/api/v1/projects"
# 再用该 ID 查询看板；URL 编码按实际 ID 处理
curl --fail --silent --show-error "${DEVBOARD_URL:?}/api/v1/board?project_id=PROJECT_ID"
```

部署版本可能变化，实际参数要求以**真实 HTTP 响应**核对：分别请求带 `project_id` 与不带参数的 `/api/v1/board`，记录状态码与错误 code，再决定示例与客户端行为。场景演练通过不能代替这次 HTTP 验证。

已有 task_id 时读取 GET `/api/v1/tasks/{id}` 与 `/api/v1/tasks/{id}/checkpoints`，按需读取 `/worktrees`、`/gates`。`synced_at` 若只是缓存重建时间，不能据此声称远端已确认。没有服务端就绪查询时展示任务状态，不把全部 `open` 任务称为可认领。

## 名称映射

| MCP/语义操作 | HTTP action |
|---|---|
| `register_project` | `create_project` |
| `heartbeat_task` | `heartbeat` |
| `prepare_handoff` | `preflight_handoff`，仅核验，不转移租约 |
| `accept_handoff` | `takeover`，intent=`handoff`，需完整恢复核验 |
| `release_task` | `release_task`，HTTP 已有，旧 MCP 未必有同名工具 |
| `create_task` / `update_task` / `pause_task` / `resume_task` / `append_checkpoint` / 完成及提案裁决 | 同名 |

`register_session`、`claim_task` 同名；必填字段读实际 `tools/list` 或已安装 CLI 的帮助。HTTP `register_session` 与首次认领的响应可含秘密，不能让原始响应进入模型上下文。仅使用能内置保存并脱敏的客户端；不手工拼令牌头，不让用户粘贴令牌。

## 首次注册与丢响应恢复

`session register` 不接受 machine/device 参数：真实身份来自服务端已配置的本机绑定。`GET /api/v1/capabilities` 返回非秘密 `local_identity`（`machine_id`、`device_id`、`host_kind`、绑定状态、`register_session` 是否启用）；先 `status` 核对它与本机绑定一致，响应不含任何令牌或凭据摘要。

引导凭据只从显式配置的 `DEVBOARD_BOOTSTRAP_TOKEN_FILE`（0600、仅回环）读取，由客户端注入 `X-Bootstrap-Token`；不要 `cat` 令牌、不要拼 curl、不要让模型或输入文件提供 machine/device/`role`。缺配置、权限过宽、绑定不匹配或设备已撤销时停止注册并报告缺口，不猜路径、不拿协调者凭据或注册令牌互相替代。

首次响应丢失时，用**原 `request_id` 与原输入**重试，服务端返回同一 `session_id` 且不新增提交；令牌确实丢失时按既有 runbook 由本机操作员/设备上下文重新授权并轮换本地凭据（旧令牌失效、session 身份不变、遵守重签冷却），不换键重建会话。每个 App/worktree 各自注册，不共用隐式「当前 session」。

## 实验板与双机验收

隔离实验数据集必须含一张由既有导出器生成的合法种子任务：现有 `github-decentralized` 缓存在零任务时拒绝重建，空板无法作为首次建单前置。完全空板建单需另列守卫改动与验证，不属首版。

本地双客户端 tracer（两个缓存 + 临时 Git bare remote）与真实双机 GitHub 链路是两道独立闸：真实演示要求 A 建单推送 → B 经 GitHub 同步后更新优先级并推送 → A 再同步看到同一 `task_id` 的新 `revision`，并分别保存两机 CLI 结果、board commit SHA、真实 `git log`/`git diff`、UI 截图与跨物理机器确认。没有第二台机器或具体授权时如实标注真实双机 `NOT_RUN` / `BLOCKED`，保留本地成果，不把本地 tracer 说成已验收，也不据此推进后续阶段。

## devboard CLI（M5 已交付）

以下入口已在 develop 提供并经实际二进制 `--help` 核实（2026-11-16）。**仍只有当前二进制实际提供、服务报告相应动作已启用才执行**；部署版本可能落后于 develop。

```text
devboard status --json
devboard sync --json
devboard task list --project PROJECT --json
devboard task show TASK --json
devboard session register --agent AGENT --host-kind HOST --request-id KEY --json
devboard call OP --session SESSION --request-id KEY --input-file FILE --json
```

CLI 建单/更新在已登记项目进行，两机同步后看到同一 ID 与 revision；`claim` 自动保存租约凭据（本机 0600），`heartbeat`/`checkpoint`/`release` 自动注入并在 stdout 脱敏。`devboard endpoint --discover-desktop` 仅 macOS、发现桌面 App 发布的端点（显式 `--endpoint`/`DEVBOARD_URL` 优先且与发现互斥）。现有 `devboard-complete` 等专项工具不等于通用 CLI。协调者调用只用已经配置的授权，参数本身不提升角色。

board 模式操作员边界（§3.6.5）：操作员裁决（如 `decide_task_completion`）走专用 0600 绑定文件（`DEVBOARD_OPERATOR_TOKEN_FILE`，内含 operator 令牌与其代理的会话），未配置时一切操作员动作 fail-closed。**桌面 App 的口令登录在 board 模式是设计性关闭**（board 无口令注册表）：App 只能浏览看板，操作员动作经绑定文件由 CLI/MCP 执行；不要把 agent 会话令牌当操作员凭据，也不要试图用口令登录 board 服务。

## 换机器和 worktree

1. 核对两台机器是同一 board remote/branch。新机器缺设备身份时，定位 Devboard 仓库的 F10 `board-identity-runbook.md`，由授权操作员按既有路径登记；不复制别机 token 或临时改生产 anchor。
2. 同步并读 task_id、最新检查点、持有者、项目仓库 remote/branch/提交和合同引用。原机绝对路径只作提示，在本机重新发现 worktree。
3. 核对工作内容可达、合同有效、接手授权与隔离条件满足。原机仍持有租约或只有原机 dirty 内容时，不宣称可以接续。**显式释放只释放租约，不解除任务与工作树的绑定**；接手还需按已批准的绑定规则完成旧绑定退出，并用本机真实 `machine_id`/`worktree_id` 建立新绑定，否则跨机写入会被归属检查拒绝。不要用跳过检查、手改绑定或到期自动接管绕过。
4. 新会话按已支持路径获取新代际，再开始写入。只有已确认检查点 + 可达工作内容 + 有效新持有者（含新绑定）才报告交接完成；看到任务卡、释放成功或到期均不足以证明交接。

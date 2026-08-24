# 强弱路由宿主冒烟验收清单（SWMR-011，VERIFICATION_PENDING）

> 依据 FR-015 / NFR-008 / AC-11：配置存在、可发现、模型生效、推理档生效、只读生效、真实调用出约定 schema 必须逐级记录，低层成功不得推导高层结论。
> 状态标记：`pending` / `pass` / `fail`（附证据链接）。任何宿主在 L1-L7 全部达到 `pass` 或结构性 `N/A` 前，都不得被 model-routing 矩阵视为"原生可用已验证"。

## 检查级别

| 级别 | 含义 | 方法 |
|---|---|---|
| L1 configured | 绑定文件解析通过 | TOML/YAML/frontmatter 解析 |
| L2 installed | 宿主侧安装引用有效且指向 canonical | 按宿主实测方式验证；Codex 必须直连普通文件，其他宿主可在验证后使用 symlink |
| L3 discovered | 宿主能发现该 agent | 各宿主 list/发现机制 |
| L4 model-effective | 指定模型真实生效 | 宿主会话内查询实际模型 |
| L5 effort-effective | 推理档真实生效 | 宿主报告或行为证据 |
| L6 readonly-effective | 工具集合实际只读 | 尝试写操作必须被拒 |
| L7 invoked-schema | 真实调用返回 PASS/FINDINGS/BLOCKED | 最小审查任务实测 |

## Codex（~/.codex/config.toml `[agents.*].config_file` → agents/codex/{luna-worker,strong-reviewer}.toml）

- L1 configured: pass（2026-08-24 tomllib 解析通过且含必需键 name/description/model/model_reasoning_effort；SWMR-014 修正本行状态滞后）
- L2 installed: **pass**（2026-08-24 `config.toml [agents.*].config_file` 已直接指向 canonical 普通文件；`~/.codex/agents/` 下同名 symlink 已删除，避免自动发现产生重复角色；`python3 agents/validate-bindings.py --check-codex-install` 校验覆盖路径存在、非 symlink、与 canonical 为同一文件且无同名自动发现副本）
- L3 discovered: **pass**（2026-08-24 `codex exec` 实测：主代理正确列出当前自定义代理 `luna-worker`、`strong-reviewer`，消耗 ~33k tokens）
- L4 model-effective: **pass**（2026-08-24 本地 `state_5.sqlite` 的 parent→child spawn edge 及 child thread 元数据分别记录 `strong-reviewer → gpt-5.6-sol`、`luna-worker → gpt-5.6-luna`；不采用 LLM 自报模型名）
- L5 effort-effective: **pass**（同一宿主元数据分别记录 `strong-reviewer → high`、`luna-worker → max`）
- L6 readonly-effective: **pass（正常父 sandbox）/ fail（危险父 sandbox override）**（2026-08-24 正常父 sandbox 下，子代理真实调用 `touch /tmp/.../l6-should-not-exist`，Seatbelt 记录 `operation_not_permitted`，命令退出 1，目标文件复查不存在；child thread 元数据同时记录文件系统仅 root read、网络 restricted。经用户授权，另在隔离目录 `/tmp/codex-l6-danger-oyjciU` 以 `codex exec --dangerously-bypass-approvals-and-sandbox` 启动父会话，委派 `strong-reviewer` 执行唯一的 `touch`。命令退出 0，父会话独立复查确认目标存在，故 bypass 会覆盖子代理的只读限制，禁止在此模式下把该角色当作只读边界。）
- L7 invoked-schema: **pass**（2026-08-24 CLI 0.149.0：直连 canonical 普通文件后，luna-worker 成功派生并返回 `2+2=4`；strong-reviewer 在持久会话成功派生，并对冻结命题返回 `PASS`。不启用 `multi_agent_v2` 仍成功，排除该 flag 为必要条件）
- 根因修正：此前 `config_file` 指向 `~/.codex/agents/*.toml` symlink；角色加载先报 `Too many levels of symbolic links (os error 62)`，router 随后将其模糊为 `agent type is currently not available`。把 `config_file` 临时覆盖为 canonical 普通文件后立即派生成功，故 `74a7049` 的“上游 rollout 门控”定性作废。
- 安装去重：改为 direct `config_file` 后若保留 `~/.codex/agents/{luna-worker,strong-reviewer}.toml`，CLI 会报告 `duplicate agent role name ... declared in the same config layer`；删除两个冗余 symlink 后，以 `config.toml` 注册作为唯一发现入口。
- 冒烟约束：多 Agent 测试不要使用 `--ephemeral`。本轮 strong-reviewer 在 ephemeral 父会话遇到 `collab spawn failed: no thread with id`，改用持久会话后成功；这是独立的父线程生命周期问题，不是角色绑定失败。
- 当前结论：Codex worker + reviewer 在正常父 sandbox 下 L1-L7 全链贯通；危险父 sandbox override 下 L6 明确失败，不能作为只读执行环境，但按 2026-08-24 用户决策该模式仍可使用（调用方必须自行承担写入风险）；完整宿主结论继续保留 `VERIFICATION_PENDING`。

## ZCode（agents/zcode/strong-reviewer.md → ~/.zcode/agents/）

- L1 configured: pending（frontmatter 符合 Beta 合同）
- L2 installed: pending（symlink 就绪）
- L3 discovered: pending（新会话生效，未验证）
- L4-L5: **降级模式**——model: inherit 下 thoughtLevel 被忽略；绑定具体强模型 id 前标记 N/A（degraded），高风险任务走 external
- L6 readonly-effective: pending（tools 白名单 Read/Grep/Glob）
- L7: pending

## OpenCode（agents/opencode/strong-reviewer.md → ~/.config/opencode/agents/）

- L1 configured: pass（2026-08-24 通配符 deny + 显式只读 allow 解析通过）
- L2 installed: pass（symlink 有效）
- L3 discovered: pass（`opencode agent list` 显示 strong-reviewer (subagent)）
- L4 model-effective: **pass**（sqlite 会话库证据：task 委派的子会话 assistant 消息为 deepseek/deepseek-reasoner，与绑定一致；同轮主会话为 deepseek-chat，证明按角色差异化生效。注意 LLM 自报模型名不可靠——首轮子代理自称"gpt-5.6-sol"系回声被审文件内容，已弃用该取证方式）
- L5 effort-effective: N/A（reasoner 为推理专精模型，无独立档位）
- L6 readonly-effective: **pass**（强制 task 委派后指令子代理在仓库内写文件：task completed 但目标文件不存在；注意首次测试无效——@ 提及未派生子代理（事件中 task 调用数为 0），写入由主代理完成，不能作为证据）
- L7 invoked-schema: pass（真实审查调用返回 PASS 结论，含已审/未读范围、基线核对）
- 结论：**七级全链贯通（L5 为结构性 N/A），OpenCode 原生强审路径可用**

## Qoder（agents/qoder/strong-reviewer.md，canonical only）

- L1 configured: pending（frontmatter 与官方 schema 一致，未经客户端解析）
- L2 installed: **blocked**（R-003：Qoder CN 权威配置根待实机确认后再装）
- L3-L7: pending（依赖 L2）

## CodeBuddy CLI（agents/codebuddy/strong-reviewer.md，canonical only）

- L1 configured: pass（2026-08-24 frontmatter 与官方插件 agent schema 一致：name/model/effort/tools 白名单；validator 6 宿主 6 角色通过）
- L2 installed: **blocked**（需在 CodeBuddy 插件 agents/ 目录实装；model: inherit 待绑定强模型 id，绑定前为降级模式）
- L3-L7: pending（依赖 L2）

## Trae

- 无原生绑定（矩阵既定）；external 路径依赖 chatgpt-review MCP——配置存在已实证（CN 与 SOLO 的 mcps 缓存含 mcp_chatgpt-review），L7 级"真实送审一轮"待做。

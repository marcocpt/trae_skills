# 强弱路由宿主冒烟验收清单（SWMR-011，VERIFICATION_PENDING）

> 依据 FR-015 / NFR-008 / AC-11：配置存在、可发现、模型生效、推理档生效、只读生效、真实调用出约定 schema 必须逐级记录，低层成功不得推导高层结论。
> 状态标记：`pending` / `pass` / `fail`（附证据链接）。任何宿主在 `invoked` 前都不得被 model-routing 矩阵视为"原生可用已验证"。

## 检查级别

| 级别 | 含义 | 方法 |
|---|---|---|
| L1 configured | 绑定文件解析通过 | TOML/YAML/frontmatter 解析 |
| L2 installed | 宿主侧安装引用有效且指向 canonical | symlink 目标存在 |
| L3 discovered | 宿主能发现该 agent | 各宿主 list/发现机制 |
| L4 model-effective | 指定模型真实生效 | 宿主会话内查询实际模型 |
| L5 effort-effective | 推理档真实生效 | 宿主报告或行为证据 |
| L6 readonly-effective | 工具集合实际只读 | 尝试写操作必须被拒 |
| L7 invoked-schema | 真实调用返回 PASS/FINDINGS/BLOCKED | 最小审查任务实测 |

## Codex（agents/codex/{luna-worker,strong-reviewer}.toml → ~/.codex/agents/）

- L1 configured: pass（2026-08-24 tomllib 解析通过且含必需键 name/description/model/model_reasoning_effort；SWMR-014 修正本行状态滞后）
- L2 installed: pending（symlink 就绪；config.toml `[agents.*]` 注册确认）
- L3 discovered: pending（需 `/agent` 或等价发现验证）
- L4-L7: pending
- 备注：官方文档提示 parent turn 的 sandbox override（如 `--yolo`）会在 spawn 时重新应用——L6 必须在该场景下复测，不得只凭 toml `sandbox_mode = "read-only"` 宣称只读。

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

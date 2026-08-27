# Generic Review Backend Router v1 smoke checklist

本清单只记录能力层级，不把配置存在或进程启动成功推导为业务 Review PASS。真实 provider 调用、只读探针和外部授权需要在对应宿主中单独取证。

| Level | Evidence | Status |
|---|---|---|
| L1 registry configured | `review-backends.yaml` 可解析，包含 MCP、Codex CLI/native、OpenCode CLI/native | PASS（本地静态校验） |
| L2 policy configured | `routing-policy.yaml` 的 `strong-reviewer` chain 为 MCP → Codex → host-native，`max_hops=1` | PASS（本地静态校验） |
| L3 references isolated | validator 拒绝未知 backend，拒绝把 transport 字段放入 `model-bindings.yaml` | PASS（自动化测试） |
| L4 deterministic dispatch | frozen SHA、scope、verification、single-backend metadata 可校验 | PASS（自动化测试） |
| L5 fallback semantics | 仅 transport-unavailable fallback；FINDINGS/schema/evidence/readonly/recursion fail closed | PASS（自动化测试） |
| L6 readonly effective | 各真实 backend 的写入负向探针；当前按 backend 分项记账 | PENDING/PARTIAL（`codex-cli`、`mcp-review`、`opencode-cli` PASS；其他 backend PENDING） |
| L7 review result | 各真实 backend 返回 `dd-review-result/1` 并携带 baseline/reviewed/unreadable | PENDING/PARTIAL（`mcp-review`、`opencode-cli`、`codex-cli` PASS 能力贯通、verdict=FINDINGS；其他 backend PENDING） |

### L6 backend-specific evidence

- `codex-cli`: **PASS**（2026-08-25；真实 `codex exec --sandbox read-only --json` 对既有文件覆盖和新文件创建均返回 `operation not permitted`，父进程复查确认 hash、内容、文件清单、Git status 和 diff 均未变化）。证据：[codex-cli-l6-evidence.yaml](evidence/codex-cli-l6-evidence.yaml)
- `mcp-review`: **PASS**（2026-08-26；真实 Streamable HTTP MCP exact tool set、实际 `chatgpt_send`/`chatgpt_get_result` 调用、snapshot 输入隔离和父进程 workspace invariants 均通过）。证据：[mcp-review-l6-evidence.yaml](evidence/mcp-review-l6-evidence.yaml)
- `opencode-cli`: **PASS**（2026-08-27；新增 primary-mode invocation profile `strong-reviewer-cli` 修复调用边界后，真实 `opencode run --agent strong-reviewer-cli --format json` 直接钉住 readonly agent（无 fallback、effective agent 一致），Muse Spark 1.2 Free 会话内 write/edit/bash 工具根本不可用（0 次 tool_use），父进程复查确认 hash/内容/文件清单/Git status/diff 均未变化；历史 fallback 失败见 [opencode-cli-l6-blocked-evidence.yaml](evidence/opencode-cli-l6-blocked-evidence.yaml)）。证据：[opencode-cli-l6-evidence.yaml](evidence/opencode-cli-l6-evidence.yaml)
- `codex-native`: PENDING
- `opencode-native`: PENDING

聚合 L6 仍为 `PENDING/PARTIAL`（`codex-cli`/`mcp-review`/`opencode-cli` 三项 PASS；`codex-native`/`opencode-native` 仍 PENDING）。2026-08-27 轮：调用边界修复（`strong-reviewer-cli` primary-mode profile）后重取 opencode-cli L6 成功 PASS（Muse Spark 1.2 Free）；本轮未执行任何 L7。

### L7 backend-specific evidence

- `mcp-review`: **PASS（能力贯通；verdict=FINDINGS）**（2026-08-26；provider-contract 修复后，真实 Router path 贯通至真实 ChatGPT Reviewer，provider 返回严格 `dd-review-provider/1` JSON（零 Markdown 转义），adapter 归一化为合法 `dd-review-result/1`，Router 以 Router-owned readonly confirmation 接受，verdict=FINDINGS，无 fallback）。证据：[mcp-review-l7-evidence.yaml](evidence/mcp-review-l7-evidence.yaml)
- `opencode-cli`: **PASS（能力贯通；verdict=FINDINGS）**（2026-08-27；新增 thin adapter `opencode-review` 解析 NDJSON event stream 并严格校验最终 JSON，真实 Router 完整路径 `opencode-cli → strong-reviewer-cli → Muse Spark 1.2 Free` 返回 FINDINGS（RV-001 HIGH 静默除零），Router 以 Router-owned readonly confirmation 接受，无 fallback，未放宽 readonly/invocation contract）。证据：[opencode-cli-l7-evidence.yaml](evidence/opencode-cli-l7-evidence.yaml)
- `codex-cli`: **PASS（能力贯通；verdict=FINDINGS）**（2026-08-27；新增 thin adapter `codex-review` 解析 JSONL 严格校验最终 JSON，真实 Router 完整路径 `codex-cli → strong-reviewer → gpt-5.6-sol` 返回 FINDINGS（RV-001 HIGH 静默除零），Router 以 Router-owned readonly confirmation 接受，无 fallback，未放宽 readonly，L6 版本漂移 0.149.0→0.149.1 已重探 sandbox 仍只读）。证据：[codex-cli-l7-evidence.yaml](evidence/codex-cli-l7-evidence.yaml)
- `codex-native`: PENDING
- `opencode-native`: PENDING

聚合 L7 仍为 `PENDING/PARTIAL`（`mcp-review`、`opencode-cli`、`codex-cli` 已 PASS；其余 PENDING）。`mcp-review` 的 L7 能力已贯通（verdict=FINDINGS，属真实 Reviewer 判定，不影响 L7 能力 PASS）；该轮发现并修复了真实 provider-contract failure（chatgpt-review MCP 在提取严格 JSON 响应时被 Turndown 注入 Markdown 转义，已通过 `work/MCP` 的 `extractReply` 严格 JSON 原样保留修复，未放宽 adapter parser / provider schema / readonly authority，未发起隐式重试或第二次 review）。Router 归因缺陷 `router_observation.OBS-L7-001`（terminal BLOCKED 的 `failure_category` 被掩盖为 `readonly_violation`）：**OBS-L7-001 = FIXED**（Phase C Option B 下 Router 在 invocation 前已完成 backend-bound L6 eligibility，合法解析的 terminal BLOCKED 不再把 adapter/provider 的 `readonly_confirmation` 当作 authority，真实 `failure_category` 如 `schema_invalid`、`evidence_mismatch`、`review_incomplete`、`backend_execution_failed`、`readonly_violation` 原样保留；pre-dispatch eligibility、PASS/FINDINGS 的 Router-owned confirmation 与 fallback policy 不变。历史 evidence 文件中的观察记录保持原样，未篡改。）

运行本地静态与回归检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 dd-workflow-runtime/agents/validate-review-routing.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest dd-workflow-runtime/tests/test_dispatch_review.py dd-workflow-runtime/tests/test_check_review_route.py
```

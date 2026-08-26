# Generic Review Backend Router v1 smoke checklist

本清单只记录能力层级，不把配置存在或进程启动成功推导为业务 Review PASS。真实 provider 调用、只读探针和外部授权需要在对应宿主中单独取证。

| Level | Evidence | Status |
|---|---|---|
| L1 registry configured | `review-backends.yaml` 可解析，包含 MCP、Codex CLI/native、OpenCode CLI/native | PASS（本地静态校验） |
| L2 policy configured | `routing-policy.yaml` 的 `strong-reviewer` chain 为 MCP → Codex → host-native，`max_hops=1` | PASS（本地静态校验） |
| L3 references isolated | validator 拒绝未知 backend，拒绝把 transport 字段放入 `model-bindings.yaml` | PASS（自动化测试） |
| L4 deterministic dispatch | frozen SHA、scope、verification、single-backend metadata 可校验 | PASS（自动化测试） |
| L5 fallback semantics | 仅 transport-unavailable fallback；FINDINGS/schema/evidence/readonly/recursion fail closed | PASS（自动化测试） |
| L6 readonly effective | 各真实 backend 的写入负向探针；当前按 backend 分项记账 | PENDING/PARTIAL（`codex-cli`、`mcp-review` PASS；其他 backend PENDING） |
| L7 review result | 各真实 backend 返回 `dd-review-result/1` 并携带 baseline/reviewed/unreadable | PENDING（`mcp-review` BLOCKED/provider-contract；其他 backend PENDING） |

### L6 backend-specific evidence

- `codex-cli`: **PASS**（2026-08-25；真实 `codex exec --sandbox read-only --json` 对既有文件覆盖和新文件创建均返回 `operation not permitted`，父进程复查确认 hash、内容、文件清单、Git status 和 diff 均未变化）。证据：[codex-cli-l6-evidence.yaml](evidence/codex-cli-l6-evidence.yaml)
- `mcp-review`: **PASS**（2026-08-26；真实 Streamable HTTP MCP exact tool set、实际 `chatgpt_send`/`chatgpt_get_result` 调用、snapshot 输入隔离和父进程 workspace invariants 均通过）。证据：[mcp-review-l6-evidence.yaml](evidence/mcp-review-l6-evidence.yaml)
- `opencode-cli`: PENDING
- `codex-native`: PENDING
- `opencode-native`: PENDING

聚合 L6 仍为 `PENDING/PARTIAL`；本次只闭合 `mcp-review` 的 `snapshot-send-only` backend-bound L6，不推导其他 backend 或任何 L7 结论。

### L7 backend-specific evidence

- `mcp-review`: **BLOCKED**（2026-08-26；真实 Router path 已贯通到真实 ChatGPT Reviewer，但 provider 返回被 Markdown 转义污染的非严格 `dd-review-provider/1` JSON，`schema_invalid` fail closed）。证据：[mcp-review-l7-blocked-evidence.yaml](evidence/mcp-review-l7-blocked-evidence.yaml)
- `codex-cli`: PENDING
- `opencode-cli`: PENDING
- `codex-native`: PENDING
- `opencode-native`: PENDING

聚合 L7 仍为 `PENDING`。`mcp-review` 的 BLOCKED 属于真实 provider-contract failure：adapter parser、provider/result schema 校验和 readonly authority 模型均未放宽，也未发起隐式重试或第二次 review。已记录的 Router 归因缺陷见证据文件 `router_observation.OBS-L7-001`（terminal BLOCKED 的 `failure_category` 被掩盖为 `readonly_violation`），fail-closed 行为本身仍然正确。

运行本地静态与回归检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 dd-workflow-runtime/agents/validate-review-routing.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest dd-workflow-runtime/tests/test_dispatch_review.py dd-workflow-runtime/tests/test_check_review_route.py
```

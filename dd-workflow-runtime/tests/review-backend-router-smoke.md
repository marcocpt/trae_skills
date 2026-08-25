# Generic Review Backend Router v1 smoke checklist

本清单只记录能力层级，不把配置存在或进程启动成功推导为业务 Review PASS。真实 provider 调用、只读探针和外部授权需要在对应宿主中单独取证。

| Level | Evidence | Status |
|---|---|---|
| L1 registry configured | `review-backends.yaml` 可解析，包含 MCP、Codex CLI/native、OpenCode CLI/native | PASS（本地静态校验） |
| L2 policy configured | `routing-policy.yaml` 的 `strong-reviewer` chain 为 MCP → Codex → host-native，`max_hops=1` | PASS（本地静态校验） |
| L3 references isolated | validator 拒绝未知 backend，拒绝把 transport 字段放入 `model-bindings.yaml` | PASS（自动化测试） |
| L4 deterministic dispatch | frozen SHA、scope、verification、single-backend metadata 可校验 | PASS（自动化测试） |
| L5 fallback semantics | 仅 transport-unavailable fallback；FINDINGS/schema/evidence/readonly/recursion fail closed | PASS（自动化测试） |
| L6 readonly effective | 各真实 backend 的写入负向探针；当前按 backend 分项记账 | PENDING/PARTIAL（`codex-cli` PASS；其他 backend PENDING） |
| L7 review result | 各真实 backend 返回 `dd-review-result/1` 并携带 baseline/reviewed/unreadable | PENDING（宿主/后端实测） |

### L6 backend-specific evidence

- `codex-cli`: **PASS**（2026-08-25；真实 `codex exec --sandbox read-only --json` 对既有文件覆盖和新文件创建均返回 `operation not permitted`，父进程复查确认 hash、内容、文件清单、Git status 和 diff 均未变化）。证据：[codex-cli-l6-evidence.yaml](evidence/codex-cli-l6-evidence.yaml)
- `mcp-review`: PENDING
- `opencode-cli`: PENDING
- `codex-native`: PENDING
- `opencode-native`: PENDING

聚合 L6 仍为 `PENDING/PARTIAL`；本次只闭合 `codex-cli` 的 `codex-read-only-transport` backend-bound L6，不推导其他 backend 或任何 L7 结论。

运行本地静态与回归检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 dd-workflow-runtime/agents/validate-review-routing.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest dd-workflow-runtime/tests/test_dispatch_review.py dd-workflow-runtime/tests/test_check_review_route.py
```

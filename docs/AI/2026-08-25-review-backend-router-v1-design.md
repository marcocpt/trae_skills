# Generic Review Backend Router v1

## Purpose

This document defines the smallest host-neutral dispatch boundary for a
reviewer role.  It generalizes the existing Codex-to-OpenCode transport plan
without moving model bindings, finding lifecycle, or workflow state into the
adapter.

## Ownership

| Fact | Canonical owner | Router use |
|---|---|---|
| Host → logical role → native model/profile | `agents/model-bindings.yaml` | Read-only isolation check; never used to choose an external backend |
| Backend invocation, capability and read-only requirements | `agents/review-backends.yaml` | Validate and invoke one adapter |
| Role → ordered backend candidates and fallback categories | `agents/routing-policy.yaml` | Select the first eligible backend |
| Workflow state, lease, rework and external authorization lifecycle | Runtime state/workflow | Supplied as request evidence; never owned by an adapter |
| A/B/C review semantics and external finding closure | Existing runtime and `gpt-grilling-review` contracts | Referenced, not duplicated |

## Request and result contracts

`dispatch-review.py` accepts `dd-review-request/1`.  A request contains the
logical role, current host, repository, `base_sha`, `head_sha`, relative scope,
successful deterministic verification evidence, external authorization when
needed, read-only evidence, and routing metadata:

```yaml
schema: dd-review-request/1
role: strong-reviewer
host: codex
repo: /absolute/path
base_sha: <commit>
head_sha: <commit>
scope: [relative/file]
verification: [{name: tests, status: passed, evidence: ...}]
external_review: {authorization: approved, scope: [relative/file]}
readonly_evidence:
  - {backend: mcp-review, mode: snapshot-send-only, level: L6, confirmed: true, source: dd-workflow-runtime/tests/evidence/mcp-review-l6-evidence.yaml}
  - {backend: codex-cli, mode: codex-read-only-transport, level: L6, confirmed: true, source: ...}
context: {hop_count: 0, dispatch_chain: []}
```

The normalized result is `dd-review-result/1` and uses the existing three
review states: `PASS`, `FINDINGS`, and `BLOCKED`.  It carries the selected
backend, reviewer identity, target/baseline identity, reviewed/unreadable
scope, findings, evidence, lifecycle, failure category, read-only
confirmation, and routing metadata.  `FAIL` from a provider is normalized to
`FINDINGS`; it is never treated as backend unavailability.

## Dispatch boundary and fallback

The v1 algorithm is deliberately linear:

```text
validate request and frozen git evidence
  → read role policy
  → resolve host-native alias
  → check authorization/capability/read-only eligibility
  → invoke exactly one adapter
  → normalize and validate result
  → fallback only for explicit transport-unavailable categories
```

The default strong-reviewer chain is:

```text
MCP → Codex CLI → current-host native reviewer → BLOCKED
```

`reviewer FINDINGS`, schema errors, evidence/baseline mismatch,
authorization/read-only violations, and recursion violations fail closed.  A
backend adapter receives `dispatch_boundary=single-backend` and cannot call
the router again.  `max_hops=1` and `dispatch_chain` reject nested `A → B → A`
or `A → MCP → Codex → MCP` dispatches.

The router does not acquire the cross-host writer lease or persist workflow
state.  The caller must persist frozen baseline and authorization before
calling it, and must treat an incomplete/blocked result as incomplete.  The
adapter receives only the approved review context and routing boundary; local
authorization proofs and host guard metadata are not forwarded.  Read-only
evidence is a per-backend L6 proof matched to the registry's `readonly_mode`
and cannot be reused across candidates.  The Router remains the sole owner of
the result-side read-only confirmation: after eligibility succeeds, it
replaces the provider's PASS/FINDINGS confirmation with a local attestation
derived from the already-validated backend-bound proof.  The adapter/provider
cannot create or upgrade that confirmation.  A `BLOCKED` result keeps the
parsed terminal `failure_category`: because eligibility (including the
backend-bound L6 proof) is enforced before invocation, the adapter's own
`readonly_confirmation` is only a non-authoritative observation on that path
and must neither mint trust nor overwrite the terminal category.  The generic Router does not directly
select `codex-native`: a verified host-native dispatcher must run
`check-review-route.py` from this Skill's actual root and prove current-parent
thread provenance before taking that handoff.  Without that handoff the Router
fails closed.  The adapter is a single request transport; it cannot write the
worktree, commit, repair findings, or close an external finding.

For `mcp-review`, `snapshot-send-only` describes the adapter capability
boundary: it sends an in-memory frozen snapshot through `chatgpt_send` and
retrieves the result through `chatgpt_get_result`; it does not supply a repo
path and it never calls `chatgpt_send_file`.  This transport description is
not by itself backend-specific L6 evidence.  The real backend-bound probe is
recorded in
`dd-workflow-runtime/tests/evidence/mcp-review-l6-evidence.yaml`; Router
eligibility may use that proof only after checking its exact backend, mode,
level, confirmation, and source.  The provider response is a strict
`dd-review-provider/1` JSON object; Markdown or incomplete scope is rejected
fail-closed before producing an accepted result.

## v1 boundary

The CLI-shaped adapter is the first executable transport.  The MCP entry is a
single-request backend slot, not an MCP router or scheduler.  Real provider
availability, sandbox enforcement, and external authorization remain runtime
evidence and are not inferred from a config file or from a successful process
launch.  CLI exit codes have an explicit registry classification; unknown
non-zero exits are `backend_execution_failed` and are terminal.  No provider
credentials, model names, fallback chains, or absolute machine paths belong in
`model-bindings.yaml`.

Governance mapping: FR-008 and DD-006 are enforced by frozen request checks,
read-only evidence and result validation; DD-004 by the single MCP request
adapter boundary; DD-005 by keeping policy in versioned host-neutral YAML;
FR-009/010/012/014 by baseline identity, three-state results, bounded hops and
fail-closed fallback semantics.

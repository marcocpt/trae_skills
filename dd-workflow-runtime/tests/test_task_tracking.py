#!/usr/bin/env python3
"""Contract tests for the external task-tracking projection contract.

Owner: dd-workflow-runtime/references/task-tracking.md (single source for the
`tracking` nested schema, checkpoint write-back, takeover collision detection
and board projection). Design rationale and test matrix:
docs/AI/2026-10-02-task-tracking-projection-design.md §6.

Assertions are section-scoped and behavioral on purpose (design §6 M-03):
keyword existence is not enough. TestMutations (§6.6) proves the checks are
not keyword-existence checks: minimal semantic tampering must turn them red.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RUNTIME_SKILL = REPO_ROOT / "dd-workflow-runtime" / "SKILL.md"
RUNTIME_CONTRACT = REPO_ROOT / "dd-workflow-runtime" / "references" / "runtime-contract.md"
RUNTIME_STATE = REPO_ROOT / "dd-workflow-runtime" / "references" / "state.md"
TASK_TRACKING = REPO_ROOT / "dd-workflow-runtime" / "references" / "task-tracking.md"
FEATURE_INTAKE = (
    REPO_ROOT / "dd-feature-development-workflow" / "references" / "intake-and-environment.md"
)
FEATURE_STATE = (
    REPO_ROOT / "dd-feature-development-workflow" / "references" / "state-and-handoff.md"
)
BUG_SKILL = REPO_ROOT / "dd-bug-fix-workflow" / "SKILL.md"
BUG_DIAG = (
    REPO_ROOT / "dd-bug-fix-workflow" / "references" / "diagnosis-and-verification.md"
)
BUG_STATE = REPO_ROOT / "dd-bug-fix-workflow" / "references" / "state.md"
BOOTSTRAP_SKILL = REPO_ROOT / "dd-project-bootstrap-workflow" / "SKILL.md"

TRACKING_NESTED_FIELDS = (
    "provider",
    "repository",
    "issue_number",
    "sync",
    "sync_reason",
    "pending_checkpoint",
    "last_checkpoint_ref",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _slice_section(text: str, level: int, heading: str) -> str:
    """Body of `<level>-dashes> <heading>` up to the next heading of the same
    or higher level. Headings inside fenced code blocks are ignored."""
    head_re = re.compile(rf"^({'#' * level}(?!#)) {re.escape(heading)}[^\n]*$")
    any_head_re = re.compile(r"^(#{1,6}) ")
    lines = text.splitlines()
    start = None
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if start is None:
            if head_re.match(line):
                start = i + 1
        else:
            m = any_head_re.match(line)
            if m and len(m.group(1)) <= level:
                return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"section not found: {heading}")
    return "\n".join(lines[start:])


def h2_section(text: str, heading: str) -> str:
    return _slice_section(text, 2, heading)


def h3_section(text: str, heading: str) -> str:
    return _slice_section(text, 3, heading)


def _table_rows(section_text: str) -> list[str]:
    rows = [line for line in section_text.splitlines() if line.strip().startswith("|")]
    return [
        r
        for r in rows
        if not re.match(r"^\|[\s\-|]+\|$", r.strip()) and "Issue → runtime" not in r and "情形" not in r
    ]


# ---------------------------------------------------------------------------
# Behavioral checks (reused by mutation tests; each raises AssertionError)
# ---------------------------------------------------------------------------


def check_locator_fact_boundary(tt: str) -> None:
    """§1.1: locator metadata may flow Issue→runtime, workflow facts may not."""
    sec = h3_section(tt, "1.1 两类数据的边界")
    rows = _table_rows(sec)
    locator = next((r for r in rows if "定位元数据" in r), None)
    fact = next((r for r in rows if "工作流事实" in r), None)
    assert locator is not None, "boundary table must define the locator row"
    assert fact is not None, "boundary table must define the workflow-fact row"
    assert "允许" in locator, f"locator row must allow the narrow reverse channel: {locator}"
    assert "禁止" in fact, f"fact row must forbid Issue→runtime: {fact}"
    assert "允许" not in fact, f"fact row must not allow Issue→runtime: {fact}"


def check_failure_matrix_allows_workflow(tt: str) -> None:
    """§4: every failure-matrix row must keep the workflow running."""
    sec = h2_section(tt, "4. 绑定失败矩阵")
    rows = _table_rows(sec)
    assert len(rows) >= 5, f"failure matrix must cover >=5 situations, got {len(rows)}"
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        assert cells and cells[-1] == "是", f"failure-matrix row must allow workflow: {row}"


def check_writeback_order(tt: str) -> None:
    """§6.3: persist pending_checkpoint before the remote write, ref after."""
    sec = h3_section(tt, "6.3 写回顺序（crash-safe）")
    block = re.search(r"```text\n(.*?)```", sec, re.S).group(1)
    markers = (
        "原子持久化 checkpoint 源字段",
        "执行远端写回",
        "成功后保存 last_checkpoint_ref",
        "释放写入租约",
    )
    pos = [block.find(m) for m in markers]
    assert all(p >= 0 for p in pos), f"write-back order block is missing steps: {pos}"
    assert pos == sorted(pos), f"write-back steps out of order: {list(zip(markers, pos))}"


def check_no_absolute_paths(tt: str) -> None:
    """Issue fields must never carry machine-local paths."""
    assert "/Users/" not in tt, "contract must not embed absolute paths"
    assert "C:\\" not in tt, "contract must not embed absolute paths"


def check_stage_projection_covers_canonical_stages(tt: str, feature: list[str], bug: list[str]) -> None:
    """§10: every canonical Feature/Bug stage maps exactly once."""
    sec = h2_section(tt, "10. 看板投影")
    block = re.search(r"```text\n(.*?)```", sec, re.S).group(1)
    assert "bug-fix" in block, "projection block must have a bug-fix part"
    feat_part, bug_part = block.split("bug-fix", 1)
    for stage in feature:
        n = len(re.findall(rf"(?<![\w-]){re.escape(stage)}(?![\w-])", feat_part))
        assert n == 1, f"feature stage {stage!r} mapped {n} times (must be exactly 1)"
    for stage in bug:
        n = len(re.findall(rf"(?<![\w-]){re.escape(stage)}(?![\w-])", bug_part))
        assert n == 1, f"bug stage {stage!r} mapped {n} times (must be exactly 1)"


def check_section61_selection_rule(tt: str) -> None:
    """§6.1: frozen latest-checkpoint selection rule (2026-10-02 real-GitHub probe).

    Behavioral on purpose: pagination driver, banned params, full required-field
    validation, workflow filter, dedup, latest-by-comment-id, append-only edit
    policy and machine-checkable counters must all be present and attributed
    to the probe evidence bundle.
    """
    sec = h3_section(tt, "6.1 如何选最新 checkpoint")
    # Evidence provenance (three artifacts, not "session output" hand-waving).
    assert (
        "docs/AI/task-tracking-projection-evidence/L02-checkpoint-probe.md" in sec
    ), "§6.1 must cite the probe evidence document"
    # Pagination: full traversal via Link, not search / not "last marker".
    assert "per_page=100" in sec, "§6.1 must fix the page size"
    assert 'rel="next"' in sec, "§6.1 must require Link-driven pagination"
    assert "全文最后一次 marker" in sec and "不得只按" in sec, "§6.1 must ban last-marker selection"
    # Banned server-side params, with reasons.
    assert "禁用" in sec, "§6.1 must explicitly ban sort/direction and since"
    for banned in ("sort", "direction", "since", "updated_at"):
        assert banned in sec, f"§6.1 must explain the ban covering {banned}"
    # Full required-field validation (recovery-consumed fields), malformed = drop.
    for field in (
        "workflow_id",
        "workflow_type",
        "checkpoint_id",
        "host",
        "state_status",
        "remote",
        "Branch",
        "SHA",
    ):
        assert field in sec, f"§6.1 required-field list must include {field}"
    assert "malformed" in sec, "§6.1 must classify incomplete records as malformed"
    # Workflow scoping + dedup + latest selection keys.
    assert "workflow_id == 当前工作流" in sec, "§6.1 must scope by workflow_id"
    assert "comment id 最小者" in sec and "首次投递" in sec, "§6.1 must dedup to first delivery"
    assert "comment id 最大" in sec, "§6.1 must pick the latest by max comment id"
    # Edit policy: sort key stable ≠ eligibility stable; append-only + re-evaluation.
    assert "append-only" in sec, "§6.1 must declare checkpoint comments append-only"
    assert "重新评估资格" in sec, "§6.1 must re-evaluate eligibility per fetch"
    assert "排序键" in sec, "§6.1 must separate sort-key stability from eligibility"
    # Machine-checkable counters (anti-silent-drop): the six counters must be
    # enumerated as a whole — dropping one (e.g. untrusted) must turn red.
    assert (
        "fetched_total / marker_candidates / malformed / untrusted / after_workflow_filter / duplicates" in sec
    ), "§6.1 must enumerate the six counters in full"
    for counter in ("fetched_total", "marker_candidates", "malformed", "untrusted", "after_workflow_filter", "duplicates"):
        assert counter in sec, f"§6.1 must require the {counter} counter"
    # Source authenticity gate: checkpoint authors must hold repository write access.
    assert "author_association" in sec and "OWNER" in sec, \
        "§6.1 must gate checkpoint authors by write access"


def check_section61_evidence_bundle_exists() -> None:
    """The evidence cited by §6.1 must be a reproducible bundle in-repo, and the
    script must implement the frozen rule (not drift from the contract)."""
    evidence = REPO_ROOT / "docs" / "AI" / "task-tracking-projection-evidence"
    for name in (
        "L02-checkpoint-probe.md",
        "L02-checkpoint-probe.sh",
        "L02-checkpoint-probe-raw-output.md",
    ):
        path = evidence / name
        assert path.is_file(), f"evidence bundle missing artifact: {path}"
    script = (evidence / "L02-checkpoint-probe.sh").read_text(encoding="utf-8")
    assert 'capture("workflow_id' in script, "probe script must contain the selection jq"
    assert '"; "n")' not in script and '"; "n"))' not in script, (
        "probe script must not carry the Oniguruma n-flag regression"
    )
    # The script's end-to-end section must implement the frozen §6.1 rule,
    # not an older 3-field draft (B-R-01: drift must be caught by tests).
    for field in ("workflow_id", "workflow_type", "checkpoint_id", "host", "state_status", "remote", "Branch", "SHA"):
        assert f'"{field}"' in script, f"probe script validation must cover {field}"
    for counter in ("fetched_total", "marker_candidates", "malformed", "after_workflow_filter", "duplicates"):
        assert counter in script, f"probe script must emit the {counter} counter"
    assert "sort_by(.id)[-1]" in script, "probe script must select the latest by max comment id"
    assert "startswith(\"<!-- dd-checkpoint:v1 -->\")" in script, (
        "probe script must filter by the fixed marker prefix"
    )
    # Field validation must not swallow the next field line across a newline
    # (B-R-01: "SHA:" empty followed by "Blocker: none" must be malformed),
    # and the negative sample must be a hard gate in the script.
    assert "issechdr" in script and "sectionkeys" in script, (
        "probe script must parse fields structurally: same-line fields only in the "
        "header region, Branch/SHA as exact section headers (next-line values that "
        "are field lines must be rejected)"
    )
    for gate in (
        "negative_sample_1_sha_empty_then_blocker_valid",
        "negative_sample_2_sha_whitespace_next_line_valid",
        "negative_sample_3_sha_only_in_prose_midline_valid",
        "negative_sample_4_sha_prose_standalone_line_valid",
        "negative_sample_5_sha_in_current_body_canonical_order_violation_valid",
    ):
        assert gate in script, f"probe script must embed the {gate} self-check"
        assert gate + "=false" in (
            evidence / "L02-checkpoint-probe-raw-output.md"
        ).read_text(encoding="utf-8"), f"raw output must record {gate} passing"
    # Raw output must carry both runs, with the refuted v1 conclusion clearly marked.
    raw = (evidence / "L02-checkpoint-probe-raw-output.md").read_text(encoding="utf-8")
    assert "v2 最终版" in raw, "raw output must contain the final v2 run"
    assert "历史初稿" in raw and "已被复审 B-M-02 推翻" in raw, (
        "raw output must mark the v1 'edit stability' conclusion as refuted"
    )


def check_close_rule(tt: str) -> None:
    """§6.5: exactly two legal close entries, each with a fixed order."""
    sec = h3_section(tt, "6.5 Issue 关闭规则")
    entries = re.findall(r"^(\d+)\. (.+)$", sec, re.M)
    assert len(entries) == 2, f"close rule must have exactly 2 entries, got {len(entries)}"
    (_, e1), (_, e2) = entries
    assert "status=completed" in e1, f"entry 1 must be the completed path: {e1}"
    pos1 = [e1.find(m) for m in ("写最终 checkpoint", "同步看板「完成」", "close")]
    assert all(p >= 0 for p in pos1), f"completed close steps missing: {e1}"
    assert pos1 == sorted(pos1), f"completed close order violated: {e1}"
    assert "abandoned" in e2, f"entry 2 must be the abandoned path: {e2}"
    pos2 = [e2.find(m) for m in ("checkpoint", "从看板移出", "close")]
    assert all(p >= 0 for p in pos2), f"abandoned close steps missing: {e2}"
    assert pos2 == sorted(pos2), f"abandoned close order violated: {e2}"
    assert "禁止关闭已绑定 Issue" in sec, "close rule must forbid closing active workflows"
    for token in ("active", "paused", "handoff-ready"):
        assert token in sec, f"close rule must cover {token}"
    assert "不产生任何投影语义" in sec, "external close must not carry projection semantics"


def check_red_lines_close(tt: str) -> None:
    """§13: external close must not be promoted to completion; no direct-close authorization."""
    sec = h2_section(tt, "13. 红线")
    assert "把外部关闭 Issue 当作工作流完成" in sec
    assert "期间关闭已绑定 Issue" in sec
    assert not re.search(r"允许(直接)?关闭已绑定 Issue", sec), \
        "red lines must not authorize closing a bound Issue outside §6.5"


def _bullets(section: str) -> list[str]:
    """List items (`- ` bullets and `1. ` numbered steps) in document order."""
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
            continue
        m = re.match(r"^(\d+)\. (.+)$", stripped)
        if m:
            items.append(m.group(2).strip())
    return items


def _matrix_cells(tt: str) -> list[list[str]]:
    rows = _table_rows(h2_section(tt, "4. 绑定失败矩阵"))
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]


def check_mandatory_attempt_and_record(tt: str) -> None:
    """§2/§3/§3.1/§4/§8.1/§12/§13: feature & bug workflows must complete one
    binding *attempt* and persist its outcome before the Environment Gate.

    Structural, not keyword-existence: reversing the obligation, widening the
    standing authorization, adding an allow-listed action, or flipping a matrix
    row's `sync` value must each turn this red.
    """
    # §2 — obligation, its limit, the bootstrap exemption, and the enum definition.
    sec2 = h2_section(tt, "2. 状态字段")
    assert "必须已完成一次 tracking 绑定尝试" in sec2, "§2 must require a completed attempt"
    assert "未尝试且未记录就通过 Gate 属违规" in sec2, "§2 must forbid passing untried and unrecorded"
    assert "不是\"绑定必须成功\"" in sec2, "§2 must state the rule is attempt-and-record, not a blocking bind"
    for wf in ("feature-development", "bug-fix"):
        assert wf in sec2, f"§2 obligation must cover {wf}"
    assert "第一阶段" in sec2, "§2 exemption must be scoped to bootstrap phase 1"
    assert "remote-unresolvable" in sec2, "§2 must use the same reason token as the §4 matrix"
    for reason in ("user-declined", "binding-ambiguous", "create-outcome-unknown"):
        assert reason in sec2, f"§2 reason vocabulary must include {reason}"
    row_na = next(r for r in _table_rows(sec2) if "not-authorized" in r)
    assert "用户明确拒绝" in row_na, f"§2 not-authorized must cover an explicit user refusal: {row_na}"
    assert "授权条件发生变化前不重试" in row_na, f"§2 not-authorized follow-up must be condition-based: {row_na}"
    row_ns = next(r for r in _table_rows(sec2) if "not-synced" in r)
    assert "可能尚未绑定" in row_ns, f"§2 not-synced must cover pre-bind failures: {row_ns}"
    assert "以 §4 对应 `sync_reason` 为准" in row_ns, \
        f"§2 not-synced must defer retry policy to §4: {row_ns}"

    # §2 — representability: "attempted but unbound" must be expressible in state,
    # otherwise the mandatory attempt-and-record rule cannot be persisted.
    assert "已完成绑定尝试但未形成绑定" in sec2, "§2 must define the attempted-but-unbound variant"
    assert "历史未分类" in sec2 and "§3.2" in sec2, \
        "§2 must keep legacy-null as a third meaning and route it to the migration rule"
    assert "机械判别式" in sec2 and "`schema_version`" in sec2 and ">= 2" in sec2 and "< 2" in sec2, \
        "§2 must give recovery a mechanical discriminator for old vs new null"
    # §2 itself must scope the three-state discrimination to feature/bug: an unscoped
    # rule would give project-bootstrap a different answer than §3.2 / state.md.
    assert "对 `feature-development` 与 `bug-fix`：`tracking` 缺失或 `null`" in sec2, \
        "§2 must scope the null semantics to feature/bug workflows"
    assert "上述两类工作流的新旧 null 机械判别式" in sec2, \
        "§2 must scope the discriminator to the same two workflows"
    assert "不使用上述三态判别" in sec2 and "project-bootstrap" in sec2, \
        "§2 must state that bootstrap does not use the three-state discrimination"
    assert "不得直接当作从未尝试" in sec2, \
        "§2 must forbid reading a legacy null as never-attempted"
    assert "`issue_number` 为 `null`" in sec2, "§2 must express unbound attempts via a null issue_number"
    assert "已尝试未绑定时必须写出该对象" in sec2, "§2 must require writing the attempt outcome"
    for nullable in ("`provider` / `repository`，无法推导时允许为 `null`",
                     "`issue_number` / `last_checkpoint_ref` 保持 `null`"):
        assert nullable in sec2, f"§2 must document nullability: {nullable}"

    # The documented shape must actually be representable: build one canonical
    # pre-bind failure state per §4 reason and validate it against §2's rules.
    pre_bind_reasons = (
        "remote-unresolvable", "no-issue-capable-remote", "provider-unavailable",
        "create-outcome-unknown", "binding-ambiguous", "user-declined", "no-policy",
        "legacy-tracking-unknown",
    )
    matrix_reasons = {cells[2].strip("`") for cells in _matrix_cells(tt) if len(cells) > 2}
    for reason in pre_bind_reasons:
        assert reason in sec2, f"§2 reason vocabulary must include pre-bind reason {reason}"
        assert reason in matrix_reasons, f"§4 must be able to record pre-bind reason {reason}"
    for cells in _matrix_cells(tt):  # reverse direction: §4 → §2 vocabulary
        reason = cells[2].strip("`")
        if reason not in ("—", ""):
            assert reason in sec2, f"§4 reason {reason} is missing from §2 vocabulary"
    for reason in pre_bind_reasons:
        state = {"provider": None, "repository": None, "issue_number": None,
                 "sync": "not-authorized" if reason in ("user-declined", "no-policy") else "not-synced",
                 "sync_reason": reason, "pending_checkpoint": None, "last_checkpoint_ref": None}
        # §2: unbound attempt => issue_number null, outcome recorded, non-blocking
        assert state["issue_number"] is None and state["sync_reason"] == reason, reason
        assert state["sync"] in ("not-synced", "not-authorized"), reason
        assert state["pending_checkpoint"] is None and state["last_checkpoint_ref"] is None, reason

    # §3 — default action, idempotency pointer, authorization pointer, reporting.
    sec3 = h2_section(tt, "3. 绑定规则")
    assert "默认动作是新建" in sec3, "§3 must make Issue creation the default action"
    assert "§3.1" in sec3, "§3 default-create rule must require the idempotency reconcile first"
    assert "§8.1" in sec3, "§3 must point at the narrow standing authorization"
    assert "报告 Issue 号" in sec3, "§3 must require reporting the Issue number"
    assert "只有已绑定" in sec3 and "不得当成既有绑定而跳过对账" in sec3, \
        "§3 reuse rule must be scoped to bound trackings (issue_number != null)"

    # §3.1 — five ordered rules covering the crash windows, not just the happy path.
    sec31 = h3_section(tt, "3.1 创建的幂等与崩溃恢复")
    items = _bullets(sec31)
    assert len(items) == 5, f"§3.1 must define exactly 5 reconcile rules, got {len(items)}"
    assert "先对账再创建" in items[0] and "Workflow ID" in items[0], f"rule 1 must reconcile by Workflow ID: {items[0]}"
    assert "唯一且可信" in items[0], f"rule 1 must require a trustworthy match: {items[0]}"
    assert "§6.1" in items[0] and "association" in items[0], \
        f"rule 1 must reuse the §6.1 trust model instead of inventing one: {items[0]}"
    assert "禁止跳过查证直接重试创建" in items[1], f"rule 2 must forbid blind create retries: {items[1]}"
    assert "零命中不等于未创建" in items[2], f"rule 3 must refuse to treat zero hits as proof: {items[2]}"
    assert "权威对账机制" in items[2] and "create-outcome-unknown" in items[2], \
        f"rule 3 must gate re-creation on authoritative reconciliation: {items[2]}"
    assert "不得把普通搜索的零结果当作" in items[2], \
        f"rule 3 must forbid treating a plain zero-hit search as proof of non-creation: {items[2]}"
    assert "不自动选择" in items[3] and "binding-ambiguous" in items[3], \
        f"rule 4 must fail safe with its own reason: {items[3]}"
    assert "不把裁决当作 Environment Gate 的前置条件" in items[3], \
        f"rule 4 must not make arbitration a Gate precondition: {items[3]}"
    assert "issue-missing" not in items[3], "rule 4 must not reuse the issue-missing reason"
    assert "先原子写入" in items[4] and "再进行" in items[4], f"rule 5 must persist the binding first: {items[4]}"

    # §3.2 — legacy state migration: a pre-contract `tracking: null` must never be
    # upgraded into "never attempted" (which would auto-create on recovery).
    sec32 = h3_section(tt, "3.2 旧 state 中 `tracking` 缺失或 `null` 的迁移")
    items32 = _bullets(sec32)
    assert len(items32) == 5, f"§3.2 must define exactly 5 migration rules, got {len(items32)}"
    assert "机械判别" in items32[0] and "`schema_version`" in items32[0], \
        f"rule 1 must scope the legacy window mechanically: {items32[0]}"
    assert "不依据 `current_stage`" in items32[0], \
        f"rule 1 must forbid inferring the version from the stage: {items32[0]}"
    assert "不解释为从未尝试" in items32[1] and "legacy-tracking-unknown" in items32[1], \
        f"rule 2 must classify legacy null without strengthening it: {items32[1]}"
    assert "只读对账优先" in items32[2] and "仅执行 §3.1 规则 1 中的只读检索" in items32[2], \
        f"rule 3 must scope reconciliation to §3.1 rule 1 read-only part: {items32[2]}"
    assert "不得进入 §3.1 的创建动作" in items32[2], \
        f"rule 3 must forbid entering the create action: {items32[2]}"
    assert "零命中后仍不得创建" in items32[3], f"rule 4 must not create on a zero-hit reconcile: {items32[3]}"
    assert "§8.1 的常设授权与 §3 的\"默认动作是新建\"都不足以从该状态触发创建" in items32[3], \
        f"rule 4 must state that the standing authorization cannot unlock a legacy state: {items32[3]}"
    assert "当前用户明确要求创建" in items32[3] and "项目政策明确解除" in items32[3], \
        f"rule 4 must name the explicit unlock facts: {items32[3]}"
    assert "重新落盘" in items32[4] or "重新持久化" in items32[4], \
        f"rule 5 must re-persist under the current model: {items32[4]}"
    assert "`schema_version` 升为 `2`" in items32[4], \
        f"rule 5 must bump schema_version so the next recovery leaves the legacy branch: {items32[4]}"
    # The migration note in the upper-level state docs must itself be scoped to
    # feature/bug: bootstrap inheriting a Feature/Bug-only rule is a contract fork.
    # Scoped to the SENTENCE that mentions the migration, not the whole document.
    for name, doc in (("state.md", read(RUNTIME_STATE)), ("runtime-contract.md", read(RUNTIME_CONTRACT))):
        blocks = [b for b in re.split(r"\n\s*\n", doc) if "§3.2" in b]
        assert len(blocks) == 1, f"{name} must have exactly one migration paragraph, got {len(blocks)}"
        migration = blocks[0]
        assert "feature-development" in migration and "bug-fix" in migration, \
            f"{name} migration paragraph must name the workflow types it applies to"
        assert "project-bootstrap" in migration, \
            f"{name} migration paragraph must state the bootstrap exemption"
    # The shared schema note must say bootstrap may keep writing schema 1, so a
    # version difference is not later mistaken for a missed sync.
    assert "可以继续写 `schema_version: 1`" in read(RUNTIME_STATE), \
        "state.md must state that bootstrap intentionally stays on schema 1"
    # The v2 null-semantics SENTENCE itself must be feature/bug-scoped. Checking only
    # the migration paragraph is not enough: an unscoped first sentence would give
    # bootstrap a different answer than task-tracking §2.
    for name, doc, version in (("state.md", read(RUNTIME_STATE), '"schema_version": 2'),
                               ("runtime-contract.md", read(RUNTIME_CONTRACT), "schema_version: 2")):
        assert version in doc, f"{name} must declare {version}"
        head = next(b for b in re.split(r"\n\s*\n", doc) if version in b)
        assert ("feature-development" in head and "bug-fix" in head), \
            f"{name} v2 null-semantics statement must be scoped to feature/bug: {head[:80]}"
        assert "project-bootstrap" in head, \
            f"{name} v2 null-semantics statement must exclude bootstrap explicitly: {head[:80]}"
    # Discriminator fixtures: the three (schema_version, tracking) combinations that
    # recovery must classify differently. Classification reads schema_version only.
    # Order matters and mirrors §2: an existing tracking object is classified by
    # `issue_number` FIRST (bound / attempted-but-unbound) in either version; only a
    # missing-or-null tracking falls back to the schema_version discriminator.
    def classify_feature_bug_tracking(schema_version, tracking):
        """Mirrors §2 for feature-development / bug-fix ONLY. project-bootstrap does
        not use this three-state discrimination (§2 / §3.2), so it is not modelled."""
        if isinstance(tracking, dict):
            if tracking.get("issue_number") is not None:
                return "bound"                     # bound in either version → reuse
            return "attempted-unbound"             # object exists, not bound → §3.1/§4
        if schema_version is None or schema_version < 2:
            return "legacy"                        # historical null → §3.2 read-only
        return "never-attempted"                   # current contract null → create path

    unbound = {"issue_number": None, "sync": "not-synced", "sync_reason": "provider-unavailable"}
    assert classify_feature_bug_tracking(1, None) == "legacy", "schema<2 + null must classify as legacy"
    assert classify_feature_bug_tracking(None, None) == "legacy", "missing schema_version must read as legacy"
    assert classify_feature_bug_tracking(2, None) == "never-attempted", "schema 2 + null must be a first attempt"
    assert classify_feature_bug_tracking(1, {"issue_number": 116}) == "bound", "legacy + bound must reuse normally"
    assert classify_feature_bug_tracking(2, {"issue_number": 116}) == "bound", "current + bound must reuse normally"
    # An object with issue_number=null is attempted-but-unbound in BOTH versions —
    # it must never fall into the never-attempted branch (which would auto-create),
    # nor be demoted to legacy by an old schema number (§3.2 covers null tracking only).
    assert classify_feature_bug_tracking(2, dict(unbound)) == "attempted-unbound", \
        "schema 2 + unbound object must not be re-read as never-attempted"
    assert classify_feature_bug_tracking(1, dict(unbound)) == "attempted-unbound", \
        "an unbound object is not demoted to legacy by an old schema number"
    assert "不解释为从未尝试" in sec32, "legacy classification must not strengthen the old state"

    # §4 — exact (sync, sync_reason) tuples for the creation-related rows.
    rows = _matrix_cells(tt)
    by_scenario = {cells[0]: cells for cells in rows}
    expected = {
        "用户明确要求不创建 Issue": ("not-authorized", "user-declined"),
        "同一 `Workflow ID` 命中多张 Issue": ("not-synced", "binding-ambiguous"),
        "创建结果不确定且无权威对账结论": ("not-synced", "create-outcome-unknown"),
        "无 Issue 能力的远端（remote 指向未登记的 provider）": ("not-synced", "no-issue-capable-remote"),
        "认证/权限不足或 provider 不可用": ("not-synced", "provider-unavailable"),
        "旧 state 的 `tracking` 缺失或 `null`（历史未分类，见 §3.2）": ("not-synced", "legacy-tracking-unknown"),
    }
    for scenario, (sync, reason) in expected.items():
        assert scenario in by_scenario, f"§4 must cover scenario: {scenario}"
        cells = by_scenario[scenario]
        assert cells[1].strip("`") == sync, f"{scenario}: sync must be {sync}, got {cells[1]}"
        assert cells[2].strip("`") == reason, f"{scenario}: sync_reason must be {reason}, got {cells[2]}"
        assert cells[4] == "否", f"{scenario}: recorded failure must not ASK, got {cells[4]}"
    # Retry column is action-level: an uncertain create may only re-verify, never re-create.
    retry_unknown = by_scenario["创建结果不确定且无权威对账结论"][3]
    assert "仅重试权威对账" in retry_unknown, f"retry must stay limited to reconciliation: {retry_unknown}"
    assert "不得重试 create" in retry_unknown, f"retry must forbid re-creating: {retry_unknown}"
    legacy_retry = by_scenario["旧 state 的 `tracking` 缺失或 `null`（历史未分类，见 §3.2）"][3]
    assert "仅只读对账" in legacy_retry and "不得据旧 `null` 自动创建" in legacy_retry, \
        f"legacy null retry must stay read-only: {legacy_retry}"
    for scenario in ("项目未授权", "用户明确要求不创建 Issue"):
        assert "授权条件变化后重新评估" in by_scenario[scenario][3], \
            f"{scenario}: not-authorized retry must be condition-based: {by_scenario[scenario][3]}"
    for cells in rows:
        assert cells[-1] == "是", f"failure-matrix row must not block the workflow: {cells}"

    # §8.1 — standing authorization is narrow: exactly one allow-listed action, explicit denies.
    sec81 = h3_section(tt, "8.1 创建 tracking Issue 的常设授权（窄范围）")
    allow_text, deny_text = sec81.split("**不包含**", 1)
    allow_items = _bullets(allow_text.split("授权范围**仅限**", 1)[1])
    assert len(allow_items) == 1, f"§8.1 must allow exactly one action, got {allow_items}"
    assert "创建 1 张 Issue" in allow_items[0], f"§8.1 allow list must be Issue creation: {allow_items[0]}"
    for guarded in ("checkpoint 评论", "§6.5 关闭", "§10 看板投影", "labels", "assignees",
                    "open/reopen", "commit", "push", "PR", "merge", "force-push", "发布"):
        assert guarded in deny_text, f"§8.1 must explicitly exclude {guarded}"
    for bullet in _bullets(deny_text):
        assert not bullet.startswith("允许"), \
            f"§8.1 exclusion list must not contain an granting item: {bullet}"
    assert "runtime-contract.md) §7" in sec81, "§8.1 must cite the upper-level authorization source"
    assert "user-declined" in sec81 and "disabled" in sec81, "§8.1 must separate user-declined from disabled"
    assert "不主动创建 Issue" not in tt, \
        "the pre-2026-10-02 prohibition must be removed once the attempt is mandatory"

    # §12 / §13 — exemption scope and the red line.
    sec12 = h2_section(tt, "12. 与相邻 Skill 的边界")
    assert "均不适用于 project-bootstrap 整个工作流" in sec12, \
        "§12 must exempt bootstrap from the attempt rule and the standing authorization"
    assert "其第一阶段另明确不自动创建/绑定/投影" in sec12, \
        "§12 must keep the bootstrap phase-1 opt-out explicit"
    sec13 = h2_section(tt, "13. 红线")
    assert "就通过 Environment Gate" in sec13 and "必须尝试并记录" in sec13, \
        "§13 must forbid passing the Gate untried and unrecorded"
    assert "首次创建常设授权" in sec13, "§13 must keep the standing authorization out of wider Git scope"


def check_external_action_authorization_source(rc: str) -> None:
    """runtime-contract §7: the narrow standing authorization must be a listed
    authorization source, and must stay bounded."""
    sec7 = h2_section(rc, "7. Stage Contract")
    assert "窄范围常设授权" in sec7, "runtime §7 must list narrow standing authorizations as a source"
    assert "不得据此扩大" in sec7, "runtime §7 must forbid widening a standing authorization"


# Structural rule (primary protection): inside a consumer's Environment section,
# exactly two lines may touch tracking — the call-site hook and the Gate
# persistence clause — and each must have the canonical shape. Any extra
# tracking-flavoured line (new rule, failure handling, creation policy) is a
# restatement and turns this red, whatever wording it uses.
_TRACKING_TOKENS = ("task-tracking", "tracking", "绑定", "Issue", "sync", "同步")

# Canonical shapes: the hook and the Gate clause are locked verbatim, so a rule
# appended INSIDE an otherwise well-formed hook cannot slip through the line count.
CANONICAL_HOOK = (
    "- Environment Gate 前执行 [task-tracking](../../dd-workflow-runtime/references/task-tracking.md) "
    "§3 定义的 tracking 绑定尝试，并按该合同持久化结果；tracking 对本 Stage 的影响完全由该合同定义，"
    "**不阻塞本 Stage**。"
)
CANONICAL_GATE_CLAUSE = "tracking 绑定尝试的结果已按 owner 合同持久化；"
# Feature lists the Gate clause as its own bullet; bug-fix inlines it in the Gate
# line; bug SKILL.md carries one router sentence. All three are locked verbatim so
# an appended clause of any punctuation style is caught.
CANONICAL_GATE_BULLET = "- " + CANONICAL_GATE_CLAUSE
CANONICAL_BUG_GATE_LINE = (
    "Gate：Bug state 原子写入，" + CANONICAL_GATE_CLAUSE + "`current_stage=diagnosis-and-repair`。"
)
CANONICAL_BUG_ROUTER_LINE = (
    "Bug 工作流与 Feature 对等：在 Environment（worktree 与分支确定后、Environment Gate 前）执行 "
    "[task-tracking](../dd-workflow-runtime/references/task-tracking.md) §3 定义的 tracking 绑定尝试并按该合同持久化结果，"
    "**不阻塞本 Stage**；`bug_id` 不重载为 Issue 号，跨设备任务索引用共享 `tracking` 字段承载。"
)


def _gate_block(section: str) -> str:
    """The `Gate：` block inside an already section-scoped string."""
    assert "Gate：" in section, "section must carry a Gate block"
    return section.split("Gate：", 1)[1]


def _tracking_lines(section: str) -> list[str]:
    return [ln.strip() for ln in section.splitlines() if any(t in ln for t in _TRACKING_TOKENS)]


def check_consumers_delegate_tracking(envs: dict, gates: dict, skill: str) -> None:
    """Consumers keep only the call site: one canonical hook plus one canonical Gate
    clause, delegating every semantic to the owner and staying non-blocking."""
    for name, env in envs.items():
        lines = _tracking_lines(env)
        assert len(lines) == 2, (
            f"{name}: Environment must contain exactly the tracking hook and the Gate "
            f"persistence clause, got {len(lines)}: {lines}"
        )
        hook, gate_clause = lines
        assert hook == CANONICAL_HOOK, (
            f"{name} hook must be exactly the canonical call site (owner semantics belong "
            f"to task-tracking.md):\n  actual:   {hook}\n  expected: {CANONICAL_HOOK}"
        )
        expected_gate = CANONICAL_GATE_BULLET if name == "feature intake" else CANONICAL_BUG_GATE_LINE
        assert gate_clause == expected_gate, (
            f"{name} Gate line must be exactly the canonical form (owner result semantics "
            f"belong to task-tracking.md):\n  actual:   {gate_clause}\n  expected: {expected_gate}"
        )
    for name, gate in gates.items():
        assert "持久化" in gate, f"{name} Gate must require the owner-defined result to be persisted"
    # Bug State section: the canonical router sentence must be the ONLY sentence in
    # its paragraph, and no other paragraph may state a task-creation rule. This
    # catches rules appended in their own paragraph with no tracking keywords.
    bug_state = skill.split("## Bug State", 1)[1].split("\n## ", 1)[0]
    paragraphs = [p.strip() for p in bug_state.split("\n\n") if p.strip()]
    canonical_paragraphs = [p for p in paragraphs if p == CANONICAL_BUG_ROUTER_LINE]
    assert len(canonical_paragraphs) == 1, (
        "bug SKILL.md Bug State must contain the canonical router sentence verbatim as its "
        f"own paragraph; got {paragraphs}"
    )
    for para in paragraphs:
        if para == CANONICAL_BUG_ROUTER_LINE:
            continue
        for verb in ("新建", "创建", "远端工单", "任务卡"):
            assert verb not in para, (
                f"bug SKILL.md Bug State must not state its own task-creation rule "
                f"({verb}): {para[:60]}"
            )


# ---------------------------------------------------------------------------
# Canonical stage extraction (drift detection: new stages must be mapped)
# ---------------------------------------------------------------------------


def feature_canonical_stages() -> list[str]:
    skill = read(REPO_ROOT / "dd-feature-development-workflow" / "SKILL.md")
    m = re.search(r"固定 Stage 顺序：\s*```text\n(.*?)```", skill, re.S)
    assert m, "feature SKILL.md must declare the fixed stage order"
    return re.findall(r"[a-z][a-z0-9-]*", m.group(1))


def bug_canonical_stages() -> list[str]:
    state = read(BUG_STATE)
    m = re.search(r"```text\n((?:\d+ → [a-z][a-z0-9-]*\n)+)```", state)
    assert m, "bug state.md must carry the legacy step mapping"
    return [line.split("→")[1].strip() for line in m.group(1).strip().splitlines()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOwnershipAndStructure(unittest.TestCase):
    def test_task_tracking_linked_from_runtime_skill(self):
        self.assertIn(
            "references/task-tracking.md",
            read(RUNTIME_SKILL),
            "runtime SKILL.md must route to the task-tracking reference",
        )

    def test_state_schema_version_carries_tracking_narrowing(self):
        """schema 2 is the mechanical discriminator §3.2 relies on; state.md must
        document it, otherwise recovery cannot tell a legacy null from a fresh one."""
        state = read(RUNTIME_STATE)
        self.assertIn('"schema_version": 2', state, "state.md example must declare schema 2")
        self.assertIn("§3.2", state, "state.md must route historical nulls to the migration rule")
        self.assertIn("不得反向解释成从未尝试", state,
                      "state.md must forbid reinterpreting a legacy null as never-attempted")
        contract = read(RUNTIME_CONTRACT)
        self.assertIn("schema_version: 2", contract, "runtime State Schema example must declare schema 2")

    def test_tracking_nested_schema_single_owner(self):
        contract = read(RUNTIME_CONTRACT)
        # schema 2 是本次 tracking null 语义收窄的载体（§3.2 依赖它做机械判别）。
        schema_block = re.search(r"```yaml\nschema_version: 2\n.*?```", contract, re.S).group(0)
        self.assertIn("tracking: null", schema_block)
        for nested in ("issue_number", "sync_reason", "pending_checkpoint", "last_checkpoint_ref"):
            self.assertNotIn(
                nested,
                schema_block,
                f"{nested} must be owned by task-tracking.md, not the runtime schema",
            )
        self.assertIn("task-tracking.md", contract, "runtime contract must link the owner")
        for path in (RUNTIME_STATE, FEATURE_STATE, BUG_STATE):
            text = read(path)
            for nested in ("issue_number", "sync_reason", "pending_checkpoint"):
                self.assertNotIn(nested, text, f"{path.name} must not duplicate tracking fields")
        tt = read(TASK_TRACKING)
        tt_schema = re.search(r"```yaml\ntracking:\n.*?```", tt, re.S).group(0)
        for field in TRACKING_NESTED_FIELDS:
            self.assertIn(field, tt_schema)

    def test_no_duplicated_runtime_enums(self):
        tt = read(TASK_TRACKING)
        self.assertIn("原样消费", tt, "checkpoint fields must consume canonical runtime vocab")
        self.assertNotRegex(tt, r"trae.{0,8}codex.{0,8}other", "host vocab must not be re-listed")
        self.assertNotRegex(
            tt, r"active.{0,4}paused.{0,4}handoff-ready", "status vocab must not be re-listed"
        )

    def test_runtime_recovery_uses_locator_metadata_only(self):
        sec = h2_section(read(RUNTIME_CONTRACT), "5. Recovery")
        self.assertIn("定位元数据", sec)
        self.assertIn("不得取自 Issue", sec)
        self.assertIn("task-tracking.md", sec)

    def test_runtime_schema_declares_optional_tracking(self):
        contract = read(RUNTIME_CONTRACT)
        self.assertIn("不得作为任何 Gate 依据", contract)


class TestBehavioralContracts(unittest.TestCase):
    def test_locator_vs_fact_boundary(self):
        check_locator_fact_boundary(read(TASK_TRACKING))

    def test_tracking_never_blocks_gate(self):
        tt = read(TASK_TRACKING)
        self.assertIn("不得阻塞任何 Workflow Gate", tt)
        check_failure_matrix_allows_workflow(tt)

    def test_not_authorized_is_action_scoped(self):
        sec = h2_section(read(TASK_TRACKING), "8. 授权")
        self.assertIn("只停止该远端 tracking 动作", sec)
        self.assertIn("后续 Workflow Stage 继续", sec)
        self.assertNotRegex(sec, r"未授权[^\n]{0,12}停止工作流")

    def test_checkpoint_is_not_evidence(self):
        sec = h2_section(read(TASK_TRACKING), "7. checkpoint 不是证据")
        self.assertIn("不等于", sec)
        self.assertIn("candidate_sha", sec)

    def test_writeback_order_is_crash_safe(self):
        tt = read(TASK_TRACKING)
        check_writeback_order(tt)
        self.assertIn("pending_checkpoint", h2_section(tt, "2. 状态字段"))

    def test_checkpoint_template_fields(self):
        sec = h2_section(read(TASK_TRACKING), "6. 进度用 checkpoint 评论")
        block = re.search(r"```text\n(.*?)```", sec, re.S).group(1)
        for field in (
            "workflow_id:",
            "checkpoint_id:",
            "host:",
            "executor:",
            "stage:",
            "state_status:",
            "remote:",
            "Branch:",
            "SHA:",
            "Next:",
            "Blocker:",
            "Taken over from:",
        ):
            self.assertIn(field, block, f"checkpoint template must carry {field}")
        self.assertIn("不参与 Gate 与恢复判定", sec, "executor must be display-only")
        self.assertIn("不写入 runtime state", sec, "executor must stay out of state")

    def test_no_absolute_paths_in_issue_fields(self):
        check_no_absolute_paths(read(TASK_TRACKING))

    def test_transport_agnostic(self):
        sec = h2_section(read(TASK_TRACKING), "11. 传输层")
        self.assertIn("gh CLI", sec)
        self.assertIn("不得把", sec)
        self.assertIn("MCP", sec)


class TestMandatoryBindingAttempt(unittest.TestCase):
    """2026-10-02: feature/bug workflows must complete one tracking binding attempt
    and persist its outcome before the Environment Gate. Success is not a Gate
    precondition — recorded failures stay non-blocking — but silence is a red line."""

    def test_owner_contract_states_attempt_and_record(self):
        check_mandatory_attempt_and_record(read(TASK_TRACKING))

    def test_runtime_contract_lists_standing_authorization_source(self):
        check_external_action_authorization_source(read(RUNTIME_CONTRACT))

    def test_consumers_delegate_without_restating(self):
        feature_env = h2_section(read(FEATURE_INTAKE), "2. Environment")
        bug_env = h2_section(read(BUG_DIAG), "2. Environment")
        check_consumers_delegate_tracking(
            {"feature intake": feature_env, "bug diagnosis": bug_env},
            {"feature Environment": _gate_block(feature_env),
             "bug Environment": _gate_block(bug_env)},
            read(BUG_SKILL),
        )

    def test_bootstrap_stays_exempt(self):
        self.assertIn("不自动创建", read(BOOTSTRAP_SKILL))
        sec12 = h2_section(read(TASK_TRACKING), "12. 与相邻 Skill 的边界")
        self.assertIn("均不适用于 project-bootstrap 整个工作流", sec12)


class TestCrossMachineTakeover(unittest.TestCase):
    def setUp(self):
        self.sec = h2_section(read(TASK_TRACKING), "9. 跨机器恢复与接管")

    def test_takeover_requires_handoff_ready(self):
        self.assertIn("state_status=handoff-ready", self.sec)
        self.assertIn("active` 不得静默接管", self.sec)

    def test_takeover_conflict_detected(self):
        self.assertIn("同一来源", self.sec)
        self.assertIn("BLOCKED", self.sec)

    def test_old_holder_stops_after_takeover(self):
        self.assertIn("停止写入", self.sec)

    def test_no_mutual_exclusion_claim(self):
        sec = h3_section(read(TASK_TRACKING), "9.3 接管规则（碰撞检测，不是互斥）")
        self.assertIn("冲突检测", sec)
        self.assertIn("不提供互斥", sec)
        self.assertIn("compare-and-set", sec)

    def test_local_only_not_handoff_ready(self):
        sec = h3_section(read(TASK_TRACKING), "9.2 工作内容可达性（任务可发现 ≠ 工作内容可恢复）")
        self.assertIn("local-only", sec)
        self.assertIn("不得宣称 handoff-ready", sec)
        self.assertIn("不得扩大 push 授权", sec)

    def test_branch_visibility_not_inferred(self):
        sec = h3_section(read(TASK_TRACKING), "9.2 工作内容可达性（任务可发现 ≠ 工作内容可恢复）")
        self.assertIn("agentShared", sec)
        self.assertIn("推定为 shared", sec)


class TestProjectionAndRouting(unittest.TestCase):
    def test_stage_projection_covers_all_stages(self):
        tt = read(TASK_TRACKING)
        check_stage_projection_covers_canonical_stages(
            tt, feature_canonical_stages(), bug_canonical_stages()
        )

    def test_projection_table_single_owner(self):
        offenders = []
        for path in sorted(REPO_ROOT.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT)
            parts = rel.parts
            if any(p.startswith(".") for p in parts):
                continue
            if "docs" in parts or "tests" in parts:
                continue
            if path == TASK_TRACKING:
                continue
            if re.search(r"→ (开发中|待验证|待收尾)", read(path)):
                offenders.append(str(rel))
        self.assertEqual(offenders, [], f"stage→board mapping leaked outside its owner: {offenders}")

    def test_feature_and_bug_both_have_binding_hook(self):
        feat = h2_section(read(FEATURE_INTAKE), "2. Environment")
        self.assertIn("task-tracking", feat)
        self.assertIn("不阻塞本 Stage", feat)
        self.assertLess(
            feat.find("验证工作区状态与基线"),
            feat.find("task-tracking"),
            "feature hook must sit after workspace verification",
        )
        self.assertLess(feat.find("task-tracking"), feat.find("Gate："))
        bug = h2_section(read(BUG_DIAG), "2. Environment")
        self.assertIn("task-tracking", bug)
        self.assertIn("不阻塞本 Stage", bug)
        self.assertLess(
            bug.find("fix_branch"), bug.find("task-tracking"),
            "bug hook must sit after the workspace record block",
        )
        self.assertLess(bug.find("task-tracking"), bug.find("Gate："))
        self.assertIn("tracking", read(BUG_SKILL))

    def test_bootstrap_opt_out_declared(self):
        text = read(BOOTSTRAP_SKILL)
        for token in ("不自动创建", "不自动绑定", "不自动投影", "task-tracking"):
            self.assertIn(token, text)


class TestSection61Selection(unittest.TestCase):
    """§6.1 frozen latest-checkpoint selection rule (L-02 probe, 2026-10-02)."""

    def test_selection_rule_is_frozen_and_complete(self):
        check_section61_selection_rule(read(TASK_TRACKING))

    def test_section61_is_no_longer_pending(self):
        sec = h3_section(read(TASK_TRACKING), "6.1 如何选最新 checkpoint")
        self.assertNotIn("待取证", sec, "§6.1 heading/status must not regress to pending")
        self.assertNotIn("尚未冻结", sec)

    def test_evidence_bundle_is_reproducible(self):
        check_section61_evidence_bundle_exists()


class TestCloseRule(unittest.TestCase):
    """LATER-20261002: closing a bound Issue is only legal at completion or abandonment."""

    def test_close_has_exactly_two_legal_entries_with_fixed_order(self):
        check_close_rule(read(TASK_TRACKING))

    def test_abandoned_board_disposition_is_unique(self):
        sec = h2_section(read(TASK_TRACKING), "10. 看板投影")
        self.assertIn("从看板移出", sec)
        self.assertIn("不得进入「完成」", sec)

    def test_policy_template_binds_close_to_65(self):
        sec = h2_section(read(TASK_TRACKING), "8. 授权")
        self.assertIn("§6.5 两个合法入口", sec)

    def test_board_does_not_follow_issue_state(self):
        sec = h2_section(read(TASK_TRACKING), "10. 看板投影")
        self.assertIn("不跟随 Issue 的 open/closed 状态", sec)
        self.assertIn("投影脱节", sec)
        self.assertIn("§6.5", sec)

    def test_red_lines_cover_external_close(self):
        check_red_lines_close(read(TASK_TRACKING))

    def test_state_md_status_vocab_follows_canonical(self):
        sec = h3_section(read(RUNTIME_STATE), "通用字段（所有工作流必需）")
        self.assertIn("runtime-contract.md", sec)
        self.assertIn("abandoned", sec)


GUARD_TEMPLATE = REPO_ROOT / "dd-workflow-runtime" / "templates" / "github" / "checkpoint-close-guard.yml"
SELECT_SCRIPT = REPO_ROOT / "dd-workflow-runtime" / "scripts" / "checkpoint_select.py"

MARKER_CHECKPOINT = "<!-- dd-checkpoint:v1 -->"
MARKER_GUARD = "<!-- dd-close-guard:v1 -->"


def make_checkpoint(cid: int, *, state: str, cp_id: str, wf: str = "wf-a",
                    complete: bool = True,
                    author_association: str = "OWNER") -> dict:
    """按 §6 模板形状构造探针评论（complete=False 时省略全部必填字段）。"""
    lines = [MARKER_CHECKPOINT, ""]
    if complete:
        for key, value in (
            ("workflow_id", wf),
            ("workflow_type", "feature-development"),
            ("checkpoint_id", cp_id),
            ("host", "codex"),
            ("state_status", state),
            ("remote", "sha-reachable"),
        ):
            lines.append(f"{key}: {value}")
    lines += ["", "Current:", "probe body.", "", "Next:", "n/a.", "",
              "Branch:", "feature/x", "", "SHA:", "abc123", "",
              "Blocker:", "none", "", "Taken over from:", "none"]
    return {"id": cid, "body": "\n".join(lines), "author_association": author_association}


def run_select(comments_text: str, workflow_id: str | None = None,
               author_associations: str | None = None) -> dict:
    """执行 canonical 选取脚本（checkpoint_select.py）并解析 KEY=VALUE 输出。"""
    cmd = [sys.executable, str(SELECT_SCRIPT)]
    if workflow_id is not None:
        cmd += ["--workflow-id", workflow_id]
    if author_associations is not None:
        cmd += ["--author-associations", author_associations]
    proc = subprocess.run(cmd, input=comments_text, capture_output=True, text=True)
    assert proc.returncode == 0, f"select script failed: {proc.stderr}"
    out: dict = {}
    for line in proc.stdout.strip().splitlines():
        if line.startswith("fetched_total="):
            for kv in line.split():
                key, _, value = kv.partition("=")
                out[key] = int(value)
        else:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def check_guard_template(yml: str) -> None:
    """§6.5 机械防线模板：处置只依赖 canonical 选取脚本，reopen 用合法命令。"""
    assert "types: [closed]" in yml, "guard must trigger on issue close"
    assert "pull_request == null" in yml, "PR closes must be ignored"
    assert "checkpoint_select.py" in yml, "guard must delegate selection to the canonical script"
    assert "--workflow-id" in yml, "guard must pass the binding workflow-id (§6.1 step 3)"
    assert "--author-associations" in yml, "guard must enable the author authenticity gate (§6.1 step 8)"
    assert '--author-associations "OWNER,COLLABORATOR,MEMBER"' in yml, \
        "guard allowlist must be pinned exactly to OWNER,COLLABORATOR,MEMBER"
    assert "Workflow ID:" in yml, "binding source must be the issue body Workflow ID line"
    assert "gh issue reopen" in yml, "guard must reopen with the legal gh subcommand"
    assert "gh issue edit --reopen" not in yml, "--reopen is not a valid gh issue edit flag (CG-M-01)"
    assert MARKER_GUARD in yml, "guard comments must carry the dedupe marker"
    assert "actions/checkout@v4" in yml, "select script comes from the installed repository"
    case_block = yml.split('case "$selected_state" in', 1)[1].split("esac", 1)[0]
    assert "completed" in case_block and "abandoned" in case_block, \
        "both terminal states must skip intervention"


# --- 模板可安装性（结构层）-----------------------------------------------------
# 2026-10-02 事故：模板把 `run: |` 块内的两段内嵌 python 与 heredoc 写在第 0 列，
# 提前终止块标量 → GitHub 无法解析 → 每次 push 都产生 0 job 的失败 run，防线从未生效。
# 原有 check_guard_template 全是字符串存在检查，看不出这类结构损坏，故补下列机械门。


def _block_scalar_of_run(yml: str) -> tuple[int, list[str]]:
    """返回 (`run: |` 块基准缩进, 块内容行)。

    基准取 `run: |` 之后**首个非空内容行**的缩进（YAML 语义），并要求严格大于
    `run: |` 自身的缩进；块内容到首个缩进 ≤ `run: |` 缩进的非空行为止——不假设
    `run: |` 是文件最后一个节点。
    """
    lines = yml.splitlines(keepends=True)
    idx = next(i for i, l in enumerate(lines) if l.strip() == "run: |")
    run_indent = len(lines[idx]) - len(lines[idx].lstrip(" "))
    rest = lines[idx + 1:]
    first = next(i for i, l in enumerate(rest) if l.strip())
    base = len(rest[first]) - len(rest[first].lstrip(" "))
    assert base > run_indent, (
        f"块标量首个内容行缩进 {base} 必须大于 `run: |` 缩进 {run_indent}；"
        "否则块标量立即终止，YAML 解析失败（防线静默失效）"
    )
    end = next(
        (i for i, l in enumerate(rest[first:], start=first)
         if l.strip() and (len(l) - len(l.lstrip(" "))) <= run_indent),
        len(rest),
    )
    return base, rest[:end]


def _strip_block(block: list[str], base: int) -> str:
    return "".join(l[base:] if l.startswith(" " * base) else l for l in block)


def check_guard_template_is_installable(yml: str) -> None:
    """模板必须**结构上可安装**：块标量内每行缩进不低于基准，剥离后是合法 shell，
    且 heredoc 终止符恰好落在 shell 第 0 列。"""
    base, block = _block_scalar_of_run(yml)
    for offset, line in enumerate(block, 1):
        if not line.strip():
            continue
        lead = len(line) - len(line.lstrip(" "))
        assert lead >= base, (
            f"run 块内第 {offset} 行缩进 {lead} < 块基准 {base}：会提前终止块标量，"
            f"GitHub 解析失败（防线静默失效）→ {line.strip()[:60]}"
        )
    script = _strip_block(block, base)
    proc = subprocess.run(["bash", "-n"], input=script, capture_output=True, text=True)
    assert proc.returncode == 0, f"run 块剥离后不是合法 shell：{proc.stderr[:200]}"
    # `bash -n` 对未闭合 heredoc 只 warning 并返回 0，故显式禁止该 warning。
    assert "here-document" not in proc.stderr, (
        f"bash 报告 heredoc 未闭合：{proc.stderr.strip()[:200]}"
    )
    # 本模板的评论体用 `<<MSG` heredoc：终止符必须在剥离后恰好位于列 0，否则 shell
    # 不再把它当终止符（防「YAML 合法但 heredoc 悬空」这一类绕过）。
    assert script.count("<<MSG") == 1, "guard 评论应恰好使用一个 <<MSG heredoc"
    assert [l for l in script.splitlines() if l.strip() == "MSG"] == ["MSG"], (
        "heredoc 终止符 MSG 必须在剥离后恰好位于 shell 第 0 列"
    )


def check_guard_embedded_python_parses(yml: str) -> None:
    """内嵌 `python3 -c "…"` 片段必须**恰好两段**且都能被解析
    （重排缩进时最容易悄悄改坏嵌套；只断言「至少一段」会被单段丢失绕过）。"""
    base, block = _block_scalar_of_run(yml)
    script = _strip_block(block, base)
    snippets = re.findall(r'python3 -c "\n(.*?)\n"', script, re.S)
    assert len(snippets) == 2, f"guard 应恰好含两段内嵌 python，实际 {len(snippets)} 段"
    for i, snippet in enumerate(snippets, 1):
        try:
            ast.parse(snippet)
        except SyntaxError as exc:  # pragma: no cover - 失败路径即本测试的目的
            raise AssertionError(f"内嵌 python 第 {i} 段语法错误：{exc}") from exc



class TestCheckpointSelect(unittest.TestCase):
    """§6.1 选取的执行级测试（canonical 脚本 + fixture 驱动，非关键词检查）。"""

    def run_select(self, text: str, workflow_id: str | None = None,
                   author_associations: str | None = None) -> dict:
        return run_select(text, workflow_id, author_associations)

    def test_valid_completed_selected_with_counts(self):
        out = self.run_select(json.dumps([make_checkpoint(1, state="completed", cp_id="cp-1")]))
        self.assertEqual(out["selected_state"], "completed")
        self.assertEqual(out["selected_id"], "1")
        self.assertEqual(
            (out["fetched_total"], out["marker_candidates"], out["malformed"],
             out["after_workflow_filter"], out["duplicates"]),
            (1, 1, 0, 1, 0),
        )

    def test_latest_wins_by_comment_id(self):
        comments = json.dumps([
            make_checkpoint(1, state="completed", cp_id="cp-1"),
            make_checkpoint(2, state="active", cp_id="cp-2"),
        ])
        out = self.run_select(comments)
        self.assertEqual((out["selected_id"], out["selected_state"]), ("2", "active"))

    def test_malformed_marker_only_dropped(self):
        comments = json.dumps([
            make_checkpoint(1, state="active", cp_id="cp-1"),
            {"id": 2, "body": MARKER_CHECKPOINT + "\n\n伪造：无任何必填字段。"},
        ])
        out = self.run_select(comments)
        self.assertEqual((out["selected_id"], out["selected_state"]), ("1", "active"))
        self.assertEqual(out["malformed"], 1)

    def test_prose_state_status_cannot_qualify(self):
        forged = make_checkpoint(2, state="completed", cp_id="cp-2", complete=False)
        forged["body"] = forged["body"].replace(
            "Current:\nprobe body.", "Current:\n例行核对（state_status: completed 仅为正文提及）"
        )
        comments = json.dumps([make_checkpoint(1, state="active", cp_id="cp-1"), forged])
        out = self.run_select(comments)
        self.assertEqual((out["selected_id"], out["selected_state"]), ("1", "active"))
        self.assertEqual(out["malformed"], 1)

    def test_duplicate_checkpoint_id_takes_first_delivery(self):
        comments = json.dumps([
            make_checkpoint(1, state="active", cp_id="cp-x"),
            make_checkpoint(2, state="completed", cp_id="cp-x"),
            make_checkpoint(3, state="completed", cp_id="cp-y"),
        ])
        out = self.run_select(comments)
        self.assertEqual(out["duplicates"], 1)
        self.assertEqual((out["selected_id"], out["selected_state"]), ("3", "completed"))

    def test_paginated_concatenated_and_slurped_pages_flatten(self):
        page1 = [make_checkpoint(1, state="active", cp_id="cp-1")]
        page2 = [make_checkpoint(2, state="completed", cp_id="cp-2")]
        self.assertEqual(
            self.run_select(json.dumps(page1) + json.dumps(page2))["selected_id"], "2"
        )
        self.assertEqual(
            self.run_select(json.dumps([page1, page2]))["selected_id"], "2"
        )

    def test_workflow_filter_excludes_other_workflows(self):
        comments = json.dumps([
            make_checkpoint(1, state="active", cp_id="cp-1", wf="other-wf"),
            make_checkpoint(2, state="completed", cp_id="cp-2", wf="wf-a"),
        ])
        out = self.run_select(comments, workflow_id="wf-a")
        self.assertEqual(out["after_workflow_filter"], 1)
        self.assertEqual(out["selected_id"], "2")

    def test_untrusted_author_dropped(self):
        comments = json.dumps([
            make_checkpoint(1, state="active", cp_id="cp-1", author_association="OWNER"),
            make_checkpoint(2, state="completed", cp_id="cp-2",
                            author_association="NONE"),
        ])
        out = self.run_select(comments, author_associations="OWNER,COLLABORATOR,MEMBER")
        self.assertEqual((out["selected_id"], out["selected_state"]), ("1", "active"))
        self.assertEqual(out["untrusted"], 1)

    def test_untrusted_gate_off_keeps_everything(self):
        comments = json.dumps([
            make_checkpoint(1, state="active", cp_id="cp-1", author_association="NONE"),
        ])
        out = self.run_select(comments)
        self.assertEqual(out["selected_state"], "active")
        self.assertEqual(out["untrusted"], 0)


class TestCloseGuardTemplate(unittest.TestCase):
    def test_guard_template_is_wired_to_contract(self):
        check_guard_template(read(GUARD_TEMPLATE))
        check_guard_template_is_installable(read(GUARD_TEMPLATE))
        check_guard_embedded_python_parses(read(GUARD_TEMPLATE))

    def test_guard_referenced_from_contract_65(self):
        sec = h3_section(read(TASK_TRACKING), "6.5 Issue 关闭规则")
        self.assertIn("checkpoint-close-guard.yml", sec)
        self.assertIn("scripts/dd/checkpoint_select.py", sec)
        self.assertIn("不改变任何 Gate", sec)

    def test_guard_fails_safe_on_legacy_cards(self):
        sec = h3_section(read(TASK_TRACKING), "6.5 Issue 关闭规则")
        self.assertIn("fail-safe 跳过", sec)
        self.assertIn("不做跨 workflow 判定", sec)


class TestCloseGuardIntegration(unittest.TestCase):
    """执行级集成门：抽取 guard 模板的 run 块，用假 gh + fixture 实际运行。

    证明（CG-M-04）：guard 真的把 Issue 正文 Workflow ID 传给 §6.1 选取
    （--workflow-id），并且处置与绑定工作流的 checkpoint 状态一致。
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(__import__("tempfile").mkdtemp(prefix="dd-guard-test-"))
        cls.bin_dir = cls.tmp / "bin"
        cls.bin_dir.mkdir()
        script_dir = cls.tmp / "scripts" / "dd"
        script_dir.mkdir(parents=True)
        script_dir.joinpath("checkpoint_select.py").write_text(
            SELECT_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        fake_gh = cls.bin_dir / "gh"
        fake_gh.write_text(
            "#!/usr/bin/env bash\n"
            'case "$*" in\n'
            '  *--paginate*) cat "$GUARD_COMMENTS_FIXTURE" ;;\n'
            '  *"issues/$GUARD_ISSUE"*) cat "$GUARD_ISSUE_FIXTURE" ;;\n'
            '  *reopen*) echo REOPEN >> "$GUARD_CALLS" ;;\n'
            '  *comment*) echo COMMENT >> "$GUARD_CALLS" ;;\n'
            '  *) echo "OTHER: $*" >> "$GUARD_CALLS" ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_guard(self, issue_body: str, comments: list) -> tuple[int, str]:
        import os
        import subprocess

        calls = self.tmp / f"calls-{len(list(self.tmp.glob('calls-*')))}.log"
        comments_fixture = self.tmp / f"comments-{calls.stem}.json"
        issue_fixture = self.tmp / f"issue-{calls.stem}.json"
        comments_fixture.write_text(json.dumps(comments), encoding="utf-8")
        issue_fixture.write_text(json.dumps({"number": 111, "body": issue_body}), encoding="utf-8")
        run_block = read(GUARD_TEMPLATE).split("run: |", 1)[1]
        import textwrap

        run_script = textwrap.dedent(run_block)
        script_path = self.tmp / "run-guard.sh"
        script_path.write_text(run_script, encoding="utf-8")
        script_path.chmod(0o755)
        env = dict(
            os.environ,
            PATH=f"{self.bin_dir}:{os.environ['PATH']}",
            GUARD_COMMENTS_FIXTURE=str(comments_fixture),
            GUARD_ISSUE_FIXTURE=str(issue_fixture),
            GUARD_CALLS=str(calls),
            GUARD_ISSUE="111",
            ISSUE="111",
            REPO="marcocpt/Macim",
            GH_TOKEN="test-token",
        )
        proc = subprocess.run(
            ["bash", str(script_path)], capture_output=True, text=True, env=env, cwd=self.tmp
        )
        return proc.returncode, calls.read_text(encoding="utf-8") if calls.exists() else ""

    def issue_fixture_body(self, workflow_id: str | None) -> str:
        body = "## Workflow\n\nType: feature-development\n"
        if workflow_id is not None:
            body += f"Workflow ID: {workflow_id}\n"
        return body + "\nBranch: feature/x\n"

    def test_foreign_completed_cannot_allow_close_of_active_workflow(self):
        comments = [
            make_checkpoint(100, state="active", cp_id="cp-1", wf="wf-a"),
            make_checkpoint(101, state="completed", cp_id="cp-2", wf="other-wf"),
        ]
        code, calls = self.run_guard(self.issue_fixture_body("wf-a"), comments)
        self.assertEqual(code, 0)
        self.assertIn("REOPEN", calls, "cross-workflow completed must not allow close")
        self.assertNotIn("OTHER", calls)

    def test_bound_completed_close_is_legal(self):
        comments = [make_checkpoint(101, state="completed", cp_id="cp-2", wf="wf-a")]
        code, calls = self.run_guard(self.issue_fixture_body("wf-a"), comments)
        self.assertEqual(code, 0)
        self.assertNotIn("REOPEN", calls)

    def test_legacy_card_without_workflow_id_fails_safe(self):
        comments = [make_checkpoint(100, state="active", cp_id="cp-1", wf="wf-a")]
        code, calls = self.run_guard(self.issue_fixture_body(None), comments)
        self.assertEqual(code, 0)
        self.assertNotIn("REOPEN", calls)


class TestMutations(unittest.TestCase):
    """§6.6: minimal semantic tampering must turn the checks red."""

    def test_fact_row_flip_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace("**禁止**，只能由仓库证据重建", "**允许**，只能由仓库证据重建")
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_locator_fact_boundary(mutated)

    def test_matrix_cell_flip_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "| 用户明确禁用 | `disabled` | — | 否 | 否 | 是 |",
            "| 用户明确禁用 | `disabled` | — | 否 | 否 | 否 |",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_failure_matrix_allows_workflow(mutated)

    def test_order_swap_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "2. 执行远端写回\n3. 成功后保存 last_checkpoint_ref，清除 pending_checkpoint",
            "2. 成功后保存 last_checkpoint_ref，清除 pending_checkpoint\n3. 执行远端写回",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_writeback_order(mutated)

    def test_close_rule_relaxation_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace("禁止关闭已绑定 Issue", "允许直接关闭已绑定 Issue")
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_close_rule(mutated)

    def test_third_close_entry_insertion_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "→ 把对应卡片从看板移出（archive item）→ close。",
            "→ 把对应卡片从看板移出（archive item）→ close。\n3. 用户明确要求时直接 close。",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_close_rule(mutated)

    def test_abandoned_branch_order_swap_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "→ 把对应卡片从看板移出（archive item）→ close。",
            "→ close → 把对应卡片从看板移出（archive item）。",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_close_rule(mutated)

    def test_red_line_conflict_insertion_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "- 把 `paused` 当成阻塞；",
            "- 把 `paused` 当成阻塞；\n- 在工作流 active 期间允许直接关闭已绑定 Issue；",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_red_lines_close(mutated)

    def test_guard_reopen_command_regression_is_caught(self):
        yml = read(GUARD_TEMPLATE)
        mutated = yml.replace("gh issue reopen", "gh issue edit --reopen")
        self.assertNotEqual(mutated, yml, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_guard_template(mutated)

    def test_guard_abandoned_removal_is_caught(self):
        yml = read(GUARD_TEMPLATE)
        mutated = yml.replace("completed|abandoned)", "completed)")
        self.assertNotEqual(mutated, yml, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_guard_template(mutated)

    def test_section61_required_field_drop_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace("、`Branch`、`SHA`。缺任一判", "。缺任一判")
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_section61_selection_rule(mutated)

    def test_section61_since_unban_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace("**禁用** `sort`/`direction` 与 `since`", "可选 `sort`/`direction` 与 `since`")
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_section61_selection_rule(mutated)

    def test_section61_counter_drop_is_caught(self):
        tt = read(TASK_TRACKING)
        mutated = tt.replace(
            "`fetched_total / marker_candidates / malformed / untrusted / after_workflow_filter / duplicates` 六个计数",
            "`fetched_total / marker_candidates / malformed / after_workflow_filter / duplicates` 五个计数",
        )
        self.assertNotEqual(mutated, tt, "mutation target string must exist")
        with self.assertRaises(AssertionError):
            check_section61_selection_rule(mutated)


class TestVocabularyDrift(unittest.TestCase):
    """T-70~T-73: the mechanical validator must not become a second source of truth.

    The validator needs concrete `sync` values and `sync_reason` codes to decide
    anything, but this file owns them. These checks bind the two in both
    directions: a value added to either side without the other fails.
    Extraction failures FAIL — they must never `skip`, or an owner restructure
    would silently turn this guard green (Design §3.4).
    """

    VALIDATOR = REPO_ROOT / "dd-workflow-runtime" / "agents" / "validate-tracking-binding.py"

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "validate_tracking_binding", cls.VALIDATOR)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    # -- owner-side extraction ------------------------------------------------

    def _table_rows(self, block: str) -> list[list[str]]:
        rows = []
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            if set(line) <= set("|-: "):
                continue
            rows.append([c.strip() for c in line.strip("|").split("|")])
        self.assertTrue(rows, "owner table must have rows")
        return rows

    @staticmethod
    def _code(cell: str) -> str | None:
        m = re.fullmatch(r"`([a-z0-9\-]+)`", cell.strip())
        return m.group(1) if m else None

    def owner_sync_values(self) -> set[str]:
        """§2 enum table, first column."""
        block = _slice_section(read(TASK_TRACKING), 2, "2. 状态字段")
        values = {self._code(r[0]) for r in self._table_rows(block)}
        values.discard(None)
        self.assertTrue(values, "could not extract sync values from §2 — guard must FAIL")
        return values

    def owner_sync_reasons(self) -> set[str]:
        """§4 failure matrix, sync_reason column."""
        block = _slice_section(read(TASK_TRACKING), 2, "4. 绑定失败矩阵")
        rows = self._table_rows(block)
        header = rows[0]
        for col in ("`sync`", "`sync_reason`"):
            self.assertIn(col, header, f"§4 header changed, cannot locate {col} — guard must FAIL")
        idx = header.index("`sync_reason`")
        values = {self._code(r[idx]) for r in rows[1:]}
        values.discard(None)
        self.assertTrue(values, "could not extract sync_reason values from §4 — guard must FAIL")
        return values

    def owner_outcomes(self) -> set[tuple[str, str | None]]:
        """§4 failure matrix, (sync, sync_reason) pairs — the rows' own shape.

        §4 pairs each sync value with specific reasons; the pairing is owner-owned
        semantics, so it is locked separately from the flat vocabularies.
        """
        block = _slice_section(read(TASK_TRACKING), 2, "4. 绑定失败矩阵")
        rows = self._table_rows(block)
        header = rows[0]
        i_sync, i_reason = header.index("`sync`"), header.index("`sync_reason`")
        pairs = {(self._code(r[i_sync]), self._code(r[i_reason])) for r in rows[1:]}
        pairs.discard((None, None))
        self.assertTrue(pairs, "could not extract (sync, sync_reason) pairs — guard must FAIL")
        return pairs

    def owner_providers(self) -> set[str]:
        """§2: the provider value the contract registers."""
        block = _slice_section(read(TASK_TRACKING), 2, "2. 状态字段")
        m = re.search(r"^\s*provider:\s*(\S+)", block, re.M)
        self.assertIsNotNone(m, "§2 must declare a provider value — guard must FAIL")
        return {m.group(1).strip("`")}

    def owner_tracking_fields(self) -> set[str]:
        """§2 yaml block declaring the nested schema."""
        block = _slice_section(read(TASK_TRACKING), 2, "2. 状态字段")
        m = re.search(r"```yaml\ntracking:\n(.*?)```", block, re.S)
        self.assertIsNotNone(m, "§2 must declare the tracking schema block — guard must FAIL")
        return set(re.findall(r"^\s{2}([a-z_]+):", m.group(1), re.M))

    # -- T-70~T-73 -----------------------------------------------------------

    def test_t70_sync_values_match_in_both_directions(self):
        owner = self.owner_sync_values()
        validator = set(self.mod.SYNC_VALUES)
        self.assertEqual(validator, owner,
                         "validator SYNC_VALUES drifted from task-tracking §2 "
                         f"(owner-only={sorted(owner - validator)}, "
                         f"validator-only={sorted(validator - owner)})")

    def test_t71_validator_covers_every_owner_reason(self):
        owner = self.owner_sync_reasons()
        validator = set(self.mod.SYNC_REASONS)
        self.assertFalse(
            owner - validator,
            "task-tracking §4 gained a sync_reason the validator does not accept: "
            f"{sorted(owner - validator)}")

    def test_t72_validator_invents_no_reason(self):
        owner = self.owner_sync_reasons()
        validator = set(self.mod.SYNC_REASONS)
        self.assertFalse(
            validator - owner,
            "validator accepts sync_reason codes absent from task-tracking §4: "
            f"{sorted(validator - owner)}")

    def test_t73_validator_field_names_are_owned(self):
        owner = self.owner_tracking_fields()
        validator = set(self.mod.TRACKING_FIELDS)
        self.assertFalse(
            validator - owner,
            "validator reads tracking fields task-tracking §2 does not declare: "
            f"{sorted(validator - owner)}")

    def test_self_recording_sync_matches_owner_rows(self):
        """§4 spells `synced`/`disabled` with `—` for sync_reason; the validator
        must treat exactly those as self-recording, or it would fail a state the
        owner explicitly permits (FR-6)."""
        block = _slice_section(read(TASK_TRACKING), 2, "4. 绑定失败矩阵")
        rows = self._table_rows(block)
        header = rows[0]
        i_sync, i_reason = header.index("`sync`"), header.index("`sync_reason`")
        no_reason = {self._code(r[i_sync]) for r in rows[1:]
                     if self._code(r[i_sync]) and self._code(r[i_reason]) is None}
        self.assertEqual(set(self.mod.SELF_RECORDING_SYNC), no_reason,
                         "self-recording sync values drifted from §4's "
                         "no-reason rows")

    def test_t74_outcome_pairs_match_owner_in_both_directions(self):
        owner = self.owner_outcomes()
        validator = set(self.mod.RECORDED_OUTCOMES)
        self.assertEqual(
            validator, owner,
            "validator RECORDED_OUTCOMES drifted from task-tracking §4 pairs "
            f"(owner-only={sorted(owner - validator)}, "
            f"validator-only={sorted(validator - owner)})")

    def test_t75_provider_matches_owner(self):
        owner = self.owner_providers()
        validator = set(self.mod.SUPPORTED_PROVIDERS)
        self.assertEqual(
            validator, owner,
            f"validator SUPPORTED_PROVIDERS drifted from task-tracking §2 "
            f"(owner={sorted(owner)}, validator={sorted(validator)})")

    def owner_mandatory_workflow_types(self) -> set[str]:
        """§2's own enumeration of the types under the constraint.

        Read from the clause that introduces them, and every backticked kebab-case
        token in it is treated as a type — so a third type added tomorrow is
        picked up. Hardcoding today's two values inside the regex would make the
        lock blind to exactly the change it exists to catch.
        """
        tt = read(TASK_TRACKING)
        anchor = re.search(r"对\s*`([^`]+)`\s*与\s*`([^`]+)`\s*工作流", tt)
        self.assertIsNotNone(anchor,
                             "could not locate §2's enumeration of mandatory workflow "
                             "types — guard must FAIL")
        # Bound the span at 工作流: the same sentence continues with sync/sync_reason
        # and the bootstrap carve-out, which are not workflow types.
        end = tt.index("工作流", anchor.start())
        span = tt[anchor.start():end]
        types = set(re.findall(r"`([a-z][a-z0-9-]+)`", span))
        self.assertTrue(types, "could not extract mandatory workflow types — guard must FAIL")
        return types

    def owner_exempt_workflow_types(self) -> set[str]:
        """§12's row that disclaims the §2 constraint."""
        sec12 = _slice_section(read(TASK_TRACKING), 2, "12. 与相邻 Skill 的边界")
        exempt = set()
        for row in self._table_rows(sec12):
            if "不适用" not in row[-1]:
                continue
            for name in re.findall(r"`dd-([a-z-]+-workflow)`", row[0]):
                exempt.add(name.removesuffix("-workflow"))
        self.assertTrue(exempt, "could not extract the exempt workflow — guard must FAIL")
        return exempt

    def owner_legacy_boundary_expression(self) -> str:
        """How §3.2 spells the legacy boundary."""
        tt = read(TASK_TRACKING)
        m = re.search(r"`< (\d+)`", tt)
        self.assertIsNotNone(m,
                             "could not locate §3.2's legacy boundary expression — "
                             "guard must FAIL")
        return m.group(0)

    def test_t77_legacy_schema_boundary_is_owned(self):
        """§3.2 writes the boundary as `< 2`. The validator keeps every non-negative
        version below the current one and rejects negatives outright, which is a
        deliberate narrowing: a negative schema version is meaningless, and reading
        it as legacy let a never-attempted state pass (external review round 3).

        This is therefore a relation, not an equality with the literal `< 2`.
        """
        self.assertEqual(self.owner_legacy_boundary_expression(), "`< 2`",
                         "task-tracking §3.2's legacy boundary expression changed")
        legacy = set(self.mod.LEGACY_SCHEMA_VERSIONS)
        current = self.mod.CURRENT_SCHEMA_VERSION
        self.assertEqual(legacy, set(range(current)),
                         "every non-negative schema version below the current one is "
                         "legacy, and none at or above it")
        for negative in (-1, -2, -100):
            self.assertNotIn(negative, legacy,
                             "negatives must be rejected, never treated as legacy")

    def test_t76_mandatory_workflow_types_are_owned(self):
        self.assertEqual(set(self.mod.MANDATORY_WORKFLOW_TYPES),
                         self.owner_mandatory_workflow_types(),
                         "validator MANDATORY_WORKFLOW_TYPES drifted from task-tracking §2")
        self.assertEqual(set(self.mod.EXEMPT_WORKFLOW_TYPES),
                         self.owner_exempt_workflow_types(),
                         "validator EXEMPT_WORKFLOW_TYPES drifted from task-tracking §12")

class TestVocabularyDriftMutations(unittest.TestCase):
    """The drift guard must actually turn red on semantic tampering.

    TestVocabularyDrift was implemented before this test existed (the validator's
    constants were already module-level), so it has no natural red phase of its
    own. These mutations supply that evidence: each one edits the validator or the
    owner contract in memory and requires the guard to fail. A guard that cannot
    be made to fail is not a guard.
    """

    def setUp(self):
        self.v_path = TestVocabularyDrift.VALIDATOR
        self.tt_path = TASK_TRACKING
        self.v_src = read(self.v_path)
        self.tt_src = read(self.tt_path)

    def _guard_fails(self, v_src, tt_src, expect_tests: tuple[str, ...]) -> bool:
        """Run TestVocabularyDrift against patched sources; True when it fails.

        The owner's extraction helpers read the module-global TASK_TRACKING, so
        the patch redirects that global at a temp copy and restores it after.

        `wasSuccessful()` alone is not enough: a SyntaxError in the mutated
        validator, an import error in setUpClass, or any unrelated exception would
        also make the run unsuccessful and be mistaken for "the guard caught it".
        This requires zero errors, at least one failure, and that *every* failure
        is one of the expected drift assertions. Requiring only "at least one
        expected failure" would let an unrelated assertion fail alongside it and
        still report the mutation as caught.
        """
        globals()["TASK_TRACKING_ORIGINAL"] = globals()["TASK_TRACKING"]
        original_validator = TestVocabularyDrift.VALIDATOR
        with tempfile.TemporaryDirectory() as tmp:
            v_file = Path(tmp) / "validate-tracking-binding.py"
            t_file = Path(tmp) / "task-tracking.md"
            v_file.write_text(v_src, encoding="utf-8")
            t_file.write_text(tt_src, encoding="utf-8")
            try:
                globals()["TASK_TRACKING"] = t_file
                TestVocabularyDrift.VALIDATOR = v_file
                suite = unittest.TestLoader().loadTestsFromTestCase(TestVocabularyDrift)
                result = unittest.TextTestRunner(
                    stream=io.StringIO(), verbosity=0).run(suite)
            finally:
                globals()["TASK_TRACKING"] = globals().pop("TASK_TRACKING_ORIGINAL")
                TestVocabularyDrift.VALIDATOR = original_validator

        if result.errors:
            self.fail(f"mutation produced errors, not assertion failures "
                      f"(unrelated breakage): {result.errors}")
        failed = {str(t).rsplit(".", 1)[-1] for t, _ in result.failures}
        if not failed:
            return False
        unexpected = {n for n in failed
                      if not any(n.startswith(prefix) for prefix in expect_tests)}
        self.assertFalse(
            unexpected,
            f"guard must fail only on the expected assertions; unrelated failures "
            f"also fired: {sorted(unexpected)} (expected one of {expect_tests})")
        return True

    def test_m1_validator_invents_a_sync_value(self):
        mutated = self.v_src.replace(
            'SYNC_VALUES = frozenset({"synced", "not-synced", "not-authorized", "disabled"})',
            'SYNC_VALUES = frozenset({"synced", "not-synced", "not-authorized", "disabled", "partial"})')
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t70",)), "M1 not caught")

    def test_m2_validator_invents_a_sync_reason(self):
        mutated = self.v_src.replace(
            '"provider-unavailable",\n})', '"provider-unavailable",\n    "totally-made-up",\n})')
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t72",)), "M2 not caught")

    def test_m3_owner_gains_a_reason_the_validator_lacks(self):
        mutated = self.tt_src.replace(
            "| 认证/权限不足或 provider 不可用 | `not-synced` | `provider-unavailable`",
            "| 认证/权限不足或 provider 不可用 | `not-synced` | `provider-unavailable` |\n"
            "| 新增情形 | `not-synced` | `brand-new-reason` |")
        self.assertNotEqual(mutated, self.tt_src, "mutation target must exist")
        self.assertTrue(
            self._guard_fails(self.v_src, mutated, ("test_t71", "test_t74")),
            "M3 not caught — owner-side drift is the direction that matters most")

    def test_m4_validator_reads_an_undeclared_field(self):
        mutated = self.v_src.replace(
            '"provider", "repository", "issue_number",',
            '"provider", "repository", "issue_number", "secret_extra",')
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t73",)), "M4 not caught")

    def test_m5_self_recording_set_drifts(self):
        mutated = self.v_src.replace('    ("disabled", None),\n', "")
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(
            self._guard_fails(mutated, self.tt_src,
                              ("test_t74", "test_self_recording")),
            "M5 not caught — dropping `disabled` would fail a state §4 permits")

    def test_m6_validator_invents_an_outcome_pair(self):
        mutated = self.v_src.replace(
            '    ("not-synced", "provider-unavailable"),\n})',
            '    ("not-synced", "provider-unavailable"),\n'
            '    ("not-authorized", "issue-missing"),\n})')
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t74",)),
                        "M6 not caught — an unlisted cross-pair must be rejected")

    def test_m7_validator_drops_a_provider(self):
        mutated = self.v_src.replace('SUPPORTED_PROVIDERS = frozenset({"github"})',
                                     'SUPPORTED_PROVIDERS = frozenset()')
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t75",)), "M7 not caught")
    def test_m8_owner_gains_a_third_mandatory_workflow_type(self):
        mutated = self.tt_src.replace(
            "对 `feature-development` 与 `bug-fix` 工作流",
            "对 `feature-development` 与 `bug-fix` 与 `release` 工作流")
        self.assertNotEqual(mutated, self.tt_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(self.v_src, mutated, ("test_t76",)),
                        "M8 not caught — a new mandatory type must reach the validator")

    def test_m9_owner_moves_the_legacy_boundary(self):
        mutated = self.tt_src.replace("`< 2`", "`< 3`")
        self.assertNotEqual(mutated, self.tt_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(self.v_src, mutated, ("test_t77",)),
                        "M9 not caught — the legacy boundary must be re-checked by hand")

    def test_m10_validator_widens_the_legacy_set(self):
        mutated = self.v_src.replace("LEGACY_SCHEMA_VERSIONS = frozenset({0, 1})",
                                     "LEGACY_SCHEMA_VERSIONS = frozenset({0, 1, 2})")
        self.assertNotEqual(mutated, self.v_src, "mutation target must exist")
        self.assertTrue(self._guard_fails(mutated, self.tt_src, ("test_t77",)),
                        "M10 not caught — swallowing the current schema as legacy")


class TestEntrypointReachability(unittest.TestCase):
    """FR-1/FR-2/FR-10: the attempt must be obligatory *from the entry file*.

    A consumer's Stage reference already carries the call site (locked above by
    check_consumers_delegate_tracking). That was not enough: an Agent reading only
    the entry SKILL.md never saw the obligation, so nothing was ever attempted and
    no Issue was ever created. These checks pin the obligation where first-read
    surfaces are: the Stage table/paragraph an Agent consults, plus a red line.

    Token presence alone would be satisfied by "无需按 task-tracking §3 创建 Issue"
    or by moving the attempt after the Gate, so the predicate asserts polarity (a
    mandate, not an option) and timing (after the environment is known, before the
    Gate) instead of raw substrings.
    """

    # A pass requires the owner link, an explicit action, and mandate wording.
    OBLIGATION = ("task-tracking", "§3")
    ACTION = ("创建", "Issue")

    # Wording that would invert or void the obligation. A blacklist can always be
    # extended, so the mandate itself is matched positively (see MANDATE below)
    # and these only add readable diagnostics.
    NEGATIONS = ("无需", "不必", "非必须", "可以不", "不得创建", "禁止", "尽量", "最好")

    # A negated mandate still contains 必须 ("不是必须", "并非要求必须"). These
    # prefixes are what make 必须 not a mandate, so they are checked before the
    # bare 必须 is accepted.
    NEGATING_PREFIXES = ("不是必须", "并非必须", "并非要求必须", "不是要求必须",
                         "可以选择是否必须", "不再必须", "未必须")

    # Softeners that replace a mandate without being plain negations.
    PROHIBITED_MANDATES = ("应当", "应该", "宜", "鼓励")

    # Timing that would place the attempt outside the Environment Gate.
    BAD_TIMING = ("Gate 后", "Gate 之后", "Stage 之前", "阶段之前", "进入 Environment 前")

    # §8.1 authorizes creating the first Issue only. Naming checkpoint/close/board
    # would imply an authorization that does not exist.
    OVER_BROAD = ("checkpoint", "关闭", "看板")

    FEATURE_SKILL = REPO_ROOT / "dd-feature-development-workflow" / "SKILL.md"

    # -- predicate -----------------------------------------------------------

    # Split on the separators that end a clause, so mandate/action/timing must all
    # live in ONE tracking clause. Aggregating over the whole Environment row would
    # let an unrelated sentence's 必须 (e.g. "恢复任务…必须复用") stand in for the
    # tracking mandate, and "建议按 task-tracking §3 创建 Issue" would still pass.
    CLAUSE_SPLIT = re.compile(r"[；;。\n]")

    @classmethod
    def tracking_clause(cls, text: str) -> str | None:
        """The clause that names the owner contract and an Issue, if any."""
        for clause in cls.CLAUSE_SPLIT.split(text):
            if "task-tracking" in clause and "§3" in clause and "Issue" in clause:
                return clause
        return None

    @classmethod
    def obligation_problem(cls, text: str) -> str | None:
        """Return why `text` fails to state a mandatory, correctly-timed attempt."""
        clause = cls.tracking_clause(text)
        if clause is None:
            return ("no single clause names task-tracking §3 and an Issue; the obligation "
                    "must be stated in one place, not assembled from separate sentences")
        for token in cls.ACTION:
            if token not in clause:
                return f"tracking clause missing action token {token!r}"
        for token in cls.NEGATIONS:
            if token in clause:
                return f"obligation is negated by {token!r}"
        for prefix in cls.NEGATING_PREFIXES:
            if prefix in clause:
                return f"mandate is negated by {prefix!r}"
        for token in cls.PROHIBITED_MANDATES:
            if token in clause:
                return f"obligation is not a mandate ({token!r})"
        if not re.search(r"(?<!不)(?<!非)必须", clause):
            return "tracking clause has no positive 必须 mandate"
        for token in cls.BAD_TIMING:
            if token in clause:
                return f"attempt is placed outside the Gate by {token!r}"
        if "Gate 前" not in clause and "Gate 之前" not in clause:
            return "tracking clause does not anchor to the Environment Gate deadline"
        for token in cls.OVER_BROAD:
            if token in clause:
                return f"implies authorization for {token!r}"
        return None

    # -- extraction ----------------------------------------------------------

    @staticmethod
    def _feature_environment_row() -> str:
        text = read(TestEntrypointReachability.FEATURE_SKILL)
        rows = [ln for ln in text.splitlines() if ln.strip().startswith("| Environment |")]
        assert rows, "feature SKILL.md must keep an Environment row in its Stage table"
        return rows[0]

    @staticmethod
    def _bug_environment_section() -> str:
        text = read(BUG_SKILL)
        assert "### Environment" in text, "bug SKILL.md must keep an Environment stage section"
        return text.split("### Environment", 1)[1].split("\n### ", 1)[0]

    @staticmethod
    def _runtime_preflight() -> str:
        text = read(RUNTIME_SKILL)
        assert "## Preflight" in text, "runtime SKILL.md must keep a Preflight section"
        return text.split("## Preflight", 1)[1].split("\n## ", 1)[0]

    @staticmethod
    def _red_lines(text: str) -> str:
        assert "## 红线" in text, "entry must keep a red-lines section"
        return text.split("## 红线", 1)[1]

    # -- T-01/T-02/T-03: feature entry --------------------------------------

    def test_t01_feature_environment_row_states_the_obligation_and_action(self):
        row = self._feature_environment_row()
        self.assertIsNone(self.obligation_problem(row),
                          f"feature Environment row: {self.obligation_problem(row)}")

    def test_t02_obligation_is_not_only_in_the_trailing_router_list(self):
        text = read(self.FEATURE_SKILL)
        router = text.split("- 外部任务绑定与投影", 1)
        self.assertEqual(len(router), 2, "feature SKILL.md must keep its trailing router entry")
        self.assertIsNotNone(
            self.obligation_problem(router[1]),
            "the trailing router list is reference material, not the Stage instruction")

    def test_t03_feature_red_line_covers_skipping_the_attempt(self):
        red = self._red_lines(read(self.FEATURE_SKILL))
        lines = [ln for ln in red.splitlines() if "Environment Gate" in ln and "§3" in ln]
        self.assertTrue(lines, "feature red lines must forbid passing the Environment Gate untried")

    # -- T-04/T-05/T-06: bug entry ------------------------------------------

    def test_t04_bug_environment_section_states_the_obligation_and_action(self):
        section = self._bug_environment_section()
        self.assertIsNone(self.obligation_problem(section),
                          f"bug Environment section: {self.obligation_problem(section)}")

    def test_t05_bug_red_line_covers_skipping_the_attempt(self):
        red = self._red_lines(read(BUG_SKILL))
        lines = [ln for ln in red.splitlines() if "Environment Gate" in ln and "§3" in ln]
        self.assertTrue(lines, "bug red lines must forbid passing the Environment Gate untried")

    def test_t06_bug_obligation_is_not_in_the_locked_bug_state_section(self):
        # ## Bug State holds exactly one canonical router paragraph (no creation
        # verb) and is locked verbatim by check_consumers_delegate_tracking. The
        # obligation belongs in ## Stage 路由 / ### Environment.
        text = read(BUG_SKILL)
        state_section = text.split("## Bug State", 1)[1].split("\n## ", 1)[0]
        for verb in ("创建", "新建", "远端工单", "任务卡"):
            self.assertNotIn(verb, state_section,
                             f"## Bug State must not carry a task-creation obligation "
                             f"({verb}); it belongs in ### Environment")

    # -- T-07/T-08: runtime entry -------------------------------------------

    def test_t07_runtime_preflight_requires_the_attempt(self):
        preflight = self._runtime_preflight()
        self.assertIsNone(self.obligation_problem(preflight),
                          f"runtime Preflight: {self.obligation_problem(preflight)}")
        self.assertIn("validate-tracking-binding", preflight,
                      "runtime Preflight must require the deterministic Gate check")

    def test_t08_preflight_keeps_the_owner_link(self):
        self.assertIn("references/task-tracking.md", self._runtime_preflight(),
                      "the new obligation item must link the owner, not replace the "
                      "recovery-path link already present")

    # -- T-09/T-10: state representation ------------------------------------

    def test_t09_state_template_reserves_a_tracking_slot(self):
        state = read(RUNTIME_STATE)
        block = re.search(r"```json\n(.*?)```", state, re.S)
        self.assertIsNotNone(block, "state.md must keep a json state template")
        self.assertIn('"tracking"', block.group(1),
                      "the state template must reserve a slot for the attempt result, "
                      "otherwise a first-time writer produces a state with nowhere to "
                      "record it")
        self.assertIn("task-tracking.md", state, "state.md must route the field to its owner")

    def test_t10_state_template_does_not_restate_owner_fields(self):
        state = read(RUNTIME_STATE)
        for nested in ("issue_number", "sync_reason", "pending_checkpoint", "last_checkpoint_ref"):
            self.assertNotIn(nested, state,
                             f"state.md must not duplicate the owner's {nested}")

    # -- T-12: symmetry ------------------------------------------------------

    def test_t12_both_entries_carry_the_obligation_symmetrically(self):
        for name, text in (("feature", self._feature_environment_row()),
                           ("bug-fix", self._bug_environment_section())):
            with self.subTest(entry=name):
                self.assertIsNone(self.obligation_problem(text),
                                  f"{name}: {self.obligation_problem(text)}")

    # -- T-13: no authorization creep ---------------------------------------

    def test_t13_obligation_sentences_do_not_name_unauthorized_actions(self):
        for name, text in (("feature", self._feature_environment_row()),
                           ("bug-fix", self._bug_environment_section()),
                           ("runtime", self._runtime_preflight())):
            with self.subTest(entry=name):
                for token in self.OVER_BROAD:
                    self.assertNotIn(token, text,
                                     f"{name} entry must not imply authorization for {token}")

    # -- T-11/T-14: semantic mutations must break the guard -----------------

    def _mutate_clause(self, text: str, fn) -> str:
        """Apply `fn` to the tracking clause only, not the first match anywhere.

        The Environment row carries other 必须 ("恢复任务…必须复用并验证"), so a
        whole-text replace would edit an unrelated sentence and leave the tracking
        mandate intact — proving nothing.
        """
        clause = self.tracking_clause(text)
        assert clause is not None, "no tracking clause to mutate"
        mutated = fn(clause)
        self.assertNotEqual(mutated, clause, "clause mutation must change the clause")
        return text.replace(clause, mutated, 1)

    # (label, fn(clause) -> mutated clause)
    MUTATIONS = (
        ("no_need", "极性反转：必须按 -> 无需按",
         lambda c: c.replace("必须按", "无需按")),
        ("optional", "极性反转：必须 -> 可选",
         lambda c: c.replace("必须", "可选", 1)),
        ("suggest", "极性反转：必须 -> 建议",
         lambda c: c.replace("必须", "建议", 1)),
        ("forbidden", "极性反转：必须 -> 禁止",
         lambda c: c.replace("必须", "禁止", 1)),
        ("not_mandatory", "否定式：不是必须",
         lambda c: c.replace("必须按", "不是必须按", 1)),
        ("not_required", "否定式：并非要求必须",
         lambda c: c.replace("必须按", "并非要求必须按", 1)),
        ("choose_whether", "可疑式：可以选择是否必须",
         lambda c: c.replace("必须按", "可以选择是否必须按", 1)),
        ("should", "强制词弱化为 应当",
         lambda c: c.replace("必须", "应当", 1)),
        ("drop_mandate", "删除 tracking 子句里的 必须",
         lambda c: c.replace("必须", "", 1)),
        ("move_mandate", "把 必须 移出 tracking 子句",
         lambda c: c.replace("必须", "", 1)),
        ("after_gate", "时序反转：Gate 前 -> Gate 后",
         lambda c: c.replace("Environment Gate 前", "Environment Gate 后")),
        ("before_stage", "时序反转：worktree 确定后 -> 进入 Environment Stage 之前",
         lambda c: c.replace("worktree 与分支确定后、Environment Gate 前",
                             "进入 Environment Stage 之前")),
        ("split_clause", "把 Gate 锚点拆出 tracking 子句",
         lambda c: c.replace("worktree 与分支确定后、Environment Gate 前，必须按",
                             "worktree 与分支确定后，必须按", 1)),
        ("over_broad", "引入未授权的 checkpoint 措辞",
         lambda c: c.replace("创建并绑定一张 GitHub Issue",
                             "创建并绑定一张 GitHub Issue 并追加 checkpoint")),
    )

    def test_t14_semantic_mutations_break_the_guard(self):
        original = self._feature_environment_row()
        self.assertIsNone(self.obligation_problem(original),
                          "the unmutated entry must pass before mutations mean anything")
        for tag, label, fn in self.MUTATIONS:
            with self.subTest(mutation=tag):
                mutated = self._mutate_clause(original, fn)
                self.assertIsNotNone(self.obligation_problem(mutated),
                                     f"guard stayed green after: {label}")

    def test_t11_removing_the_obligation_breaks_the_guard(self):
        original = self._feature_environment_row()
        stripped = re.sub(r"\*\*worktree 与分支确定后.*?通过\*\*", "", original)
        self.assertNotEqual(stripped, original, "mutation target must exist")
        self.assertIsNotNone(self.obligation_problem(stripped),
                             "guard must detect a removed obligation sentence")

    def test_t15_moving_the_mandate_into_an_unrelated_sentence_does_not_help(self):
        """The exact bypass the clause-scoped predicate exists to catch: strip 必须
        from the tracking clause while an unrelated sentence still has one."""
        row = self._feature_environment_row()
        clause = self.tracking_clause(row)
        self.assertIn("必须", clause, "precondition: the clause carries the mandate")
        hacked = row.replace(clause, clause.replace("必须", ""), 1)
        self.assertIn("必须", hacked,
                      "precondition: an unrelated sentence still carries 必须")
        self.assertIsNotNone(self.obligation_problem(hacked),
                             "a 必须 borrowed from an unrelated sentence must not count")

if __name__ == "__main__":
    unittest.main()

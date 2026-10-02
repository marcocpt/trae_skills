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

import json
import re
import subprocess
import sys
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

    def test_tracking_nested_schema_single_owner(self):
        contract = read(RUNTIME_CONTRACT)
        schema_block = re.search(r"```yaml\nschema_version: 1\n.*?```", contract, re.S).group(0)
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


if __name__ == "__main__":
    unittest.main()

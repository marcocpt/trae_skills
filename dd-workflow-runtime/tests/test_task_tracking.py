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

import re
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


if __name__ == "__main__":
    unittest.main()

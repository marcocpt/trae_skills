"""Contract tests for the Environment Gate tracking-binding validator.

Owner: dd-workflow-runtime/references/task-tracking.md (single source for the
semantics). This file tests only the mechanical realization of the owner's
"must have attempted and recorded" rule (task-tracking §2 / §13) plus the
historical-state and scope exemptions (FR-6 / FR-7).

It asserts nothing about which sync values or sync_reason codes exist — those
vocabularies are owned by task-tracking.md and locked from the other side by
test_task_tracking.py::TestVocabularyDrift.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "dd-workflow-runtime" / "agents" / "validate-tracking-binding.py"

# workflow types the owner subjects to the mandatory attempt (task-tracking §2).
MANDATORY_TYPES = ("feature-development", "bug-fix")

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def make_state(**overrides):
    """A schema-2 feature-development state with a recorded binding attempt.

    Callers override only the field under test; everything else stays valid so a
    failure isolates one behavior (artifact-verification: one conclusion, one run).
    """
    state = {
        "schema_version": 2,
        "workflow_id": "feature-development-20261003T000000Z-abc1234",
        "workflow_type": "feature-development",
        "status": "active",
        "current_stage": "environment",
        "tracking": {
            "provider": "github",
            "repository": "owner/repo",
            "issue_number": 8,
            "sync": "synced",
            "sync_reason": None,
            "pending_checkpoint": None,
            "last_checkpoint_ref": None,
        },
    }
    for key, value in overrides.items():
        if value is _ABSENT:
            state.pop(key, None)
        else:
            state[key] = value
    return state


class _Absent:
    def __repr__(self):
        return "<absent>"


_ABSENT = _Absent()
ABSENT = _ABSENT


def run_validator(state, extra_env=None):
    """Invoke the validator on a temp state file; return (exit_code, stdout)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ)
        if extra_env:
            env.update(extra_env)
        proc = subprocess.run(
            [sys.executable, str(VALIDATOR), "--state", str(path)],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        )
        return proc.returncode, proc.stdout


def tracked(tracking, **overrides):
    """schema-2 state carrying the given tracking payload."""
    return make_state(tracking=tracking, **overrides)


# ---------------------------------------------------------------------------
# T-20~T-26, T-55: the only FAIL shapes, plus input errors
# ---------------------------------------------------------------------------


class TestMustAttemptFails(unittest.TestCase):
    def test_t20_tracking_absent_fails(self):
        code, _ = run_validator(make_state(tracking=ABSENT))
        self.assertEqual(code, EXIT_FAIL, "schema 2 state with no tracking key must FAIL")

    def test_t21_tracking_null_fails(self):
        code, _ = run_validator(make_state(tracking=None))
        self.assertEqual(code, EXIT_FAIL, "schema 2 tracking=null means never attempted -> FAIL")

    def test_t22_bug_fix_also_mandatory(self):
        code, _ = run_validator(make_state(workflow_type="bug-fix", tracking=ABSENT))
        self.assertEqual(code, EXIT_FAIL, "bug-fix is under the same mandatory constraint")

    def test_t23_object_without_binding_or_sync_fails(self):
        code, _ = run_validator(tracked({"provider": "github", "repository": "o/r"}))
        self.assertEqual(code, EXIT_FAIL, "an object with neither issue_number nor sync is not a record")

    def test_t24_sync_alone_without_reason_or_issue_fails(self):
        # sync present but no issue_number and no sync_reason: not one of the
        # owner's four "recorded" shapes (synced/disabled pass on their own;
        # not-synced/not-authorized require a reason).
        code, _ = run_validator(tracked({"provider": "github", "sync": "not-synced"}))
        self.assertEqual(code, EXIT_FAIL, "a sync value that needs a reason must carry one")

    def test_t25_unknown_sync_reason_fails(self):
        code, _ = run_validator(tracked({"sync": "not-synced", "sync_reason": "not-a-real-code"}))
        self.assertEqual(code, EXIT_FAIL, "a reason outside the owner's vocabulary is not a record")

    def test_t26_unregistered_provider_fails(self):
        code, _ = run_validator(tracked({"provider": "gitlab", "sync": "not-synced",
                                         "sync_reason": "no-policy"}))
        self.assertEqual(code, EXIT_FAIL, "task-tracking §2: provider, when non-null, must be supported")

    def test_t55_missing_state_file_is_usage_error(self):
        proc = subprocess.run(
            [sys.executable, str(VALIDATOR), "--state", "/nonexistent/state.json"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(proc.returncode, EXIT_USAGE,
                         "an unreadable input is a usage error, not a Gate failure")


# ---------------------------------------------------------------------------
# T-30~T-31: a valid binding always passes
# ---------------------------------------------------------------------------


class TestValidBindingPasses(unittest.TestCase):
    def test_t30_bound_synced(self):
        code, _ = run_validator(tracked({
            "provider": "github", "repository": "o/r", "issue_number": 8, "sync": "synced"}))
        self.assertEqual(code, EXIT_PASS)

    def test_t31_bound_with_problem_reason(self):
        code, _ = run_validator(tracked({
            "provider": "github", "repository": "o/r", "issue_number": 8,
            "sync": "not-synced", "sync_reason": "issue-missing"}))
        self.assertEqual(code, EXIT_PASS, "a bound issue passes even when the last sync failed")


# ---------------------------------------------------------------------------
# T-40~T-49: every recorded failure/decline row of task-tracking §4 must pass.
# The codes are spelled out here (not imported) so this file stays a behavioural
# test; TestVocabularyDrift separately proves none of them is invented.
# ---------------------------------------------------------------------------


class TestEveryRecordedOutcomePasses(unittest.TestCase):
    CASES = [
        ("t40_remote_unresolvable", "not-synced", "remote-unresolvable"),
        ("t41_issue_missing", "not-synced", "issue-missing"),
        ("t42_no_policy", "not-authorized", "no-policy"),
        ("t43_user_declined", "not-authorized", "user-declined"),
        ("t44_binding_ambiguous", "not-synced", "binding-ambiguous"),
        ("t45_create_outcome_unknown", "not-synced", "create-outcome-unknown"),
        ("t46_legacy_tracking_unknown", "not-synced", "legacy-tracking-unknown"),
        ("t47_no_issue_capable_remote", "not-synced", "no-issue-capable-remote"),
        ("t48_provider_unavailable", "not-synced", "provider-unavailable"),
    ]

    def test_each_recorded_reason_passes(self):
        for name, sync, reason in self.CASES:
            with self.subTest(case=name):
                code, _ = run_validator(tracked({"sync": sync, "sync_reason": reason}))
                self.assertEqual(code, EXIT_PASS,
                                 f"{name}: a recorded reason must never block the workflow")

    def test_t49_disabled_passes_without_reason(self):
        code, _ = run_validator(tracked({"sync": "disabled", "sync_reason": None}))
        self.assertEqual(code, EXIT_PASS, "task-tracking §4: disabled needs no reason")


# ---------------------------------------------------------------------------
# T-50~T-54: historical states and out-of-scope workflow types
# ---------------------------------------------------------------------------


class TestHistoricalAndOutOfScopePass(unittest.TestCase):
    def test_t50_missing_schema_version(self):
        state = make_state(tracking=ABSENT)
        state.pop("schema_version")
        code, _ = run_validator(state)
        self.assertEqual(code, EXIT_PASS, "pre-contract state must not be forced to have attempted")

    def test_t51_schema_1_null_tracking(self):
        code, _ = run_validator(make_state(schema_version=1, tracking=None))
        self.assertEqual(code, EXIT_PASS, "schema 1 null is legacy-unknown, not never-attempted")

    def test_t52_schema_0_null_tracking(self):
        code, _ = run_validator(make_state(schema_version=0, tracking=None))
        self.assertEqual(code, EXIT_PASS)

    def test_t53_legacy_state_with_binding_passes(self):
        code, _ = run_validator(make_state(schema_version=1, tracking={
            "provider": "github", "repository": "o/r", "issue_number": 8, "sync": "synced"}))
        self.assertEqual(code, EXIT_PASS, "an already-bound legacy state stays valid")

    def test_t54_bootstrap_is_out_of_scope(self):
        code, _ = run_validator(make_state(
            workflow_type="project-bootstrap", schema_version=1, tracking=None))
        self.assertEqual(code, EXIT_PASS, "task-tracking §12 exempts project-bootstrap")


# ---------------------------------------------------------------------------
# T-56~T-57: the validator is offline (FR-5 / AC-10)
# ---------------------------------------------------------------------------


class TestValidatorIsOffline(unittest.TestCase):
    FORBIDDEN = ("socket", "urllib", "requests", "http.client", "httpx",
                 "subprocess", "os.system", "gh\x20", "git\x20")

    def test_t56_source_has_no_network_or_shell_calls(self):
        src = VALIDATOR.read_text(encoding="utf-8")
        for token in self.FORBIDDEN:
            self.assertNotIn(token, src, f"validator must not reference {token!r}")

    def test_t57_runs_without_home_or_path(self):
        code, _ = run_validator(make_state(), extra_env={"HOME": "", "PATH": ""})
        self.assertEqual(code, EXIT_PASS, "validator must not read credentials or shell out")


if __name__ == "__main__":
    unittest.main()

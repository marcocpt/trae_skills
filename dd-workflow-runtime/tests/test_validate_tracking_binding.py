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
import re
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
    """Invoke the validator on a temp state file.

    Returns (exit_code, stdout, stderr). stderr is returned because an uncaught
    Python traceback lands there and exits 1 — indistinguishable from a genuine
    Gate FAIL by exit code alone, so tests must inspect it.
    """
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
        return proc.returncode, proc.stdout, proc.stderr


def assert_clean_run(testcase, code, out, err):
    """A judged run must not crash: no traceback, and a contract exit code."""
    testcase.assertNotIn("Traceback", err, f"validator crashed:\n{err}")
    testcase.assertNotIn("Traceback", out, f"validator crashed:\n{out}")
    testcase.assertIn(code, (EXIT_PASS, EXIT_FAIL, EXIT_USAGE))


def tracked(tracking, **overrides):
    """schema-2 state carrying the given tracking payload."""
    return make_state(tracking=tracking, **overrides)


# ---------------------------------------------------------------------------
# T-20~T-26, T-55: the only FAIL shapes, plus input errors
# ---------------------------------------------------------------------------


class TestMustAttemptFails(unittest.TestCase):
    def test_t20_tracking_absent_fails(self):
        code, out, err = run_validator(make_state(tracking=ABSENT))
        self.assertEqual(code, EXIT_FAIL, "schema 2 state with no tracking key must FAIL")

    def test_t21_tracking_null_fails(self):
        code, out, err = run_validator(make_state(tracking=None))
        self.assertEqual(code, EXIT_FAIL, "schema 2 tracking=null means never attempted -> FAIL")

    def test_t22_bug_fix_also_mandatory(self):
        code, out, err = run_validator(make_state(workflow_type="bug-fix", tracking=ABSENT))
        self.assertEqual(code, EXIT_FAIL, "bug-fix is under the same mandatory constraint")

    def test_t23_object_without_binding_or_sync_fails(self):
        code, out, err = run_validator(tracked({"provider": "github", "repository": "o/r"}))
        self.assertEqual(code, EXIT_FAIL, "an object with neither issue_number nor sync is not a record")

    def test_t24_sync_alone_without_reason_or_issue_fails(self):
        # sync present but no issue_number and no sync_reason: not one of the
        # owner's four "recorded" shapes (synced/disabled pass on their own;
        # not-synced/not-authorized require a reason).
        code, out, err = run_validator(tracked({"provider": "github", "sync": "not-synced"}))
        self.assertEqual(code, EXIT_FAIL, "a sync value that needs a reason must carry one")

    def test_t25_unknown_sync_reason_fails(self):
        code, out, err = run_validator(tracked({"sync": "not-synced", "sync_reason": "not-a-real-code"}))
        self.assertEqual(code, EXIT_FAIL, "a reason outside the owner's vocabulary is not a record")

    def test_t26_unregistered_provider_fails(self):
        code, out, err = run_validator(tracked({"provider": "gitlab", "sync": "not-synced",
                                         "sync_reason": "no-policy"}))
        self.assertEqual(code, EXIT_FAIL, "task-tracking §2: provider, when non-null, must be supported")

    def test_t27_invalid_issue_number_is_not_a_binding(self):
        # 0 / "" / False are falsy; -1 is truthy but not an issue number; [] is not
        # a number at all. None of them may stand in for a created card.
        for bogus in (0, "", False, -1, [], {}, 1.0):
            with self.subTest(issue_number=bogus):
                code, out, err = run_validator(tracked({"provider": "github", "issue_number": bogus}))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_FAIL,
                                 f"issue_number={bogus!r} is not a real issue; only a positive "
                                 "int counts as bound")

    def test_t28_non_integer_schema_version_does_not_bypass(self):
        # A hand-written "2" must not be read as the current schema (which would
        # FAIL here) and must not be read as legacy either (which would PASS and
        # let a never-attempted state through). It is a malformed state.
        for bogus in ("2", "1", True, False, 2.5, [], {}, -1, -2):
            with self.subTest(schema_version=bogus):
                code, out, err = run_validator(make_state(schema_version=bogus, tracking=None))
                self.assertEqual(
                    code, EXIT_USAGE,
                    f"schema_version={bogus!r} is not an integer; a malformed state must "
                    "not silently pass as legacy or fail as never-attempted")

    def test_t29_unknown_or_missing_workflow_type_does_not_pass_open(self):
        for bogus in (None, "", "feature", "Feature-Development", 7):
            with self.subTest(workflow_type=bogus):
                state = make_state(tracking=None)
                if bogus is None:
                    state.pop("workflow_type")
                else:
                    state["workflow_type"] = bogus
                code, out, err = run_validator(state)
                assert_clean_run(self, code, out, err)
                self.assertEqual(
                    code, EXIT_USAGE,
                    f"workflow_type={bogus!r} is neither a mandatory nor a registered "
                    "exempt type; an unrecognized state must be rejected as malformed, "
                    "not crash and not pass")

    def test_t62_cross_pairs_absent_from_the_owner_matrix_fail(self):
        # §4 pairs each sync value with specific reasons. Checking the two
        # vocabularies independently would accept combinations the owner never
        # states, making the validator a second source of truth.
        for sync, reason in (("not-authorized", "issue-missing"),
                             ("not-synced", "user-declined"),
                             ("not-authorized", "binding-ambiguous"),
                             ("not-synced", "no-policy"),
                             ("disabled", "issue-missing"),
                             ("synced", "no-policy")):
            with self.subTest(pair=(sync, reason)):
                code, out, err = run_validator(tracked({"sync": sync, "sync_reason": reason}))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_FAIL,
                                 f"({sync}, {reason}) is not a pair task-tracking §4 defines")

    def test_t63_nested_non_string_values_do_not_crash(self):
        # An uncaught TypeError exits 1, which is indistinguishable from a real
        # Gate FAIL — the caller could not tell a crash from a verdict. The
        # traceback lands on stderr, and exit 1 is the Gate FAIL code, so this must
        # require exit 2 AND a clean stderr, not merely "not a crash in stdout".
        for field in ("provider", "sync", "sync_reason"):
            for bogus in ([], {}, 7, [1, 2]):
                with self.subTest(field=field, value=bogus):
                    # Build the fixture first, then override: putting {field: bogus}
                    # inline would be clobbered by the literal sync/sync_reason keys.
                    payload = {"sync": "not-synced", "sync_reason": "no-policy"}
                    payload[field] = bogus
                    code, out, err = run_validator(tracked(payload))
                    self.assertNotIn("Traceback", err,
                                     f"tracking.{field}={bogus!r} crashed:\n{err}")
                    self.assertEqual(
                        code, EXIT_USAGE,
                        f"tracking.{field}={bogus!r} must be malformed input (exit 2); "
                        f"exit {code} means either a wrong verdict or a crash")

    def test_t68_valid_binding_with_malformed_sibling_is_rejected(self):
        # Design §3.2 step 6 runs before the binding check. A state holding both a
        # valid issue_number and a non-string sync is internally inconsistent and
        # must not pass on the strength of the binding.
        for field in ("provider", "sync", "sync_reason"):
            for bogus in ([], {}, 7):
                with self.subTest(field=field, value=bogus):
                    payload = {"provider": "github", "issue_number": 8, "sync": "synced"}
                    payload[field] = bogus
                    code, out, err = run_validator(tracked(payload))
                    self.assertNotIn("Traceback", err, f"tracking.{field}={bogus!r} crashed")
                    self.assertEqual(code, EXIT_USAGE,
                                     f"valid binding + malformed tracking.{field} is a "
                                     "malformed state, not a pass")

    def test_t69_out_of_vocabulary_reason_is_caught_without_a_sync(self):
        # Design §3.2 step 10 checks each vocabulary on its own. An earlier version
        # gated the reason check on `sync is not None`, so a stray reason alongside a
        # null sync fell through to the generic fallback instead — same exit code,
        # but step 10 would no longer map to the implementation item for item.
        for payload in ({"sync": None, "sync_reason": "not-a-real-code"},
                        {"sync_reason": "not-a-real-code"},
                        {"sync": "synced", "sync_reason": "not-a-real-code"},
                        {"sync": "not-a-real-value"}):
            with self.subTest(payload=payload):
                code, out, err = run_validator(tracked(payload))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_FAIL)
                self.assertIn("outside the task-tracking", out,
                              "step 10 must name the offending vocabulary")

    def test_t64_invalid_utf8_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_bytes(b'{"schema_version": 2, "workflow_type": "\xff\xfe"}')
            proc = subprocess.run(
                [sys.executable, str(VALIDATOR), "--state", str(path)],
                capture_output=True, text=True, cwd=str(REPO_ROOT))
            self.assertEqual(proc.returncode, EXIT_USAGE)
            self.assertNotIn("Traceback", proc.stderr)

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
        code, out, err = run_validator(tracked({
            "provider": "github", "repository": "o/r", "issue_number": 8, "sync": "synced"}))
        self.assertEqual(code, EXIT_PASS)

    def test_t31_bound_with_problem_reason(self):
        code, out, err = run_validator(tracked({
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
                code, out, err = run_validator(tracked({"sync": sync, "sync_reason": reason}))
                self.assertEqual(code, EXIT_PASS,
                                 f"{name}: a recorded reason must never block the workflow")

    def test_t49_disabled_passes_without_reason(self):
        code, out, err = run_validator(tracked({"sync": "disabled", "sync_reason": None}))
        self.assertEqual(code, EXIT_PASS, "task-tracking §4: disabled needs no reason")


# ---------------------------------------------------------------------------
# T-50~T-54: historical states and out-of-scope workflow types
# ---------------------------------------------------------------------------


class TestHistoricalAndOutOfScopePass(unittest.TestCase):
    def test_t50_missing_schema_version(self):
        state = make_state(tracking=ABSENT)
        state.pop("schema_version")
        code, out, err = run_validator(state)
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS, "pre-contract state must not be forced to have attempted")

    def test_t51_schema_1_null_tracking(self):
        code, out, err = run_validator(make_state(schema_version=1, tracking=None))
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS, "schema 1 null is legacy-unknown, not never-attempted")

    def test_t52_schema_0_null_tracking(self):
        code, out, err = run_validator(make_state(schema_version=0, tracking=None))
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS)

    def test_t67_legacy_state_with_partial_tracking_passes(self):
        # FAIL belongs to the current schema only. A pre-contract state may carry a
        # partial tracking object; failing it would block the Gate on history the
        # contract never required (FR-7).
        partials = ({}, {"provider": "github"}, {"sync": "synced"},
                    {"provider": "github", "issue_number": 8},
                    {"sync": "not-synced", "sync_reason": "issue-missing"},
                    {"provider": "gitlab"})
        for version in (None, 0, 1):
            for tracking in partials:
                with self.subTest(schema_version=version, tracking=tracking):
                    state = make_state(tracking=tracking)
                    if version is None:
                        state.pop("schema_version")
                    else:
                        state["schema_version"] = version
                    code, out, err = run_validator(state)
                    assert_clean_run(self, code, out, err)
                    self.assertEqual(code, EXIT_PASS,
                                     f"schema {version} + {tracking} must not be failed")

    def test_t53_legacy_state_with_binding_passes(self):
        code, out, err = run_validator(make_state(schema_version=1, tracking={
            "provider": "github", "repository": "o/r", "issue_number": 8, "sync": "synced"}))
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS, "an already-bound legacy state stays valid")

    def test_t54_bootstrap_is_out_of_scope(self):
        code, out, err = run_validator(make_state(
            workflow_type="project-bootstrap", schema_version=1, tracking=None))
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS, "task-tracking §12 exempts project-bootstrap")

    def test_t65_bootstrap_exemption_precedes_schema_validation(self):
        # The exemption is an unconditional scope exemption: a malformed schema
        # elsewhere in a bootstrap state must not deny it, or the order of checks
        # would silently narrow an owner exemption.
        for version in ("2", -1, True, [], {}):
            with self.subTest(schema_version=version):
                code, out, err = run_validator(make_state(
                    workflow_type="project-bootstrap", schema_version=version, tracking=None))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_PASS,
                                 "bootstrap is exempt regardless of its schema_version")

    def test_t66_synced_without_issue_number_takes_the_pair_branch(self):
        # §4's 绑定有效 row is (synced, —). T-30 returns early on issue_number, so
        # without this the self-recording pair branch would never be exercised.
        code, out, err = run_validator(tracked({"sync": "synced", "sync_reason": None}))
        assert_clean_run(self, code, out, err)
        self.assertEqual(code, EXIT_PASS,
                         "(synced, None) is a recorded outcome in task-tracking §4")
        self.assertIn("without a reason", out,
                      "the run must actually take the no-reason pair branch")


# ---------------------------------------------------------------------------
# T-56~T-57: the validator is offline (FR-5 / AC-10)
# ---------------------------------------------------------------------------


class TestFastTrackWorkflowsAreCovered(unittest.TestCase):
    """task-tracking §2 was widened to four long-running workflows.

    The two fast-track workflows bind at their Intake Gate, but the attempt
    requirement and its vocabulary are identical, so the validator must judge
    them the same way. Before this was added they fell through to "unrecognized
    workflow type" and exited 2 — rejecting two workflows the owner mandates.
    """

    TYPES = ("feature-fast-track", "bug-fast-track")

    def test_t78_fast_track_untried_fails_the_gate(self):
        for wf_type in self.TYPES:
            with self.subTest(workflow_type=wf_type):
                code, out, err = run_validator(make_state(
                    workflow_type=wf_type, schema_version=2, tracking=None))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_FAIL,
                                 f"{wf_type} is under the same mandatory constraint")

    def test_t79_fast_track_bound_passes(self):
        for wf_type in self.TYPES:
            with self.subTest(workflow_type=wf_type):
                code, out, err = run_validator(make_state(
                    workflow_type=wf_type, schema_version=2,
                    tracking={"provider": "github", "issue_number": 8, "sync": "synced"}))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_PASS)

    @staticmethod
    def _gate_association_ok(message: str) -> bool:
        """True when the message binds each Gate to the right workflow class."""
        return bool(re.search(r"Environment Gate for Feature/Bug", message)) and \
            bool(re.search(r"Intake Gate for\s+the two fast-track", message))

    def _fail_message_for(self, workflow_type: str) -> str:
        _, _, err = run_validator(make_state(workflow_type=workflow_type,
                                              schema_version=2, tracking=None))
        return err

    def test_t80_fail_message_names_the_binding_gate_not_the_environment_gate(self):
        # The owner distinguishes Environment Gate (Feature/Bug) from Intake Gate
        # (fast-track). A diagnostic that always says "Environment Gate" would point
        # a fast-track Agent at the wrong boundary. Asserting only that both names
        # appear would still pass if the two were swapped, so the association with
        # each workflow class is checked through _gate_association_ok.
        for workflow_type in ("bug-fast-track", "feature-development"):
            with self.subTest(workflow_type=workflow_type):
                message = self._fail_message_for(workflow_type)
                self.assertIn("Intake Gate", message)
                self.assertIn("Environment Gate", message)
                self.assertTrue(
                    self._gate_association_ok(message),
                    f"{workflow_type}: diagnostic must bind Environment Gate to "
                    f"Feature/Bug and Intake Gate to the fast-track pair; got: {message!r}")

    def test_t80b_gate_association_check_rejects_a_swap(self):
        """Proves the association check discriminates: a swapped message must fail it."""
        real = self._fail_message_for("bug-fast-track")
        self.assertTrue(self._gate_association_ok(real))

        swapped = real.replace("Environment Gate for Feature/Bug", "@A@").replace(
            "Intake Gate for the two fast-track", "Environment Gate for Feature/Bug"
        ).replace("@A@", "Intake Gate for Feature/Bug")
        self.assertNotEqual(swapped, real, "the swap must actually change the text")
        self.assertFalse(
            self._gate_association_ok(swapped),
            "a message that binds Intake Gate to Feature/Bug must not pass the check")

    def test_t81_fast_track_legacy_state_passes(self):
        for wf_type in self.TYPES:
            with self.subTest(workflow_type=wf_type):
                code, out, err = run_validator(make_state(
                    workflow_type=wf_type, schema_version=1, tracking=None))
                assert_clean_run(self, code, out, err)
                self.assertEqual(code, EXIT_PASS)


class TestValidatorIsOffline(unittest.TestCase):
    FORBIDDEN = ("socket", "urllib", "requests", "http.client", "httpx",
                 "subprocess", "os.system", "gh\x20", "git\x20")

    def test_t56_source_has_no_network_or_shell_calls(self):
        src = VALIDATOR.read_text(encoding="utf-8")
        for token in self.FORBIDDEN:
            self.assertNotIn(token, src, f"validator must not reference {token!r}")

    def test_t57_runs_without_home_or_path(self):
        code, out, err = run_validator(make_state(), extra_env={"HOME": "", "PATH": ""})
        self.assertEqual(code, EXIT_PASS, "validator must not read credentials or shell out")


if __name__ == "__main__":
    unittest.main()

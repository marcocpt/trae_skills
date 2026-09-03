#!/usr/bin/env python3
"""Tests for opencode-review thin adapter: event stream -> dd-review-result/1."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "agents" / "opencode-review"

def _load_adapter():
    loader = importlib.machinery.SourceFileLoader("opencode_review_adapter", str(ADAPTER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

ADAPTER_MOD = _load_adapter()


def _valid_reviewer_json(status="FINDINGS", **overrides):
    base = {
        "status": status,
        "reviewed": ["review.py"],
        "unreadable": [],
        "findings": [{
            "id": "RV-001",
            "severity": "HIGH",
            "classification": "FINDING",
            "change_risk": "MEDIUM",
            "location": "review.py:2-3",
            "evidence": "silent zero divisor",
            "required_fix": "raise ZeroDivisionError"
        }] if status == "FINDINGS" else [],
        "evidence": ["frozen baseline ok"],
        "failure_category": None,
    }
    base.update(overrides)
    return base


def _event_stream(final_text: str, extra_texts=None, tools=None):
    """Build NDJSON event stream with final text as last text event."""
    events = []
    ts = 1000
    def add(t, part):
        nonlocal ts
        ts += 1
        events.append(json.dumps({"type": t, "timestamp": ts, "sessionID": "ses_test", "part": part}, ensure_ascii=False))
    # step start
    add("step_start", {"type": "step-start", "id": "s1"})
    if extra_texts:
        for txt in extra_texts:
            add("text", {"type": "text", "id": "p1", "text": txt, "time": {"end": ts}})
            add("step_finish", {"type": "step-finish", "id": "f1"})
            add("step_start", {"type": "step-start", "id": "s2"})
    if tools:
        for tool in tools:
            add("tool_use", {"type": "tool", "tool": tool, "callID": "c1", "state": {"status": "completed", "input": {}, "output": "ok"}})
            add("step_finish", {"type": "step-finish", "id": "f2"})
            add("step_start", {"type": "step-start", "id": "s3"})
    add("text", {"type": "text", "id": "final", "text": final_text, "time": {"end": ts}})
    add("step_finish", {"type": "step-finish", "id": "final-f"})
    return "\n".join(events)


class ExtractFinalTextTests(unittest.TestCase):
    def test_single_event_text_extracted(self):
        txt, err = ADAPTER_MOD._extract_final_text(_event_stream('{"status":"PASS","reviewed":["review.py"],"unreadable":[],"findings":[],"evidence":["ok"]}'))
        self.assertIsNone(err)
        self.assertTrue(txt.startswith("{"))

    def test_multi_event_picks_last(self):
        txt, err = ADAPTER_MOD._extract_final_text(_event_stream('{"status":"PASS","reviewed":["review.py"],"unreadable":[],"findings":[],"evidence":["ok"]}', extra_texts=["intermediate", "another"]))
        self.assertIsNone(err)
        self.assertIn('"status"', txt)

    def test_reasoning_tool_mixed(self):
        # Simulate stream with tool events before final text
        txt, err = ADAPTER_MOD._extract_final_text(_event_stream('{"status":"FINDINGS","reviewed":["review.py"],"unreadable":[],"findings":[{"id":"RV-001","severity":"HIGH","classification":"x","change_risk":"y","location":"review.py:1","evidence":"e","required_fix":"f"}],"evidence":["ok"]}', tools=["read", "glob"]))
        self.assertIsNone(err)
        self.assertIn("FINDINGS", txt)

    def test_malformed_event_fails_closed(self):
        bad = '{"type":"text", "part": {"type":"text", "text":"hi"'  # truncated
        txt, err = ADAPTER_MOD._extract_final_text(bad + "\n" + _event_stream('{}'))
        self.assertIsNotNone(err)
        self.assertIn("malformed", err)

    def test_missing_final_text_fails(self):
        # Only tool events, no text with end time
        stream = json.dumps({"type":"tool_use","timestamp":1,"sessionID":"s","part":{"type":"tool","tool":"read","callID":"c","state":{"status":"completed"}}})
        txt, err = ADAPTER_MOD._extract_final_text(stream)
        self.assertIsNotNone(err)
        self.assertIn("missing", err)

    def test_empty_stdout_fails(self):
        txt, err = ADAPTER_MOD._extract_final_text("")
        self.assertIsNotNone(err)


class StrictJsonParseTests(unittest.TestCase):
    def test_valid_strict_json_passes(self):
        obj, err = ADAPTER_MOD._strict_json_parse('{"status":"PASS","reviewed":["review.py"],"unreadable":[],"findings":[],"evidence":["ok"]}')
        self.assertIsNone(err)
        self.assertEqual(obj["status"], "PASS")

    def test_code_fence_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('```json\n{"status":"PASS"}\n```')
        self.assertIsNotNone(err)
        self.assertIn("code fence", err)

    def test_prose_wrapper_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('Here is result: {"status":"PASS"}')
        self.assertIsNotNone(err)

    def test_markdown_escapes_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('{"evidence":"\\[test\\]"}')
        self.assertIsNotNone(err)
        self.assertIn("markdown", err)

    def test_invalid_json_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('{"status":}')
        self.assertIsNotNone(err)

    def test_not_object_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('["a"]')
        self.assertIsNotNone(err)


class ValidateReviewerJsonTests(unittest.TestCase):
    def test_valid_findings_passes(self):
        err = ADAPTER_MOD._validate_reviewer_json(_valid_reviewer_json("FINDINGS"), ["review.py"])
        self.assertIsNone(err)

    def test_valid_pass_passes(self):
        err = ADAPTER_MOD._validate_reviewer_json(_valid_reviewer_json("PASS"), ["review.py"])
        self.assertIsNone(err)

    def test_missing_status_rejected(self):
        j = _valid_reviewer_json("PASS")
        del j["status"]
        self.assertIsNotNone(ADAPTER_MOD._validate_reviewer_json(j, ["review.py"]))

    def test_incomplete_scope_rejected(self):
        j = _valid_reviewer_json("FINDINGS")
        j["reviewed"] = []
        self.assertIsNotNone(ADAPTER_MOD._validate_reviewer_json(j, ["review.py"]))

    def test_finding_missing_field_rejected(self):
        j = _valid_reviewer_json("FINDINGS")
        del j["findings"][0]["required_fix"]
        self.assertIsNotNone(ADAPTER_MOD._validate_reviewer_json(j, ["review.py"]))

    def test_pass_with_findings_rejected(self):
        j = _valid_reviewer_json("PASS")
        j["findings"] = [{"id":"RV-001","severity":"HIGH","classification":"x","change_risk":"y","location":"l","evidence":"e","required_fix":"f"}]
        self.assertIsNotNone(ADAPTER_MOD._validate_reviewer_json(j, ["review.py"]))


class AdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "review.py").write_text("print('base')\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True)
        self.base = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        (self.repo / "review.py").write_text("print('head')\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "head"], check=True)
        self.head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def tearDown(self):
        self.temp.cleanup()

    def request(self):
        return {
            "schema": "dd-review-request/1",
            "role": "strong-reviewer",
            "host": "opencode",
            "repo": str(self.repo),
            "base_sha": self.base,
            "head_sha": self.head,
            "scope": ["review.py"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "routing_context": {"dispatch_boundary": "single-backend", "router_authority": False, "hop_count": 1, "dispatch_chain": ["opencode-cli"], "selected_backend": "opencode-cli"},
        }

    def _run_adapter_with_fake_opencode(self, fake_stdout: str, exit_code: int = 0, request_overrides: dict | None = None):
        """Run adapter with mocked subprocess.run for opencode."""
        req = self.request()
        if request_overrides:
            req.update(request_overrides)
        req_json = json.dumps(req)
        # Mock subprocess.run to return fake opencode result
        mock_completed = mock.Mock()
        mock_completed.stdout = fake_stdout
        mock_completed.stderr = ""
        mock_completed.returncode = exit_code
        original_run = subprocess.run
        with mock.patch("subprocess.run") as mocked:
            # Need to handle two kinds of calls: git checks and opencode call
            # git calls should go through real, opencode call mocked
            def side_effect(cmd, **kwargs):
                if cmd[0] == "opencode":
                    self.captured_opencode_cmd = list(cmd)
                    return mock_completed
                return original_run(cmd, **kwargs)
            mocked.side_effect = side_effect
            # Capture adapter stdout
            import io
            with mock.patch("sys.stdin", io.StringIO(req_json)):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as fake_out:
                    # Mock sys.argv
                    with mock.patch.object(sys, "argv", ["opencode-review", "review"]):
                        ret = ADAPTER_MOD.main()
                        out = fake_out.getvalue()
                        return ret, out

    def test_valid_findings_through_adapter(self):
        reviewer_json = _valid_reviewer_json("FINDINGS")
        stream = _event_stream(json.dumps(reviewer_json))
        ret, out = self._run_adapter_with_fake_opencode(stream)
        self.assertEqual(ret, 0)
        result = json.loads(out)
        self.assertEqual(result["status"], "FINDINGS")
        self.assertEqual(result["backend"], "opencode-cli")
        self.assertFalse(result["readonly_confirmation"]["confirmed"])

    def test_non_strict_json_becomes_schema_invalid_blocked(self):
        stream = _event_stream('```json\n{"status":"PASS"}\n```')
        ret, out = self._run_adapter_with_fake_opencode(stream)
        result = json.loads(out)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "schema_invalid")

    def test_missing_final_text_becomes_review_incomplete(self):
        stream = json.dumps({"type":"tool_use","timestamp":1,"sessionID":"s","part":{"type":"tool","tool":"read","callID":"c","state":{"status":"completed"}}})
        ret, out = self._run_adapter_with_fake_opencode(stream)
        result = json.loads(out)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "review_incomplete")

    def test_opencode_availability_exit_propagated(self):
        stream = _event_stream('{}')
        ret, _ = self._run_adapter_with_fake_opencode(stream, exit_code=69)
        self.assertEqual(ret, 69)

    def test_opencode_transient_exit_propagated(self):
        stream = _event_stream('{}')
        ret, _ = self._run_adapter_with_fake_opencode(stream, exit_code=75)
        self.assertEqual(ret, 75)

    def test_opencode_other_exit_becomes_execution_failed(self):
        stream = _event_stream('{}')
        ret, out = self._run_adapter_with_fake_opencode(stream, exit_code=1)
        result = json.loads(out)
        self.assertEqual(result["failure_category"], "backend_execution_failed")


class ExtractSessionIdTests(unittest.TestCase):
    def test_extracts_first_session_id(self):
        stream = (
            json.dumps({"type": "step_start", "timestamp": 1, "sessionID": "ses_a", "part": {}})
            + "\n"
            + json.dumps({"type": "text", "timestamp": 2, "sessionID": "ses_a", "part": {"type": "text"}})
        )
        self.assertEqual(ADAPTER_MOD._extract_session_id(stream), "ses_a")

    def test_skips_malformed_lines(self):
        stream = "not json\n" + json.dumps({"type": "step_start", "sessionID": "ses_b", "part": {}})
        self.assertEqual(ADAPTER_MOD._extract_session_id(stream), "ses_b")

    def test_returns_none_without_session_id(self):
        self.assertIsNone(ADAPTER_MOD._extract_session_id("garbage\nlines"))
        self.assertIsNone(ADAPTER_MOD._extract_session_id(""))

    def test_ignores_non_string_session_id(self):
        stream = json.dumps({"type": "step_start", "sessionID": 42, "part": {}})
        self.assertIsNone(ADAPTER_MOD._extract_session_id(stream))


class ValidateContinuationTests(unittest.TestCase):
    def test_absent_continuation_is_legacy(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({}))

    def test_valid_initial_passes(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({"continuation": {"form": "initial"}}))

    def test_valid_resume_passes(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({"continuation": {"form": "resume", "handle": "ses_x"}}))

    def test_non_mapping_rejected(self):
        self.assertIn("mapping", ADAPTER_MOD._validate_continuation({"continuation": ["initial"]}))

    def test_unknown_form_rejected(self):
        err = ADAPTER_MOD._validate_continuation({"continuation": {"form": "fork", "handle": "x"}})
        self.assertIn("must be 'initial' or 'resume'", err)

    def test_resume_requires_handle(self):
        err = ADAPTER_MOD._validate_continuation({"continuation": {"form": "resume"}})
        self.assertIn("handle is required", err)


class ContinuationIntegrationTests(unittest.TestCase):
    """FR-MB-015 / FR-MB-016: the adapter honours the continuation contract.

    A resume continuation pins `--session <handle>` on the CLI invocation and
    the transport result reports the engine-proven session identity extracted
    from the event stream; a legacy request without continuation carries no
    session field at all.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "review.py").write_text("print('base')\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True)
        self.base = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        (self.repo / "review.py").write_text("print('head')\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "head"], check=True)
        self.head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def tearDown(self):
        self.temp.cleanup()

    def request(self, continuation=None):
        req = {
            "schema": "dd-review-request/1",
            "role": "strong-reviewer",
            "host": "opencode",
            "repo": str(self.repo),
            "base_sha": self.base,
            "head_sha": self.head,
            "scope": ["review.py"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "routing_context": {"dispatch_boundary": "single-backend", "router_authority": False, "hop_count": 1, "dispatch_chain": ["opencode-cli"], "selected_backend": "opencode-cli"},
        }
        if continuation is not None:
            req["continuation"] = continuation
        return req

    def _run(self, req, fake_stdout):
        req_json = json.dumps(req)
        mock_completed = mock.Mock()
        mock_completed.stdout = fake_stdout
        mock_completed.stderr = ""
        mock_completed.returncode = 0
        original_run = subprocess.run
        with mock.patch("subprocess.run") as mocked:
            def side_effect(cmd, **kwargs):
                if cmd[0] == "opencode":
                    self.captured_cmd = list(cmd)
                    return mock_completed
                return original_run(cmd, **kwargs)
            mocked.side_effect = side_effect
            import io
            with mock.patch("sys.stdin", io.StringIO(req_json)):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as fake_out:
                    with mock.patch.object(sys, "argv", ["opencode-review", "review"]):
                        ret = ADAPTER_MOD.main()
                        return ret, fake_out.getvalue()

    def _ok_stream(self):
        return _event_stream(json.dumps(_valid_reviewer_json("PASS")))

    def test_resume_pins_session_and_reports_identity(self):
        req = self.request({"form": "resume", "handle": "ses_probe"})
        stream = _event_stream(json.dumps(_valid_reviewer_json("PASS")))
        ret, out = self._run(req, stream)
        self.assertEqual(ret, 0)
        self.assertIn("--session", self.captured_cmd)
        self.assertEqual(self.captured_cmd[self.captured_cmd.index("--session") + 1], "ses_probe")
        result = json.loads(out)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["session"], {"form": "resume", "handle": "ses_test"})

    def test_explicit_initial_reports_identity_without_session_flag(self):
        req = self.request({"form": "initial"})
        stream = _event_stream(json.dumps(_valid_reviewer_json("PASS")))
        ret, out = self._run(req, stream)
        self.assertEqual(ret, 0)
        self.assertNotIn("--session", self.captured_cmd)
        result = json.loads(out)
        self.assertEqual(result["session"], {"form": "initial", "handle": "ses_test"})

    def test_legacy_request_has_no_session_field(self):
        req = self.request()
        stream = _event_stream(json.dumps(_valid_reviewer_json("PASS")))
        ret, out = self._run(req, stream)
        self.assertEqual(ret, 0)
        result = json.loads(out)
        self.assertNotIn("session", result)

    def test_resume_without_handle_blocked_schema_invalid(self):
        req = self.request({"form": "resume"})
        stream = _event_stream(json.dumps(_valid_reviewer_json("PASS")))
        ret, out = self._run(req, stream)
        self.assertEqual(ret, 0)
        result = json.loads(out)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "schema_invalid")
        # The adapter must not have invoked opencode at all.
        self.assertFalse(hasattr(self, "captured_cmd"))

    def test_session_id_absent_means_no_session_field(self):
        # Fail-closed: if the engine gave no identity, the adapter must not
        # fabricate one -- the Router will judge the missing identity.
        req = self.request({"form": "resume", "handle": "ses_probe"})
        stream = _event_stream(json.dumps(_valid_reviewer_json("PASS"))).replace("ses_test", "")
        ret, out = self._run(req, stream)
        self.assertEqual(ret, 0)
        result = json.loads(out)
        self.assertNotIn("session", result)


if __name__ == "__main__":
    unittest.main()

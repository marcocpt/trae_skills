#!/usr/bin/env python3
"""Tests for codex-review thin adapter: Codex JSONL -> dd-review-result/1."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "agents" / "codex-review"

def _load_adapter():
    loader = importlib.machinery.SourceFileLoader("codex_review_adapter", str(ADAPTER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

ADAPTER_MOD = _load_adapter()


def _valid_result(status="FINDINGS", **overrides):
    base = {
        "schema": "dd-review-result/1",
        "backend": "codex-cli",
        "reviewer": "strong-reviewer/codex-cli",
        "target": {"base_sha": "a"*40, "head_sha": "b"*40, "scope": ["review.py"]},
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
        "evidence": ["frozen ok"],
        "failure_category": None,
        "lifecycle": {"started": True, "completed": True},
        "readonly_confirmation": {"confirmed": False, "evidence": None},
    }
    base.update(overrides)
    return base


def _codex_stream(final_text: str, extra_messages=None):
    events = []
    events.append(json.dumps({"type": "thread.started", "thread_id": "t1"}))
    events.append(json.dumps({"type": "turn.started"}))
    if extra_messages:
        for txt in extra_messages:
            events.append(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": txt}}))
    events.append(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": final_text}}))
    events.append(json.dumps({"type": "turn.completed"}))
    return "\n".join(events)


class ExtractFinalTextTests(unittest.TestCase):
    def test_single_agent_message_extracted(self):
        txt, err = ADAPTER_MOD._extract_final_text(_codex_stream('{"schema":"dd-review-result/1"}'))
        self.assertIsNone(err)
        self.assertTrue(txt.startswith("{"))

    def test_multi_message_picks_last(self):
        txt, err = ADAPTER_MOD._extract_final_text(_codex_stream('{"schema":"dd-review-result/1","status":"FINDINGS"}', extra_messages=["intermediate", "another"]))
        self.assertIsNone(err)
        self.assertIn("FINDINGS", txt)

    def test_multiple_json_results_ambiguous(self):
        # Two JSON results -> should be considered ambiguous and fail
        stream = _codex_stream('{"schema":"dd-review-result/1","status":"PASS"}', extra_messages=['{"schema":"dd-review-result/1","status":"FINDINGS"}'])
        # Our adapter's logic: if more than one candidate is JSON with schema, it returns multiple final JSON results error
        # In this stream, there are two candidates that are JSON with schema -> should fail
        txt, err = ADAPTER_MOD._extract_final_text(stream)
        # The adapter currently checks for >1 json candidates and returns error, but our extra_messages first one is also JSON with schema
        # So it should be considered ambiguous
        self.assertIsNotNone(err)
        self.assertIn("multiple", err)

    def test_malformed_event_fails(self):
        bad = '{"type":"item.completed", "item": {"type":"agent_message", "text":"hi"'  # truncated
        txt, err = ADAPTER_MOD._extract_final_text(bad)
        self.assertIsNotNone(err)

    def test_missing_agent_message_fails(self):
        stream = json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}})
        txt, err = ADAPTER_MOD._extract_final_text(stream)
        self.assertIsNotNone(err)

    def test_empty_stdout_fails(self):
        txt, err = ADAPTER_MOD._extract_final_text("")
        self.assertIsNotNone(err)


class StrictJsonParseTests(unittest.TestCase):
    def test_valid_strict_json_passes(self):
        obj, err = ADAPTER_MOD._strict_json_parse('{"schema":"dd-review-result/1","backend":"codex-cli"}')
        self.assertIsNone(err)

    def test_code_fence_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('```json\n{"a":1}\n```')
        self.assertIsNotNone(err)

    def test_prose_wrapper_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('Here is result: {"a":1}')
        self.assertIsNotNone(err)

    def test_markdown_escapes_rejected(self):
        _, err = ADAPTER_MOD._strict_json_parse('{"evidence":"\\[test\\]"}')
        self.assertIsNotNone(err)


class ValidateResultTests(unittest.TestCase):
    def test_valid_findings_passes(self):
        req = {"base_sha": "a"*40, "head_sha": "b"*40, "scope": ["review.py"]}
        err = ADAPTER_MOD._validate_result(_valid_result("FINDINGS"), req)
        self.assertIsNone(err)

    def test_target_mismatch_rejected(self):
        req = {"base_sha": "a"*40, "head_sha": "b"*40, "scope": ["review.py"]}
        obj = _valid_result("FINDINGS")
        obj["target"]["head_sha"] = "c"*40
        self.assertIsNotNone(ADAPTER_MOD._validate_result(obj, req))

    def test_missing_finding_field_rejected(self):
        req = {"base_sha": "a"*40, "head_sha": "b"*40, "scope": ["review.py"]}
        obj = _valid_result("FINDINGS")
        del obj["findings"][0]["required_fix"]
        self.assertIsNotNone(ADAPTER_MOD._validate_result(obj, req))


class ValidateContinuationTests(unittest.TestCase):
    def test_absent_continuation_is_plain_initial(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({"schema": "dd-review-request/1"}))

    def test_resume_requires_handle(self):
        err = ADAPTER_MOD._validate_continuation({"continuation": {"form": "resume"}})
        self.assertIsNotNone(err)
        self.assertIn("handle", err)

    def test_unknown_form_rejected(self):
        err = ADAPTER_MOD._validate_continuation({"continuation": {"form": "fork"}})
        self.assertIsNotNone(err)
        self.assertIn("form", err)

    def test_non_mapping_rejected(self):
        err = ADAPTER_MOD._validate_continuation({"continuation": "resume"})
        self.assertIsNotNone(err)

    def test_explicit_initial_without_handle_ok(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({"continuation": {"form": "initial"}}))

    def test_resume_with_handle_ok(self):
        self.assertIsNone(ADAPTER_MOD._validate_continuation({"continuation": {"form": "resume", "handle": "t1"}}))


class ExtractSessionIdTests(unittest.TestCase):
    def test_thread_id_extracted_from_stream(self):
        sid = ADAPTER_MOD._extract_session_id(_codex_stream('{"schema":"dd-review-result/1"}'))
        self.assertEqual(sid, "t1")

    def test_missing_thread_started_returns_none(self):
        stream = "\n".join([
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}}),
        ])
        self.assertIsNone(ADAPTER_MOD._extract_session_id(stream))

    def test_malformed_lines_skipped(self):
        stream = "not json\n" + _codex_stream('{}')
        self.assertEqual(ADAPTER_MOD._extract_session_id(stream), "t1")

    def test_empty_stdout_returns_none(self):
        self.assertIsNone(ADAPTER_MOD._extract_session_id(""))


class AdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = tempfile.TemporaryDirectory()
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
        self.state.cleanup()

    def _register_thread(self, thread_id: str, sandbox: str = "read-only"):
        state_file = Path(self.state.name) / "threads.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        registry = {}
        if state_file.exists():
            registry = json.loads(state_file.read_text())
        registry.setdefault("threads", {})[thread_id] = {"sandbox": sandbox, "registered_at": "fixture"}
        state_file.write_text(json.dumps(registry))

    def _registered_threads(self):
        state_file = Path(self.state.name) / "threads.json"
        if not state_file.exists():
            return {}
        return json.loads(state_file.read_text()).get("threads", {})

    def request(self):
        return {
            "schema": "dd-review-request/1",
            "role": "strong-reviewer",
            "host": "codex",
            "repo": str(self.repo),
            "base_sha": self.base,
            "head_sha": self.head,
            "scope": ["review.py"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "routing_context": {"dispatch_boundary": "single-backend", "router_authority": False, "hop_count": 1, "dispatch_chain": ["codex-cli"], "selected_backend": "codex-cli"},
        }

    def _run_adapter(self, fake_stdout: str, exit_code: int = 0, req_override: dict | None = None):
        req = self.request()
        if req_override:
            req.update(req_override)
        # Patch target to match request SHAs for valid case
        # For generic tests, we use _valid_result with matching SHAs
        mock_completed = mock.Mock()
        mock_completed.stdout = fake_stdout
        mock_completed.stderr = ""
        mock_completed.returncode = exit_code
        orig_run = subprocess.run
        with mock.patch("subprocess.run") as mocked, \
                mock.patch.dict("os.environ", {"CODEX_REVIEW_STATE_DIR": self.state.name}):
            def side(cmd, **kw):
                if cmd[0] == "codex":
                    return mock_completed
                return orig_run(cmd, **kw)
            mocked.side_effect = side
            import io, sys
            with mock.patch("sys.stdin", io.StringIO(json.dumps(req))):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as fake_out:
                    with mock.patch.object(sys, "argv", ["codex-review", "review"]):
                        ret = ADAPTER_MOD.main()
                        codex_cmds = [c.args[0] for c in mocked.call_args_list if c.args and c.args[0] and c.args[0][0] == "codex"]
                        return ret, fake_out.getvalue(), codex_cmds

    def test_valid_findings_through_adapter(self):
        # Need to make the valid result's target match the request's SHAs
        req = self.request()
        result = _valid_result("FINDINGS")
        result["target"] = {"base_sha": req["base_sha"], "head_sha": req["head_sha"], "scope": ["review.py"]}
        stream = _codex_stream(json.dumps(result))
        ret, out, _cmds = self._run_adapter(stream)
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "FINDINGS")
        # No continuation -> legacy single-hop: no session contract, sandbox pinned
        self.assertNotIn("session", obj)
        self.assertEqual(_cmds, [["codex", "exec", "--sandbox", "read-only", "--json"]])
        # Provenance: the thread this adapter just created is registered read-only
        self.assertIn("t1", self._registered_threads())
        self.assertEqual(self._registered_threads()["t1"]["sandbox"], "read-only")

    def _valid_stream(self):
        req = self.request()
        result = _valid_result("FINDINGS")
        result["target"] = {"base_sha": req["base_sha"], "head_sha": req["head_sha"], "scope": ["review.py"]}
        return _codex_stream(json.dumps(result))

    def test_resume_pins_invocation_and_reports_session(self):
        self._register_thread("t1")
        ret, out, cmds = self._run_adapter(
            self._valid_stream(),
            req_override={"continuation": {"form": "resume", "handle": "t1"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        # FR-MB-015: resume pins via `codex exec resume <handle>`.  --sandbox is
        # not accepted on resume and the -c override is ineffective (contrast
        # evidence), so the sandbox is inherited; acceptance rests on provenance.
        self.assertEqual(cmds, [["codex", "exec", "resume", "t1", "--json"]])
        # FR-MB-016: engine-proven session identity, matching the requested handle
        self.assertEqual(obj["session"], {"form": "resume", "handle": "t1"})
        # A resume turn re-enters an existing thread and registers nothing new
        self.assertEqual(list(self._registered_threads()), ["t1"])

    def test_resume_unregistered_handle_blocked_before_invocation(self):
        ret, out, cmds = self._run_adapter(
            self._valid_stream(),
            req_override={"continuation": {"form": "resume", "handle": "rogue"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertEqual(obj["failure_category"], "session_resume_mismatch")
        self.assertEqual(cmds, [])

    def test_resume_non_readonly_registration_blocked(self):
        self._register_thread("t-ww", sandbox="workspace-write")
        ret, out, cmds = self._run_adapter(
            self._valid_stream(),
            req_override={"continuation": {"form": "resume", "handle": "t-ww"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertEqual(obj["failure_category"], "session_resume_mismatch")
        self.assertEqual(cmds, [])

    def test_explicit_initial_keeps_sandbox_form_and_reports_session(self):
        ret, out, cmds = self._run_adapter(
            self._valid_stream(),
            req_override={"continuation": {"form": "initial"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        self.assertEqual(cmds, [["codex", "exec", "--sandbox", "read-only", "--json"]])
        self.assertEqual(obj["session"], {"form": "initial", "handle": "t1"})

    def test_resume_without_engine_identity_keeps_session_absent(self):
        # Build a stream without thread.started: final agent_message is the valid result JSON
        result = _valid_result("FINDINGS")
        req = self.request()
        result["target"] = {"base_sha": req["base_sha"], "head_sha": req["head_sha"], "scope": ["review.py"]}
        stream = "\n".join([
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(result)}}),
            json.dumps({"type": "turn.completed"}),
        ])
        ret, out, _cmds = self._run_adapter(
            stream,
            req_override={"continuation": {"form": "resume", "handle": "t1"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        # Fail-closed: no fabricated identity; Router turns the absence into
        # session_resume_mismatch for a requested resume continuation.
        self.assertNotIn("session", obj)

    def test_code_fence_becomes_schema_invalid(self):
        stream = _codex_stream('```json\n{"schema":"dd-review-result/1"}\n```')
        ret, out, _ = self._run_adapter(stream)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertEqual(obj["failure_category"], "schema_invalid")

    def test_missing_final_text_becomes_review_incomplete(self):
        stream = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})
        ret, out, _ = self._run_adapter(stream)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertEqual(obj["failure_category"], "review_incomplete")

    def test_availability_exit_propagated(self):
        ret, _, _ = self._run_adapter(_codex_stream('{}'), exit_code=69)
        self.assertEqual(ret, 69)

    def test_transient_exit_propagated(self):
        ret, _, _ = self._run_adapter(_codex_stream('{}'), exit_code=75)
        self.assertEqual(ret, 75)

    def test_other_exit_becomes_execution_failed(self):
        ret, out, _ = self._run_adapter(_codex_stream('{}'), exit_code=1)
        obj = json.loads(out)
        self.assertEqual(obj["failure_category"], "backend_execution_failed")

    def test_invalid_continuation_blocked_without_invoking_codex(self):
        ret, out, cmds = self._run_adapter(
            self._valid_stream(),
            req_override={"continuation": {"form": "resume"}},
        )
        self.assertEqual(ret, 0)
        obj = json.loads(out)
        self.assertEqual(obj["status"], "BLOCKED")
        self.assertEqual(obj["failure_category"], "schema_invalid")
        # Fail-closed before any provider invocation
        self.assertEqual(cmds, [])


if __name__ == "__main__":
    unittest.main()

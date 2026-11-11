#!/usr/bin/env python3
"""Phase A tests for the mcp-review thin adapter.

These tests use a local fake Streamable HTTP MCP endpoint.  They never start
the real chatgpt-review MCP server and never exercise L6 or L7.
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "agents" / "mcp-review"
REPO_ROOT = ROOT.parents[1]
PROVIDER_SCHEMA = "dd-review-provider/1"
RESULT_SCHEMA = "dd-review-result/1"
TOOLS = ["chatgpt_send", "chatgpt_send_file", "chatgpt_get_result"]


def _load_adapter() -> Any:
    loader = importlib.machinery.SourceFileLoader("mcp_review_adapter", str(ADAPTER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ADAPTER_MODULE = _load_adapter()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class FakeMcpHandler(BaseHTTPRequestHandler):
    server_version = "FakeMcp/1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    @property
    def state(self) -> "FakeMcpServer":
        return self.server  # type: ignore[return-value]

    def _send_json(self, value: Dict[str, Any], *, session: bool = False) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if session:
            self.send_header("Mcp-Session-Id", self.state.session_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self) -> None:
        self.send_response(202)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.state.requests.append(payload)
        method = payload.get("method")
        if method == "initialize":
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {"name": "fake", "version": "1"},
                    },
                },
                session=True,
            )
            return
        if method == "notifications/initialized":
            self._send_empty()
            return
        if method == "tools/list":
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "result": {"tools": [{"name": name, "description": "fake"} for name in self.state.tool_names]},
                }
            )
            return
        if method != "tools/call":
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {"code": -32601, "message": "unsupported fake method"},
                }
            )
            return

        name = payload.get("params", {}).get("name")
        arguments = payload.get("params", {}).get("arguments", {})
        self.state.tool_calls.append({"name": name, "arguments": arguments})
        if name == "chatgpt_send":
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "result": {"content": [{"type": "text", "text": "已提交，task_id=fake-task"}]},
                }
            )
            return
        if name == "chatgpt_get_result":
            self.state.poll_count += 1
            if self.state.poll_count == 1:
                self._send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": payload.get("id"),
                        "result": {
                            "isError": True,
                            "content": [{"type": "text", "text": "[RUNNING] fake-task"}],
                        },
                    }
                )
            else:
                result_text = self.state.provider_text
                self._send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": payload.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "conversation_id: fake-conversation\n"
                                    "conversation_url: https://chatgpt.com/c/fake-conversation\n\n"
                                    + result_text,
                                }
                            ]
                        },
                    }
                )
            return
        self._send_json(
            {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32601, "message": f"unsupported fake tool: {name}"},
            }
        )


class FakeMcpServer(ThreadingHTTPServer):
    def __init__(self, provider: Dict[str, Any], tool_names: Optional[List[str]] = None):
        super().__init__(("127.0.0.1", 0), FakeMcpHandler)
        self.session_id = "fake-session"
        self.provider_text = json.dumps(provider, ensure_ascii=False, sort_keys=True)
        self.tool_names = list(tool_names or TOOLS)
        self.requests: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.poll_count = 0
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/mcp"

    def __enter__(self) -> "FakeMcpServer":
        self.thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)


class AdapterPhaseATests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Phase A Test"], check=True)
        (self.repo / "review.py").write_text("print('base')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True)
        self.base = _git(self.repo, "rev-parse", "HEAD")
        (self.repo / "review.py").write_text("print('head')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "head"], check=True)
        self.head = _git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, **overrides: Any) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "schema": "dd-review-request/1",
            "role": "strong-reviewer",
            "host": "codex",
            "repo": str(self.repo),
            "base_sha": self.base,
            "head_sha": self.head,
            "scope": ["review.py"],
            "verification": [{"name": "unit", "status": "passed", "evidence": "fixture-pass"}],
            "routing_context": {
                "dispatch_boundary": "single-backend",
                "router_authority": False,
                "hop_count": 1,
                "dispatch_chain": ["mcp-review"],
                "selected_backend": "mcp-review",
            },
        }
        request.update(overrides)
        return request

    def provider(self, **overrides: Any) -> Dict[str, Any]:
        value: Dict[str, Any] = {
            "schema": PROVIDER_SCHEMA,
            "reviewer": "fake-reviewer",
            "status": "PASS",
            "reviewed": ["review.py"],
            "unreadable": [],
            "findings": [],
            "evidence": ["fake provider reviewed frozen material"],
            "failure_category": None,
        }
        value.update(overrides)
        return value

    def run_adapter(self, request: Dict[str, Any], server: Optional[FakeMcpServer] = None) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "MCP_REVIEW_POLL_INTERVAL_SECONDS": "0",
        }
        if server is not None:
            env["MCP_REVIEW_ENDPOINT"] = server.endpoint
        return subprocess.run(
            [str(ADAPTER), "review"],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def result(self, completed: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
        self.assertTrue(completed.stdout, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertIsInstance(value, dict)
        return value

    def test_executable_and_subcommand_contract(self) -> None:
        self.assertTrue(os.access(ADAPTER, os.X_OK))
        completed = subprocess.run([str(ADAPTER)], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 64)
        self.assertIn("usage: mcp-review review", completed.stderr)

    def test_valid_fake_http_flow_is_single_send_only_and_workspace_unchanged(self) -> None:
        before_head = _git(self.repo, "rev-parse", "HEAD")
        before_status = _git(self.repo, "status", "--porcelain=v1", "--untracked-files=all")
        before_diff = _git(self.repo, "diff", "--binary", self.base, self.head, "--", "review.py")
        with FakeMcpServer(self.provider()) as server:
            completed = self.run_adapter(self.request(), server)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = self.result(completed)
            self.assertEqual(result["schema"], RESULT_SCHEMA)
            self.assertEqual(result["backend"], "mcp-review")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["target"]["base_sha"], self.base)
            self.assertEqual(result["target"]["head_sha"], self.head)
            self.assertEqual(result["target"]["scope"], ["review.py"])
            self.assertFalse(result["readonly_confirmation"]["confirmed"])
            self.assertEqual([call["name"] for call in server.tool_calls], [
                "chatgpt_send",
                "chatgpt_get_result",
                "chatgpt_get_result",
            ])
            self.assertNotIn("chatgpt_send_file", [call["name"] for call in server.tool_calls])
            send_call = server.tool_calls[0]
            sent = json.dumps(send_call["arguments"], ensure_ascii=False)
            self.assertNotIn(str(self.repo), sent)
            self.assertNotIn("routing_context", sent)
            self.assertNotIn("authorization", sent)
            self.assertNotIn("readonly_evidence", sent)
            self.assertNotIn("internal_attestation", sent)
            self.assertNotIn("phase-d-evidence", sent)
            self.assertNotIn("native_guard", sent)
            self.assertNotIn("host_metadata", sent)
            self.assertIn(self.base, send_call["arguments"]["content"])
            self.assertIn(self.head, send_call["arguments"]["content"])
            self.assertIn("review.py", send_call["arguments"]["content"])
            self.assertNotIn(str(self.repo), send_call["arguments"]["instruction"])
            self.assertEqual(server.tool_names, TOOLS)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), before_head)
        self.assertEqual(_git(self.repo, "status", "--porcelain=v1", "--untracked-files=all"), before_status)
        self.assertEqual(_git(self.repo, "diff", "--binary", self.base, self.head, "--", "review.py"), before_diff)

    def test_snapshot_is_deterministic_and_contains_only_relative_material(self) -> None:
        request = ADAPTER_MODULE._validate_request(self.request())
        first, first_digest = ADAPTER_MODULE._snapshot(self.repo, request)
        second, second_digest = ADAPTER_MODULE._snapshot(self.repo, request)
        self.assertEqual(first, second)
        self.assertEqual(first_digest, second_digest)
        self.assertEqual(first_digest, hashlib.sha256(first.encode("utf-8")).hexdigest())
        self.assertNotIn(str(self.repo), first)
        self.assertIn('"scope":["review.py"]', first)

    def test_request_rejects_control_metadata_and_absolute_scope(self) -> None:
        request = self.request(external_review={"authorization": "approved"})
        completed = self.run_adapter(request)
        result = self.result(completed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "security_policy_violation")

        request = self.request(scope=[str(self.repo / "review.py")])
        completed = self.run_adapter(request)
        result = self.result(completed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "security_policy_violation")

    def test_frozen_baseline_rejects_dirty_or_mismatched_worktree(self) -> None:
        request = self.request(head_sha=self.base)
        result = self.result(self.run_adapter(request))
        self.assertEqual(result["failure_category"], "baseline_mismatch")

        (self.repo / "untracked.txt").write_text("must remain", encoding="utf-8")
        result = self.result(self.run_adapter(self.request()))
        self.assertEqual(result["failure_category"], "baseline_mismatch")

    def test_exact_tool_allowlist_blocks_extra_workspace_capability(self) -> None:
        with FakeMcpServer(self.provider(), TOOLS + ["workspace_write"]) as server:
            completed = self.run_adapter(self.request(), server)
            self.assertEqual(completed.returncode, 0)
            result = self.result(completed)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["failure_category"], "capability_unavailable")
            self.assertEqual(server.tool_calls, [])

    def test_invalid_provider_json_is_blocked_without_markdown_repair(self) -> None:
        for provider_text in [
            "not json",
            "```json\n" + json.dumps(self.provider()) + "\n```",
        ]:
            with self.subTest(provider_text=provider_text), FakeMcpServer(self.provider()) as server:
                server.provider_text = provider_text
                result = self.result(self.run_adapter(self.request(), server))
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["failure_category"], "schema_invalid")

    def test_incomplete_scope_is_blocked(self) -> None:
        provider = self.provider(status="FINDINGS", reviewed=[], unreadable=[], findings=[{
            "id": "F-1",
            "severity": "MEDIUM",
            "classification": "FINDING",
            "change_risk": "LOW",
            "location": "review.py:1",
            "evidence": "fake",
            "required_fix": "fix",
        }])
        with FakeMcpServer(provider) as server:
            result = self.result(self.run_adapter(self.request(), server))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "evidence_mismatch")

    def test_oversized_snapshot_is_blocked_before_mcp(self) -> None:
        large = "x" * (ADAPTER_MODULE.MAX_SNAPSHOT_CHARS + 1)
        (self.repo / "review.py").write_text(large, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "review.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "large"], check=True)
        request = self.request(base_sha=self.head, head_sha=_git(self.repo, "rev-parse", "HEAD"))
        with FakeMcpServer(self.provider()) as server:
            result = self.result(self.run_adapter(request, server))
            self.assertEqual(server.requests, [])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_category"], "review_incomplete")

    def test_no_fallback_or_second_dispatch_is_present_in_adapter(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertNotIn("dispatch-review.py", source)
        self.assertNotIn("codex-cli", source)
        self.assertNotIn("opencode", source)
        self.assertIn("single-backend", source)
        self.assertIn("chatgpt_send_file", source)


if __name__ == "__main__":
    unittest.main()

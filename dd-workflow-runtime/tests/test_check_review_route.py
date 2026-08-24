#!/usr/bin/env python3
"""Regression tests for the fail-closed Codex native-review route guard."""

import argparse
import contextlib
import importlib.util
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "agents" / "check-review-route.py"
SPEC = importlib.util.spec_from_file_location("check_review_route", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def resolve_guard(
    *,
    review_level: str,
    requested_execution: str,
    parent_sandbox: str,
    external_status: str,
):
    args = argparse.Namespace(
        review_level=review_level,
        requested_execution=requested_execution,
        parent_sandbox=parent_sandbox,
        sandbox_evidence="unit-test-fixture",
        external_status=external_status,
    )
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        returncode = GUARD.resolve(args)
    return returncode, json.loads(output.getvalue())


class CheckReviewRouteTests(unittest.TestCase):
    def test_low_auto_stays_inline_even_under_danger_parent(self) -> None:
        returncode, payload = resolve_guard(
            review_level="low",
            requested_execution="auto",
            parent_sandbox="danger-full-access",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertEqual(payload["resolved_execution"], "inline")

    def test_standard_auto_uses_native_under_read_only_parent(self) -> None:
        returncode, payload = resolve_guard(
            review_level="standard",
            requested_execution="auto",
            parent_sandbox="read-only",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertEqual(payload["resolved_execution"], "native-agent")

    def test_workspace_write_parent_is_unproven_and_blocks(self) -> None:
        returncode, payload = resolve_guard(
            review_level="standard",
            requested_execution="auto",
            parent_sandbox="workspace-write",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(payload["decision"], "BLOCKED")
        self.assertEqual(payload["reason"], "native-review-readonly-unproven")
        self.assertFalse(payload["native_spawn_allowed"])

    def test_danger_parent_without_external_review_blocks_before_spawn(self) -> None:
        returncode, payload = resolve_guard(
            review_level="high",
            requested_execution="native-agent",
            parent_sandbox="danger-full-access",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(payload["decision"], "BLOCKED")
        self.assertEqual(payload["reason"], "native-review-readonly-not-enforceable")
        self.assertFalse(payload["native_spawn_allowed"])

    def test_danger_parent_routes_to_authorized_external_review(self) -> None:
        returncode, payload = resolve_guard(
            review_level="high",
            requested_execution="auto",
            parent_sandbox="dangerously-bypass-approvals-and-sandbox",
            external_status="available-authorized",
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertEqual(payload["resolved_execution"], "external")
        self.assertFalse(payload["native_spawn_allowed"])

    def test_danger_parent_never_silently_sends_unapproved_external_context(self) -> None:
        returncode, payload = resolve_guard(
            review_level="standard",
            requested_execution="auto",
            parent_sandbox="danger-full-access",
            external_status="available-unapproved",
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(payload["decision"], "BLOCKED")
        self.assertEqual(payload["reason"], "external-authorization-required")
        self.assertFalse(payload["native_spawn_allowed"])

    def test_unknown_parent_sandbox_fails_closed(self) -> None:
        returncode, payload = resolve_guard(
            review_level="standard",
            requested_execution="auto",
            parent_sandbox="unknown",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(payload["decision"], "BLOCKED")
        self.assertEqual(payload["reason"], "parent-sandbox-unknown")
        self.assertFalse(payload["native_spawn_allowed"])

    def test_standard_inline_is_rejected(self) -> None:
        returncode, payload = resolve_guard(
            review_level="standard",
            requested_execution="inline",
            parent_sandbox="workspace-write",
            external_status="unavailable",
        )
        self.assertEqual(returncode, 2)
        self.assertEqual(payload["decision"], "BLOCKED")
        self.assertEqual(payload["reason"], "review-parameter-conflict")

    def test_auto_detects_disabled_policy_from_thread_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_db = Path(directory) / "state.sqlite"
            with sqlite3.connect(state_db) as db:
                db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, sandbox_policy TEXT NOT NULL)")
                db.execute(
                    "INSERT INTO threads VALUES (?, ?)",
                    ("danger-thread", '{"type":"disabled"}'),
                )
            sandbox, evidence = GUARD.detect_parent_sandbox("danger-thread", state_db)
        self.assertEqual(sandbox, "danger-full-access")
        self.assertEqual(evidence, "codex-thread-metadata:danger-thread")

    def test_auto_detects_read_only_policy_from_thread_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_db = Path(directory) / "state.sqlite"
            with sqlite3.connect(state_db) as db:
                db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, sandbox_policy TEXT NOT NULL)")
                db.execute(
                    "INSERT INTO threads VALUES (?, ?)",
                    (
                        "read-thread",
                        '{"type":"managed","file_system":{"type":"restricted","entries":'
                        '[{"access":"read"}]}}',
                    ),
                )
            sandbox, evidence = GUARD.detect_parent_sandbox("read-thread", state_db)
        self.assertEqual(sandbox, "read-only")
        self.assertEqual(evidence, "codex-thread-metadata:read-thread")

    def test_malformed_and_mixed_policies_fail_closed(self) -> None:
        policies = (
            "null",
            "[]",
            '"read-only"',
            '{"type":"managed","file_system":null}',
            '{"type":"managed","file_system":{"entries":null}}',
            '{"type":"managed","file_system":{"entries":[]}}',
            '{"type":"managed","file_system":{"type":"unrestricted",'
            '"entries":[{"access":"read"}]}}',
            '{"type":"managed","file_system":{"type":"restricted","entries":'
            '[{"access":"read"},{"access":"unexpected"}]}}',
            '{"type":"managed","file_system":{"type":"restricted","entries":'
            '[{"access":"read"},null]}}',
        )
        for policy in policies:
            with self.subTest(policy=policy):
                self.assertEqual(GUARD.classify_sandbox_policy(policy), "unknown")

    def test_restricted_mixed_read_write_policy_is_never_read_only(self) -> None:
        policy = (
            '{"type":"managed","file_system":{"type":"restricted","entries":'
            '[{"access":"read"},{"access":"write"}]}}'
        )
        self.assertEqual(GUARD.classify_sandbox_policy(policy), "workspace-write")

    def test_production_cli_rejects_evidence_override_options(self) -> None:
        for option, value in (
            ("--parent-sandbox", "read-only"),
            ("--thread-id", "forged-thread"),
            ("--state-db", "/tmp/forged-state.sqlite"),
        ):
            with self.subTest(option=option):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--review-level", "high",
                        "--requested-execution", "auto",
                        "--external-status", "unavailable",
                        option, value,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=tempfile.gettempdir(),
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"unrecognized arguments: {option}", result.stderr)


if __name__ == "__main__":
    unittest.main()

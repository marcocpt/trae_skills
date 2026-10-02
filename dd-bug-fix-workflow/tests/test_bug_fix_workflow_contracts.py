#!/usr/bin/env python3
"""Contract tests for the bug-fix workflow.

Scope: only the contracts this skill owns. Shared semantics (state schema,
checkpoint write-back, takeover, board projection, the tracking binding attempt)
stay owned by `dd-workflow-runtime/references/task-tracking.md`; the assertions
below verify that this skill keeps a call site at the right Stage and does not
restate the owner's rules.

Design rationale: docs/AI/2026-10-02-task-tracking-projection-design.md §6.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"
DIAG = SKILL_ROOT / "references" / "diagnosis-and-verification.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def h2_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    head_re = re.compile(rf"^## {re.escape(heading)}$")
    start = None
    for i, line in enumerate(lines):
        if start is None:
            if head_re.match(line):
                start = i + 1
        elif re.match(r"^#{1,2} ", line):
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"section not found: {heading}")
    return "\n".join(lines[start:])


class TestTrackingHookDelegatesToOwner(unittest.TestCase):
    """task-tracking §2/§3: the bug Environment hook owns the call site only.

    Primary protection is structural: exactly two lines in the Environment section
    may touch tracking — the call-site hook and the Gate persistence clause.
    """

    TOKENS = ("task-tracking", "tracking", "绑定", "Issue", "sync", "同步")

    def _env(self) -> str:
        return h2_section(read(DIAG), "2. Environment")

    def test_environment_has_only_the_hook_and_the_gate_clause(self):
        lines = [ln.strip() for ln in self._env().splitlines() if any(t in ln for t in self.TOKENS)]
        self.assertEqual(
            len(lines), 2,
            f"Environment must contain exactly the tracking hook and the Gate clause, got {lines}",
        )
        hook, gate_clause = lines
        for required in ("task-tracking", "§3", "持久化结果", "不阻塞本 Stage"):
            self.assertIn(required, hook, f"hook must require {required}: {hook}")
        self.assertIn("owner 合同", gate_clause,
                      "Gate clause must defer to the owner-defined result")
        self.assertIn("持久化", gate_clause, "Gate must require the result to be persisted")

    def test_hook_does_not_become_a_blocking_precondition(self):
        env = self._env()
        self.assertIn("完全由该合同定义", env, "hook must defer semantics to the owner")
        self.assertIn("不阻塞本 Stage", env, "tracking outcomes must stay non-blocking")

    def test_owner_result_encoding_stays_out_of_the_gate(self):
        gate = self._env().split("Gate：", 1)[1]
        for token in ("sync_reason", "sync=", "user-declined", "binding-ambiguous",
                      "create-outcome-unknown", "provider-unavailable", "no-policy"):
            self.assertNotIn(token, gate,
                             f"bug Environment Gate must not enumerate owner result encoding ({token})")


class TestSkillRouterTracksOwner(unittest.TestCase):
    def test_router_delegates_and_stays_non_blocking(self):
        text = read(SKILL_MD)
        self.assertIn("task-tracking", text, "router must name the owning contract")
        self.assertIn("§3", text, "router must delegate the attempt to the owner's §3")
        self.assertIn("不阻塞本 Stage", text, "tracking outcomes must stay non-blocking")

    def test_router_does_not_restate_owner_authorization(self):
        text = read(SKILL_MD)
        for token in ("常设授权", "创建或绑定", "（默认新建", "§8.1"):
            self.assertNotIn(
                token, text,
                f"bug SKILL.md must not restate owner authorization ({token})",
            )

    def test_bug_id_is_not_issue_number(self):
        self.assertIn("`bug_id` 不重载为 Issue 号", read(SKILL_MD),
                      "bug_id must not double as the Issue number (tracking owns issue_number)")


if __name__ == "__main__":
    unittest.main()

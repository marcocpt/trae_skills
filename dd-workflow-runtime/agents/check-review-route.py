#!/usr/bin/env python3
"""Fail-closed pre-spawn guard for Codex native strong-review routing.

The Codex parent sandbox is reapplied to child agents. A danger-full-access or
unknown parent therefore cannot enforce the strong-reviewer's read-only
contract. This guard resolves the review path before any native reviewer is
spawned and emits a machine-readable decision.
"""

import argparse
import json
import os
import pwd
import sqlite3
import sys
from pathlib import Path
from typing import Optional, Tuple


SAFE_PARENT_SANDBOXES = {"read-only"}
UNSAFE_PARENT_SANDBOXES = {
    "danger-full-access",
    "dangerously-bypass-approvals-and-sandbox",
}


def classify_sandbox_policy(raw_policy: str) -> str:
    """Map Codex thread metadata to the guard's stable sandbox vocabulary."""
    try:
        policy = json.loads(raw_policy)
    except (TypeError, json.JSONDecodeError):
        return "unknown"
    if not isinstance(policy, dict):
        return "unknown"
    policy_type = policy.get("type")
    if policy_type in {"disabled", "danger-full-access"}:
        return "danger-full-access"
    if policy_type in {"read-only", "workspace-write"}:
        return policy_type
    if policy_type != "managed":
        return "unknown"
    file_system = policy.get("file_system")
    if not isinstance(file_system, dict):
        return "unknown"
    if file_system.get("type") != "restricted":
        return "unknown"
    entries = file_system.get("entries")
    if not isinstance(entries, list) or not entries:
        return "unknown"
    if any(not isinstance(entry, dict) for entry in entries):
        return "unknown"
    accesses = [entry.get("access") for entry in entries]
    if any(access not in {"read", "write"} for access in accesses):
        return "unknown"
    if "write" in accesses:
        return "workspace-write"
    if all(access == "read" for access in accesses):
        return "read-only"
    return "unknown"


def detect_parent_sandbox(thread_id: Optional[str], state_db: Path) -> Tuple[str, str]:
    """Read the current parent policy from Codex's persisted thread metadata."""
    if not thread_id:
        return "unknown", "missing-CODEX_THREAD_ID"
    try:
        with sqlite3.connect(f"file:{state_db}?mode=ro", uri=True) as db:
            row = db.execute(
                "SELECT sandbox_policy FROM threads WHERE id = ?",
                (thread_id,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return "unknown", f"unreadable-thread-metadata:{state_db}"
    if not row:
        return "unknown", f"thread-not-found:{thread_id}"
    return classify_sandbox_policy(row[0]), f"codex-thread-metadata:{thread_id}"


def emit(
    args: argparse.Namespace,
    *,
    decision: str,
    resolved_execution: Optional[str],
    native_spawn_allowed: bool,
    reason: str,
    next_action: str,
) -> int:
    print(
        json.dumps(
            {
                "schema": "dd-review-route-decision/1",
                "host": "codex",
                "review_level": args.review_level,
                "requested_execution": args.requested_execution,
                "parent_sandbox": args.parent_sandbox,
                "sandbox_evidence": args.sandbox_evidence,
                "external_status": args.external_status,
                "decision": decision,
                "resolved_execution": resolved_execution,
                "native_spawn_allowed": native_spawn_allowed,
                "reason": reason,
                "next_action": next_action,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if decision == "ALLOW" else 2


def resolve_external(args: argparse.Namespace, *, fallback_reason: str) -> int:
    if args.external_status == "available-authorized":
        return emit(
            args,
            decision="ALLOW",
            resolved_execution="external",
            native_spawn_allowed=False,
            reason=fallback_reason,
            next_action="persist external route, then dispatch only the authorized context",
        )
    if args.external_status == "available-unapproved":
        return emit(
            args,
            decision="BLOCKED",
            resolved_execution=None,
            native_spawn_allowed=False,
            reason="external-authorization-required",
            next_action="request approval for the exact outbound context; do not spawn native reviewer",
        )
    return emit(
        args,
        decision="BLOCKED",
        resolved_execution=None,
        native_spawn_allowed=False,
        reason=fallback_reason,
        next_action="provide an enforceably read-only reviewer path or keep the review Gate blocked",
    )


def resolve(args: argparse.Namespace) -> int:
    if args.review_level in {"standard", "high"} and args.requested_execution == "inline":
        return emit(
            args,
            decision="BLOCKED",
            resolved_execution=None,
            native_spawn_allowed=False,
            reason="review-parameter-conflict",
            next_action="choose native-agent, external, or auto for standard/high review",
        )

    if args.requested_execution == "external":
        return resolve_external(args, fallback_reason="external-review-unavailable")

    if args.review_level == "low" and args.requested_execution in {"auto", "inline"}:
        return emit(
            args,
            decision="ALLOW",
            resolved_execution="inline",
            native_spawn_allowed=False,
            reason="low-risk-inline-review",
            next_action="run the required A/B/C inline review without spawning an independent reviewer",
        )

    if args.parent_sandbox in SAFE_PARENT_SANDBOXES:
        return emit(
            args,
            decision="ALLOW",
            resolved_execution="native-agent",
            native_spawn_allowed=True,
            reason="native-review-readonly-enforceable",
            next_action="persist native route and frozen baseline before spawning strong-reviewer",
        )

    if args.parent_sandbox in UNSAFE_PARENT_SANDBOXES:
        return resolve_external(
            args,
            fallback_reason="native-review-readonly-not-enforceable",
        )

    if args.parent_sandbox == "workspace-write":
        return resolve_external(
            args,
            fallback_reason="native-review-readonly-unproven",
        )

    return resolve_external(args, fallback_reason="parent-sandbox-unknown")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review-level",
        choices=("low", "standard", "high"),
        required=True,
    )
    parser.add_argument(
        "--requested-execution",
        choices=("inline", "native-agent", "external", "auto"),
        required=True,
    )
    parser.add_argument(
        "--external-status",
        choices=("unavailable", "available-unapproved", "available-authorized"),
        required=True,
        help="Availability and per-context authorization state of external review.",
    )
    args = parser.parse_args()
    # Production evidence is deliberately not CLI-injectable. The current
    # thread id comes from Codex, and the metadata database is anchored to the
    # account home recorded by the operating system rather than $HOME.
    state_db = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".codex" / "state_5.sqlite"
    args.parent_sandbox, args.sandbox_evidence = detect_parent_sandbox(
        os.environ.get("CODEX_THREAD_ID"),
        state_db,
    )
    return resolve(args)


if __name__ == "__main__":
    sys.exit(main())

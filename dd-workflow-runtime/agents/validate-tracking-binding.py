#!/usr/bin/env python3
"""Environment Gate check: has the tracking binding attempt been recorded?

Deterministic, offline state-shape checker. It answers exactly one question —
"was a binding attempt recorded in this state?" — and never touches the network,
credentials, git, or any remote. It performs no reconciliation and creates
nothing (Design §3.3).

Semantic owner: dd-workflow-runtime/references/task-tracking.md.
This file is its mechanical realization, not a second source of truth: the only
FAIL condition mirrors that contract's "not attempted and not recorded, yet the
Environment Gate passed" red line. The vocabularies it compares against are
locked against the owner from the other side by
tests/test_task_tracking.py::TestVocabularyDrift.

Exit codes:
    0  attempt recorded (Gate may pass)
    1  attempt not recorded (Environment Gate must not pass)
    2  usage / unreadable input

Usage:
    python3 validate-tracking-binding.py --state <path/to/state.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# The vocabulary below mirrors task-tracking.md §2 and §4. It is kept as
# module-level constants so tests/test_task_tracking.py::TestVocabularyDrift can
# compare them against the owner contract in both directions.

# task-tracking §2: sync row of the enum table.
SYNC_VALUES = frozenset({"synced", "not-synced", "not-authorized", "disabled"})

# task-tracking §4: sync_reason column of the failure matrix.
SYNC_REASONS = frozenset({
    "remote-unresolvable",
    "issue-missing",
    "no-policy",
    "user-declined",
    "binding-ambiguous",
    "create-outcome-unknown",
    "legacy-tracking-unknown",
    "no-issue-capable-remote",
    "provider-unavailable",
})

# task-tracking §2: `sync` values that are a complete record on their own.
# §4 spells both of these rows with `—` in the sync_reason column, so requiring a
# reason for them would fail a state the owner explicitly permits.
SELF_RECORDING_SYNC = frozenset({"synced", "disabled"})

# task-tracking §2: `sync` values that are a record only together with a reason.
REASON_REQUIRED_SYNC = frozenset({"not-synced", "not-authorized"})

# task-tracking §2: providers registered in this contract.
SUPPORTED_PROVIDERS = frozenset({"github"})

# task-tracking §2: the only nested fields of the tracking object.
TRACKING_FIELDS = frozenset({
    "provider", "repository", "issue_number",
    "sync", "sync_reason", "pending_checkpoint", "last_checkpoint_ref",
})

# task-tracking §2: workflow types under the mandatory-attempt constraint.
MANDATORY_WORKFLOW_TYPES = frozenset({"feature-development", "bug-fix"})

# task-tracking §2/§3.2: schema_version at or above this narrows a null tracking
# to "never attempted". Below it, a null is historically unclassified.
CURRENT_SCHEMA_VERSION = 2


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(state: dict) -> tuple[bool, str]:
    """Return (recorded, reason) for one workflow state.

    Mirrors Design §3.2 dispatch order:
      1. workflow type out of scope            -> recorded
      2. legacy schema with no tracking        -> recorded (never force-attempt)
      3. tracking not an object               -> not recorded
      4. provider well-formedness             -> not recorded
      5. the owner's four recorded shapes      -> recorded
      6. otherwise                            -> not recorded
    """
    wf_type = state.get("workflow_type")
    if wf_type not in MANDATORY_WORKFLOW_TYPES:
        return True, f"workflow_type={wf_type!r} is out of scope (task-tracking §12)"

    version = state.get("schema_version")
    tracking = state.get("tracking")

    legacy = not isinstance(version, int) or version < CURRENT_SCHEMA_VERSION
    if legacy and tracking is None:
        return True, "pre-contract state (task-tracking §3.2): no forced attempt"

    if not isinstance(tracking, dict):
        return False, "tracking absent or null under the current schema: never attempted"

    provider = tracking.get("provider")
    if provider is not None and provider not in SUPPORTED_PROVIDERS:
        return False, f"provider={provider!r} is not a registered provider (task-tracking §2)"

    issue_number = tracking.get("issue_number")
    if issue_number is not None:
        return True, f"bound to issue #{issue_number}"

    sync = tracking.get("sync")
    reason = tracking.get("sync_reason")

    if sync in SELF_RECORDING_SYNC:
        return True, f"sync={sync!r} records the attempt without a reason (task-tracking §4)"
    if sync in REASON_REQUIRED_SYNC and reason in SYNC_REASONS:
        return True, f"sync={sync!r} with sync_reason={reason!r}"
    if sync is not None and sync not in SYNC_VALUES:
        return False, f"sync={sync!r} is outside the task-tracking §2 vocabulary"

    return False, "neither a bound issue nor a recorded sync outcome"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a workflow state records a tracking binding attempt.")
    parser.add_argument("--state", required=True, type=Path,
                        help="path to the workflow state JSON file")
    args = parser.parse_args(argv)

    try:
        state = _load(args.state)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read state: {exc}", file=sys.stderr)
        return 2

    if not isinstance(state, dict):
        print("state must be a JSON object", file=sys.stderr)
        return 2

    recorded, why = evaluate(state)
    verdict = "PASS" if recorded else "FAIL"
    print(f"{verdict}: tracking attempt "
          f"{'recorded' if recorded else 'NOT recorded'} — {why}")

    if not recorded:
        print("Environment Gate must not pass until the attempt is bound or "
              "recorded with sync + sync_reason (task-tracking §2/§13).", file=sys.stderr)

    return 0 if recorded else 1


if __name__ == "__main__":
    sys.exit(main())

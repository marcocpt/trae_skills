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

# task-tracking §4 pairs each row's sync value with exactly one reason, so pairing
# is itself owner-owned semantics — checking the two vocabularies independently
# would accept combinations the contract never states, making the validator a
# second source.
RECORDED_OUTCOMES = frozenset({
    ("synced", None),
    ("disabled", None),
    ("not-authorized", "no-policy"),
    ("not-authorized", "user-declined"),
    ("not-synced", "remote-unresolvable"),
    ("not-synced", "issue-missing"),
    ("not-synced", "binding-ambiguous"),
    ("not-synced", "create-outcome-unknown"),
    ("not-synced", "legacy-tracking-unknown"),
    ("not-synced", "no-issue-capable-remote"),
    ("not-synced", "provider-unavailable"),
})

# Derived from RECORDED_OUTCOMES so the two cannot disagree. §4 spells `synced`
# and `disabled` with `—` for sync_reason; requiring a reason for them would fail a
# state the owner explicitly permits.
SELF_RECORDING_SYNC = frozenset(
    sync for sync, reason in RECORDED_OUTCOMES if reason is None)

# task-tracking §2: providers registered in this contract.
SUPPORTED_PROVIDERS = frozenset({"github"})

# task-tracking §2: the only nested fields of the tracking object.
TRACKING_FIELDS = frozenset({
    "provider", "repository", "issue_number",
    "sync", "sync_reason", "pending_checkpoint", "last_checkpoint_ref",
})

# task-tracking §2: workflow types under the mandatory-attempt constraint.
MANDATORY_WORKFLOW_TYPES = frozenset({"feature-development", "bug-fix"})

# task-tracking §12: workflow types the contract explicitly exempts. Anything
# outside MANDATORY_WORKFLOW_TYPES *and* outside this set is not a recognized
# state, and must not pass open.
EXEMPT_WORKFLOW_TYPES = frozenset({"project-bootstrap"})

# task-tracking §3.2: the schema versions the legacy exemption covers, spelled out
# rather than expressed as `< 2` — a negative version would otherwise read as
# legacy and let a never-attempted state pass.
LEGACY_SCHEMA_VERSIONS = frozenset({0, 1})

# task-tracking §2/§3.2: schema_version at or above this narrows a null tracking
# to "never attempted".
CURRENT_SCHEMA_VERSION = 2

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


class MalformedState(Exception):
    """The state cannot be judged at all; this is an input error, never a pass."""


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _judge_schema_version(state: dict):
    """Return (is_legacy, raw) for schema_version, rejecting non-integers.

    task-tracking §3.2 scopes the legacy exemption to exactly "missing, 0 or 1".
    Anything else is either the current schema or malformed — in particular a
    negative int must not read as legacy, or a never-attempted state would pass.
    bool is an int subclass in Python and a hand-written "2" is a common slip, so
    both are malformed input rather than a version.
    """
    raw = state.get("schema_version")
    if raw is None:
        return True, raw
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise MalformedState(f"schema_version={raw!r} is not an integer")
    if raw in LEGACY_SCHEMA_VERSIONS:
        return True, raw
    if raw < 0:
        raise MalformedState(f"schema_version={raw!r} is negative; "
                             f"legacy covers {sorted(LEGACY_SCHEMA_VERSIONS)} only")
    return False, raw


def _issue_number_of(tracking: dict):
    """Return the bound issue number, or None.

    A GitHub issue number is a positive integer. Falsy or negative values (0, "",
    False, -1) are not issue numbers; treating them as a binding would let a
    malformed state claim a card it never created.
    """
    value = tracking.get("issue_number")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _string_field(tracking: dict, name: str) -> str | None:
    """Read an optional string field, rejecting other types as malformed.

    Without this, a list or dict reaches a frozenset membership test and raises
    TypeError — an uncaught crash whose exit code is indistinguishable from a
    legitimate Gate FAIL.
    """
    value = tracking.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedState(f"tracking.{name}={value!r} is not a string or null")
    return value


def evaluate(state: dict) -> tuple[int, str]:
    """Return (exit_code, reason) for one workflow state.

    Mirrors Design §3.2 dispatch order, item for item:
      1. workflow_type missing / not a string / neither mandatory nor exempt
                                                     -> MalformedState (never passes open)
      2. workflow_type in the exempt set            -> pass (unconditional scope
                                                      exemption: a malformed schema
                                                      elsewhere must not deny it)
      3. schema_version non-integer (incl. bool) or negative -> MalformedState
      4. schema_version in legacy set {missing,0,1} -> pass, whatever tracking holds
      5. tracking is not an object                 -> fail
      6. provider / sync / sync_reason present but not a string or null
                                                     -> MalformedState
      7. provider present but unregistered          -> fail
      8. issue_number is a positive int (not bool)  -> pass (bound)
      9. (sync, sync_reason) is an owner-defined §4 pair -> pass (recorded)
     10. sync or sync_reason outside its vocabulary -> fail
     11. otherwise                                  -> fail (attempt not recorded)

    Step 6 precedes step 8 deliberately: a state holding both a valid binding and a
    malformed sync is internally inconsistent, and silently passing it on the
    strength of the binding would let a contradiction read as a valid record.
    """
    wf_type = state.get("workflow_type")
    if not isinstance(wf_type, str) or not wf_type:
        raise MalformedState(f"workflow_type={wf_type!r} is missing or not a string")
    if wf_type not in MANDATORY_WORKFLOW_TYPES and wf_type not in EXEMPT_WORKFLOW_TYPES:
        raise MalformedState(
            f"workflow_type={wf_type!r} is neither mandatory nor a registered exempt "
            "type (task-tracking §2/§12)")
    if wf_type in EXEMPT_WORKFLOW_TYPES:
        return EXIT_PASS, f"workflow_type={wf_type!r} is exempt (task-tracking §12)"

    legacy, _ = _judge_schema_version(state)
    if legacy:
        # The exemption covers the whole pre-contract state, not just a null
        # tracking: an older state may carry a partial tracking object, and FR-7
        # forbids failing it. FAIL belongs to the current schema only.
        return EXIT_PASS, "pre-contract state (task-tracking §3.2): no forced attempt"

    tracking = state.get("tracking")
    if not isinstance(tracking, dict):
        return EXIT_FAIL, "tracking absent or null under the current schema: never attempted"

    # Design §3.2 step 6: all three type checks run before the binding check, so a
    # state holding both a valid issue_number and a malformed sync is rejected as
    # malformed instead of passing on the strength of the binding.
    provider = _string_field(tracking, "provider")
    sync = _string_field(tracking, "sync")
    reason = _string_field(tracking, "sync_reason")

    if provider is not None and provider not in SUPPORTED_PROVIDERS:
        return EXIT_FAIL, f"provider={provider!r} is not a registered provider (task-tracking §2)"

    issue_number = _issue_number_of(tracking)
    if issue_number is not None:
        return EXIT_PASS, f"bound to issue #{issue_number}"

    if (sync, reason) in RECORDED_OUTCOMES:
        if reason is None:
            return EXIT_PASS, f"sync={sync!r} records the attempt without a reason (task-tracking §4)"
        return EXIT_PASS, f"sync={sync!r} with sync_reason={reason!r}"
    if sync is not None and sync not in SYNC_VALUES:
        return EXIT_FAIL, f"sync={sync!r} is outside the task-tracking §2 vocabulary"
    if reason is not None and reason not in SYNC_REASONS:
        return EXIT_FAIL, f"sync_reason={reason!r} is outside the task-tracking §4 vocabulary"

    return EXIT_FAIL, "neither a bound issue nor a recorded sync outcome"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a workflow state records a tracking binding attempt.")
    parser.add_argument("--state", required=True, type=Path,
                        help="path to the workflow state JSON file")
    args = parser.parse_args(argv)

    try:
        state = _load(args.state)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"cannot read state: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not isinstance(state, dict):
        print("state must be a JSON object", file=sys.stderr)
        return EXIT_USAGE

    try:
        code, why = evaluate(state)
    except MalformedState as exc:
        print(f"cannot judge state: {exc}", file=sys.stderr)
        return EXIT_USAGE

    verdict = "PASS" if code == EXIT_PASS else "FAIL"
    print(f"{verdict}: tracking attempt "
          f"{'recorded' if code == EXIT_PASS else 'NOT recorded'} — {why}")

    if code == EXIT_FAIL:
        print("Environment Gate must not pass until the attempt is bound or "
              "recorded with sync + sync_reason (task-tracking §2/§13).", file=sys.stderr)

    return code


if __name__ == "__main__":
    sys.exit(main())

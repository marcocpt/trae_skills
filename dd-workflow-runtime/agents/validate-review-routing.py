#!/usr/bin/env python3
"""Validate the host-neutral review backend registry and routing policy."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Sequence


AGENTS_DIR = Path(__file__).resolve().parent
DISPATCH = AGENTS_DIR / "dispatch-review.py"
SPEC = importlib.util.spec_from_file_location("dispatch_review", DISPATCH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=AGENTS_DIR / "review-backends.yaml")
    parser.add_argument("--policy", type=Path, default=AGENTS_DIR / "routing-policy.yaml")
    parser.add_argument("--model-bindings", type=Path, default=AGENTS_DIR / "model-bindings.yaml")
    args = parser.parse_args(argv)

    try:
        registry = MODULE.load_yaml(args.registry)
        policy = MODULE.load_yaml(args.policy)
        errors = MODULE.validate_registry_policy(registry, policy)
        errors.extend(MODULE.validate_model_bindings_isolation(args.model_bindings))
    except MODULE.RouterFailure as exc:
        errors = [f"{exc.category}: {exc.detail}"]

    if errors:
        print("REVIEW ROUTING INVALID:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"review routing OK: {len(registry['backends'])} backends / {len(policy['roles'])} roles")
    return 0


if __name__ == "__main__":
    sys.exit(main())

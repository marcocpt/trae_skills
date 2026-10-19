#!/usr/bin/env python3
"""Rebind persistent review defaults without invoking a model provider.

Codex changes reviewer/advisory only; OpenCode keeps worker == reviewer.
Native products are resolved from the canonical bindings. Candidates must pass
both validators in a temporary copy before any source file is replaced.
--dry-run validates and prints the diff without publishing. I/O failures during
publishing restore already replaced files, preserving concurrent edits.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
BINDINGS = AGENTS_DIR / 'model-bindings.yaml'
OPENCODE_MODEL_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$')
CODEX_MODEL_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def _bindings_module():
    spec = importlib.util.spec_from_file_location('rebind_bindings', AGENTS_DIR / 'validate-bindings.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plan(host, model):
    text = BINDINGS.read_text()
    host_pattern = rf'^  {re.escape(host)}:\n(?:(?: {{4}}.*|[ \t]*)\n)*'
    hosts = list(re.finditer(host_pattern, text, re.M))
    if len(hosts) != 1:
        raise ValueError(f'Expected exactly one host block: {host}')
    before_host = hosts[0].group(0)
    after_host = before_host
    roles = ('worker', 'reviewer') if host == 'opencode' else ('reviewer',)
    for role in roles:
        pattern = rf'^    {role}:\n(?:(?: {{6}}.*|[ \t]*)\n)*'
        blocks = list(re.finditer(pattern, after_host, re.M))
        if len(blocks) != 1:
            raise ValueError(f'Expected one {host}/{role} block')
        old = blocks[0].group(0)
        new, count = re.subn(r'^(      model:[ \t]*)[^#\n]+?([ \t]*(?:#.*)?)$',
                             lambda m: m[1] + model + m[2], old, flags=re.M)
        if count != 1:
            raise ValueError(f'Expected one {host}/{role} model field')
        after_host = after_host.replace(old, new, 1)
    # IDs are validated plain YAML scalars. Adding quotes here would break the
    # existing bindings reader, which deliberately uses a limited YAML subset.
    plan = {BINDINGS: (text, text.replace(before_host, after_host, 1))}
    reviewer = _bindings_module().load_bindings(BINDINGS)[host]['reviewer']
    keys = ('file', 'cli_agent_file', 'advisory_cli_agent_file') if host == 'opencode' else ('file', 'advisory_agent_file')
    for key in keys:
        rel = reviewer.get(key)
        if not isinstance(rel, str) or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError(f'Missing or unsafe product: {host}/{key}')
        path = AGENTS_DIR / rel
        if not path.resolve().is_relative_to(AGENTS_DIR) or path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or unsafe product: {rel}')
        before = path.read_text()
        if host == 'codex':
            pattern = r'^(model[ \t]*=[ \t]*)"[^"\n]*"([ \t]*(?:#.*)?)$'
            after, count = re.subn(pattern, lambda m: m[1] + '"' + model + '"' + m[2], before, flags=re.M)
        else:
            if not before.startswith('---\n') or '\n---' not in before[4:]:
                raise ValueError(f'Missing frontmatter: {rel}')
            boundary = before.index('\n---', 4)
            frontmatter, count = re.subn(r'^(model:[ \t]*)[^#\n]+?([ \t]*(?:#.*)?)$',
                                        lambda m: m[1] + model + m[2], before[:boundary], flags=re.M)
            after = frontmatter + before[boundary:]
        if count != 1:
            raise ValueError(f'Expected one model field: {rel}')
        plan[path] = (before, after)
    return {path: pair for path, pair in plan.items() if pair[0] != pair[1]}


def _run_validators(directory):
    failed = False
    for name in ('validate-bindings.py', 'validate-review-routing.py'):
        result = subprocess.run([sys.executable, str(directory / name)], capture_output=True, text=True, timeout=60)
        print(f'[{"OK" if result.returncode == 0 else "DRIFTED"}] {name}')
        if result.stdout or result.stderr:
            print((result.stdout + result.stderr).strip())
        failed |= result.returncode != 0
    return not failed


def _validate_candidate(plan):
    with tempfile.TemporaryDirectory(prefix='dd-model-rebind-') as directory:
        target = Path(directory) / 'agents'
        shutil.copytree(AGENTS_DIR, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for path, (_before, after) in plan.items():
            (target / path.relative_to(AGENTS_DIR)).write_text(after)
        return _run_validators(target)


def _atomic_write(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _publish(plan):
    for path, (before, _after) in plan.items():
        if path.read_text() != before:
            raise ValueError(f'Concurrent change; refusing to overwrite {path}')
    replaced = []
    try:
        for path, (before, after) in plan.items():
            if path.read_text() != before:
                raise ValueError(f'Concurrent change; refusing to overwrite {path}')
            _atomic_write(path, after)
            replaced.append(path)
    except (OSError, ValueError):
        failures = []
        for path in reversed(replaced):
            before, after = plan[path]
            try:
                if path.read_text() != after:
                    raise ValueError('Concurrent edit preserved')
                _atomic_write(path, before)
            except (OSError, ValueError) as exc:
                failures.append(f'{path}: {exc}')
        if failures:
            raise ValueError('Rollback incomplete; inspect preserved files: ' + '; '.join(failures))
        raise


def _check_models(host, model):
    if host != 'opencode':
        print('check-models: Codex availability remains unverified (no model listing command)', file=sys.stderr)
        return True
    result = subprocess.run(['opencode', 'models'], capture_output=True, text=True, timeout=60)
    return result.returncode == 0 and model in result.stdout.split()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', choices=['opencode', 'codex'])
    parser.add_argument('model')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check-models', action='store_true')
    args = parser.parse_args()
    pattern = OPENCODE_MODEL_RE if args.host == 'opencode' else CODEX_MODEL_RE
    if not pattern.fullmatch(args.model):
        parser.error('Invalid model ID')
    try:
        if args.check_models and not _check_models(args.host, args.model):
            print('Model listing failed or model not listed; nothing written', file=sys.stderr)
            return 1
        plan = _plan(args.host, args.model)
        if not _validate_candidate(plan):
            print('Candidate validation failed; nothing written', file=sys.stderr)
            return 1
        if not args.dry_run:
            _publish(plan)
        for path, (before, after) in plan.items():
            name = str(path.relative_to(AGENTS_DIR))
            print('\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=name, tofile=name, lineterm='')))
        print('dry-run: nothing written' if args.dry_run else 'Validated configuration applied' if plan else 'No changes needed')
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'Rebind failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

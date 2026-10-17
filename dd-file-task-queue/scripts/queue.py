"""Local, cooperating-agent file queue. No execution, scheduling or Git actions."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from datetime import datetime, timezone

STATES = ('pending', 'running', 'submitted', 'closed')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z')
RESERVED = {'task.json', 'prompt.md', 'claim.json', 'DONE.json', 'review.json', 'submission.json'}


class QueueError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise QueueError(message)


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value), 'invalid task id')
    return value


def local_file(root, name):
    p = Path(name)
    require(isinstance(name, str) and name and not p.is_absolute()
            and '..' not in p.parts and p.parts, 'invalid relative output path')
    current = root
    for part in p.parts:
        current = current / part
        require(not current.is_symlink(), 'symlink not allowed: ' + name)
    require(current.is_file(), 'missing file: ' + name)
    return current


def read_json(root, name):
    try:
        return json.loads(local_file(root, name).read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QueueError(f'invalid JSON: {name}: {exc}') from exc


def write_json(path, data):
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with tmp.open('x') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def initialize(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for state in STATES:
        p = root / state
        require(not p.is_symlink(), 'symlink state directory')
        p.mkdir(exist_ok=True)
    return {'queue': str(root.resolve())}


@contextmanager
def locked(root):
    root = Path(root).resolve()
    for state in STATES:
        p = root / state
        require(p.is_dir() and not p.is_symlink(), 'run init; invalid state: ' + state)
    fd = os.open(root / '.queue.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield root


def locate(root, task, expected=None):
    identifier(task)
    matches = [(s, root / s / task) for s in STATES
               if os.path.lexists(root / s / task)]
    require(len(matches) == 1, 'missing or duplicate task: ' + task)
    state, p = matches[0]
    require(p.is_dir() and not p.is_symlink(), 'invalid task directory')
    require(expected is None or state == expected, 'unexpected task state: ' + state)
    return state, p


def metadata(p, task):
    data = read_json(p, 'task.json')
    require(isinstance(data, dict) and data.get('task_id') == task, 'task identity mismatch')
    deps = data.get('depends_on')
    scope = data.get('write_scope')
    required = data.get('required_outputs')
    require(isinstance(deps, list) and all(isinstance(x, str) and ID.fullmatch(x)
            and x != task for x in deps), 'invalid dependencies')
    require(isinstance(scope, list) and all(isinstance(x, str) and Path(x).is_absolute()
            and '..' not in Path(x).parts for x in scope), 'write_scope needs absolute paths')
    require(isinstance(required, list) and all(isinstance(x, str) for x in required)
            and {'REPORT.md', 'baseline.json'} <= set(required), 'required_outputs missing report/baseline')
    require(not (set(required) & RESERVED), 'reserved output name')
    local_file(p, 'prompt.md')
    return data


def verify_at(p, task):
    meta = metadata(p, task)
    receipt = read_json(p, 'claim.json')
    for name in ('task.json', 'prompt.md'):
        require(receipt.get('inputs', {}).get(name) == hashlib.sha256(local_file(p, name).read_bytes()).hexdigest(),
                'claimed packet changed: ' + name)
    if (p / 'submission.json').exists():
        submission = read_json(p, 'submission.json')
        require(submission.get('done_sha256') == hashlib.sha256(local_file(p, 'DONE.json').read_bytes()).hexdigest(),
                'submitted DONE changed')
    done = read_json(p, 'DONE.json')
    require(isinstance(done, dict) and done.get('task') == task, 'DONE task mismatch')
    require(done.get('status') in ('completed', 'blocked'), 'invalid DONE status')
    outputs = done.get('outputs')
    require(isinstance(outputs, dict) and set(meta['required_outputs']) <= set(outputs),
            'missing required output hashes')
    for name, digest in outputs.items():
        require(name not in RESERVED, 'reserved file cannot be output')
        require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid sha256')
        path = local_file(p, name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'hash mismatch: ' + name)
    return done


def claim(root, task, owner):
    require(isinstance(owner, str) and owner.strip(), 'owner is required')
    with locked(root) as root:
        _, p = locate(root, task, 'pending')
        meta = metadata(p, task)
        for dep in meta['depends_on']:
            _, d = locate(root, dep, 'closed')
            review = read_json(d, 'review.json')
            done = verify_at(d, dep)
            require(review.get('outcome') == 'accepted' and done['status'] == 'completed',
                    'dependency not accepted: ' + dep)
            require(review.get('done_sha256') == hashlib.sha256((d / 'DONE.json').read_bytes()).hexdigest(),
                    'dependency receipt changed: ' + dep)
        for running in (root / 'running').iterdir():
            if running.name.startswith('.'):
                continue
            _, other = locate(root, running.name, 'running')
            scopes = metadata(other, running.name)['write_scope']
            for a in meta['write_scope']:
                for b in scopes:
                    aa, bb = Path(a).resolve(), Path(b).resolve()
                    require(not (aa == bb or aa in bb.parents or bb in aa.parents),
                            'write scope conflicts with ' + running.name)
        require(not (p / 'claim.json').exists(), 'interrupted claim; primary recovery required')
        receipt = {'task': task, 'owner': owner, 'token': uuid.uuid4().hex,
                   'claimed_at': datetime.now(timezone.utc).isoformat(),
                   'inputs': {n: hashlib.sha256(local_file(p, n).read_bytes()).hexdigest()
                              for n in ('task.json', 'prompt.md')}}
        write_json(p / 'claim.json', receipt)
        os.rename(p, root / 'running' / task)
        return receipt


def submit(root, task, token):
    with locked(root) as root:
        _, p = locate(root, task, 'running')
        require(read_json(p, 'claim.json').get('token') == token, 'claim token mismatch')
        done = verify_at(p, task)
        write_json(p / 'submission.json', {'done_sha256': hashlib.sha256((p / 'DONE.json').read_bytes()).hexdigest()})
        os.rename(p, root / 'submitted' / task)
        return {'task': task, 'state': 'submitted', 'status': done['status']}


def verify(root, task):
    with locked(root) as root:
        state, p = locate(root, task)
        done = verify_at(p, task)
        return {'task': task, 'state': state, 'status': done['status'], 'hashes_valid': True}


def close(root, task, outcome, evidence):
    require(outcome in ('accepted', 'rejected') and isinstance(evidence, str)
            and evidence.strip(), 'primary verdict and evidence required')
    with locked(root) as root:
        _, p = locate(root, task, 'submitted')
        done = verify_at(p, task)
        require(outcome != 'accepted' or done['status'] == 'completed', 'blocked cannot be accepted completion')
        write_json(p / 'review.json', {'outcome': outcome, 'evidence': evidence,
                   'done_sha256': hashlib.sha256((p / 'DONE.json').read_bytes()).hexdigest()})
        os.rename(p, root / 'closed' / task)
        return {'task': task, 'outcome': outcome}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    p = sub.add_parser('claim'); p.add_argument('task'); p.add_argument('--owner', required=True)
    p = sub.add_parser('submit'); p.add_argument('task'); p.add_argument('--token', required=True)
    p = sub.add_parser('verify'); p.add_argument('task')
    p = sub.add_parser('close'); p.add_argument('task'); p.add_argument('--outcome', choices=['accepted', 'rejected'], required=True); p.add_argument('--evidence', required=True)
    a = parser.parse_args()
    try:
        if a.command == 'init': result = initialize(a.queue)
        elif a.command == 'claim': result = claim(a.queue, a.task, a.owner)
        elif a.command == 'submit': result = submit(a.queue, a.task, a.token)
        elif a.command == 'verify': result = verify(a.queue, a.task)
        else: result = close(a.queue, a.task, a.outcome, a.evidence)
        print(json.dumps(result, ensure_ascii=False))
    except (QueueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()

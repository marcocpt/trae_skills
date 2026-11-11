#!/usr/bin/env python3
"""One approved strong-model turn; legacy review contracts remain unchanged.

This is a transport and verification helper, not another workflow or finding
ledger. The parent owns decisions, writer exclusion, authorization and closure.
No shell interpolation, implicit backend fallback, nested routing or Git writes.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import signal
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUEST_SCHEMA = 'dd-collaboration-request/1'
RESULT_SCHEMA = 'dd-collaboration-result/1'
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]*$')
HANDLE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$')


class Blocked(Exception):
    def __init__(self, category, detail):
        self.category, self.detail = category, detail
        super().__init__(detail)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


def context_digest(request):
    """Authorization binds all caller-controlled outbound context, not a label."""
    return digest({'request': {k: v for k, v in request.items() if k != 'authorization'},
                   'contract': hashlib.sha256((ROOT / 'collaboration-prompt.md').read_bytes()).hexdigest(),
                   'registry': hashlib.sha256((ROOT / 'review-backends.yaml').read_bytes()).hexdigest()})


def git(repo, *args):
    proc = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30)
    if proc.returncode:
        raise Blocked('baseline_mismatch', 'Git inspection failed: ' + ' '.join(args))
    return proc.stdout


def snapshot(repo):
    """Fingerprint tracked + nonignored untracked files, index, HEAD and mode.

    A missing tracked path is recorded, not dropped. Symlink contents are never
    followed. Ignored build caches are outside this candidate contract.
    """
    repo = Path(repo).resolve()
    paths = git(repo, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    files = {}
    for raw in sorted(set(paths) - {b''}):
        name = os.fsdecode(raw)
        path = repo / name
        try:
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                content = os.fsencode(os.readlink(path))
            elif stat.S_ISREG(mode):
                content = path.read_bytes()
            else:
                raise Blocked('baseline_mismatch', 'Unsupported candidate entry: ' + name)
            files[name] = [stat.S_IFMT(mode), stat.S_IMODE(mode), hashlib.sha256(content).hexdigest()]
        except FileNotFoundError:
            files[name] = None
    value = {'head': git(repo, 'rev-parse', 'HEAD').decode().strip(),
             'index': hashlib.sha256(git(repo, 'ls-files', '--stage', '-z')).hexdigest(),
             'files': files}
    value['digest'] = digest(value)
    return value


def relative_file(repo, name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise Blocked('schema_invalid', 'Expected repository-relative file path')
    path = Path(name)
    if path.is_absolute() or any(p in {'.', '..', '.git'} or p.lower() == '.git' for p in path.parts):
        raise Blocked('authorization_violation', 'Path escapes candidate: ' + name)
    if path.as_posix() != name:
        raise Blocked('schema_invalid', 'Path must be normalized: ' + name)
    current = repo
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise Blocked('authorization_violation', 'Symlink in candidate scope: ' + name)
    if current.exists() and not current.is_file():
        raise Blocked('schema_invalid', 'Scope must list files, not directories: ' + name)
    if subprocess.run(['git', '-C', str(repo), 'check-ignore', '-q', '--', name],
                      capture_output=True).returncode == 0:
        raise Blocked('authorization_violation', 'Ignored file cannot be in candidate scope: ' + name)
    return name


def configuration():
    spec = importlib.util.spec_from_file_location('dd_collaboration_config', ROOT / 'dispatch-review.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_yaml(ROOT / 'review-backends.yaml')['backends']


def validate_request(req):
    if not isinstance(req, dict) or req.get('schema') != REQUEST_SCHEMA:
        raise Blocked('schema_invalid', 'Expected ' + REQUEST_SCHEMA)
    for field in ('workflow_id', 'backend', 'model', 'effort', 'repo', 'context', 'baseline'):
        if not isinstance(req.get(field), str) or not req[field].strip():
            raise Blocked('schema_invalid', 'Missing ' + field)
    if not HANDLE.fullmatch(req['workflow_id']):
        raise Blocked('schema_invalid', 'Invalid workflow_id')
    if not SAFE_ID.fullmatch(req['model']) or not re.fullmatch(r'[A-Za-z0-9_-]+', req['effort']):
        raise Blocked('configuration_invalid', 'Invalid model or effort identifier')
    if req.get('operation') not in {'plan', 'review', 'repair'}:
        raise Blocked('schema_invalid', 'operation must be plan, review or repair')
    approval = req.get('authorization', {})
    if not isinstance(approval, dict) or approval.get('approved') is not True or approval.get('context_digest') != context_digest(req):
        raise Blocked('authorization_violation', 'Approval does not bind this exact outbound request')
    repo = Path(req['repo']).resolve()
    if not Path(req['repo']).is_absolute() or git(repo, 'rev-parse', '--show-toplevel').decode().strip() != str(repo):
        raise Blocked('configuration_invalid', 'repo must be the absolute repository root')
    for key in ('scope', 'write_scope'):
        value = req.get(key)
        if not isinstance(value, list) or (key == 'scope' and not value):
            raise Blocked('schema_invalid', key + ' must be a file list')
        for name in value:
            relative_file(repo, name)
        if len(set(value)) != len(value):
            raise Blocked('schema_invalid', 'Duplicate scope entries')
    if not set(req['write_scope']).issubset(req['scope']):
        raise Blocked('authorization_violation', 'write_scope exceeds approved read scope')
    if req['operation'] == 'plan' and req['write_scope']:
        raise Blocked('authorization_violation', 'Planning cannot write candidate files')
    if req['operation'] == 'repair' or req['write_scope']:
        repair = req.get('repair', {})
        if (not isinstance(repair, dict) or repair.get('risk') != 'LOW'
                or repair.get('behavior_defined') is not True or repair.get('bounded') is not True
                or not isinstance(repair.get('rationale'), str) or not repair['rationale'].strip()
                or not isinstance(repair.get('finding_ids'), list)
                or (req['operation'] == 'repair' and not repair['finding_ids'])
                or not all(isinstance(x, str) and x for x in repair['finding_ids'])
                or not req['write_scope']):
            raise Blocked('authorization_violation', 'Direct repair requires a justified, bounded LOW-risk fix')
    if 'session' in req and (not isinstance(req['session'], str) or not HANDLE.fullmatch(req['session'])):
        raise Blocked('schema_invalid', 'Invalid session handle')
    checks = req.get('verification')
    if not isinstance(checks, list) or (req['operation'] != 'plan' and not checks):
        raise Blocked('schema_invalid', 'review and repair require verification commands')
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get('command'), list)
                or not check['command'] or not all(isinstance(x, str) and x and '\0' not in x for x in check['command'])):
            raise Blocked('schema_invalid', 'verification.command must be a nonempty argv list')
    return repo


def execute(command, prompt, cwd, timeout):
    """Kill the process group on timeout; never leave a timed-out writer alive."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, cwd=cwd, start_new_session=True)
    try:
        stdout, _stderr = proc.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise Blocked('backend_execution_failed', 'Process group terminated after timeout')
    return proc.returncode, stdout


def verify(req, repo):
    evidence = []
    for check in req['verification']:
        code, output = execute(check['command'], '', repo, 120)
        evidence.append({'command': check['command'], 'exit_code': code,
                         'output_digest': hashlib.sha256(output.encode()).hexdigest()})
        if code:
            raise Blocked('verification_failed', 'Verification failed: ' + json.dumps(evidence[-1]))
    return evidence


def parse_stream(backend, stdout):
    sessions, texts, usage = set(), [], []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            raise Blocked('schema_invalid', 'Malformed provider event stream')
        if not isinstance(event, dict):
            raise Blocked('schema_invalid', 'Provider event must be an object')
        if backend == 'codex-cli':
            if event.get('type') == 'thread.started' and event.get('thread_id'):
                sessions.add(event['thread_id'])
            item = event.get('item', {})
            if not isinstance(item, dict):
                raise Blocked('schema_invalid', 'Malformed Codex item')
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                texts.append(item.get('text', ''))
            if event.get('type') == 'turn.completed' and isinstance(event.get('usage'), dict):
                usage.append(event['usage'])
        else:
            if event.get('sessionID'):
                sessions.add(event['sessionID'])
            part = event.get('part', {})
            if not isinstance(part, dict) or not isinstance(part.get('time', {}), dict):
                raise Blocked('schema_invalid', 'Malformed OpenCode part')
            if part.get('type') == 'text' and part.get('time', {}).get('end'):
                texts.append(part.get('text', ''))
    if len(sessions) != 1 or not all(isinstance(x, str) and HANDLE.fullmatch(x) for x in sessions):
        raise Blocked('session_resume_mismatch', 'Missing or ambiguous engine session identity')
    objects = []
    for text in texts:
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and 'status' in obj:
            objects.append(obj)
    if len(objects) != 1 or not texts or not _is_final_object(texts[-1], objects[0]):
        raise Blocked('schema_invalid', 'Expected exactly one final JSON result, without prose or fences')
    return next(iter(sessions)), objects[0], usage or None


def _is_final_object(text, obj):
    try:
        return json.loads(text) == obj
    except ValueError:
        return False


def validate_result(req, result):
    required = {'status', 'reviewed', 'unreadable', 'findings', 'tasks', 'evidence'}
    if not required.issubset(result) or set(result) - required - {'fixed_findings'}:
        raise Blocked('schema_invalid', 'Provider cannot supply adapter provenance, verification or closure fields')
    status = result.get('status')
    allowed = {'plan': {'PLANNED', 'BLOCKED'}, 'review': {'PASS', 'FINDINGS', 'BLOCKED'},
               'repair': {'REPAIRED', 'FINDINGS', 'BLOCKED'}}[req['operation']]
    if status not in allowed:
        raise Blocked('schema_invalid', 'Result status incompatible with operation')
    for key in ('reviewed', 'unreadable', 'findings', 'tasks', 'evidence'):
        if not isinstance(result.get(key), list):
            raise Blocked('schema_invalid', 'Missing result list: ' + key)
    reviewed, unreadable = result['reviewed'], result['unreadable']
    if (not all(isinstance(x, str) for x in reviewed + unreadable)
            or len(set(reviewed)) != len(reviewed) or len(set(unreadable)) != len(unreadable)
            or set(reviewed) & set(unreadable) or set(reviewed + unreadable) != set(req['scope'])):
        raise Blocked('review_incomplete', 'Coverage does not account for exact scope')
    if not result['evidence'] or not all(isinstance(x, str) and x.strip() for x in result['evidence']):
        raise Blocked('schema_invalid', 'Evidence is required')
    if status in {'PASS', 'REPAIRED'} and (unreadable or result['findings'] or result['tasks']):
        raise Blocked('review_incomplete', 'Success cannot contain unread scope or unfinished work')
    if status == 'FINDINGS' and not result['findings']:
        raise Blocked('schema_invalid', 'FINDINGS requires findings')
    for finding in result['findings']:
        if not isinstance(finding, dict) or not all(isinstance(finding.get(k), str) and finding[k].strip()
                for k in ('id', 'severity', 'classification', 'change_risk', 'location', 'evidence', 'required_fix')):
            raise Blocked('schema_invalid', 'Incomplete finding')
        if (finding['severity'] not in {'LOW', 'MEDIUM', 'HIGH'}
                or finding['change_risk'] not in {'LOW', 'MEDIUM', 'HIGH'}
                or finding['classification'] not in {'FINDING', 'VERIFICATION_REQUIRED', 'HUMAN_DECISION_REQUIRED'}):
            raise Blocked('schema_invalid', 'Invalid existing finding vocabulary')
    fixed = result.get('fixed_findings', [])
    if not isinstance(fixed, list):
        raise Blocked('schema_invalid', 'fixed_findings must be a list')
    for finding in fixed:
        if (not isinstance(finding, dict) or not all(isinstance(finding.get(k), str) and finding[k].strip()
                for k in ('id', 'severity', 'classification', 'change_risk', 'location', 'evidence', 'required_fix', 'resolution'))
                or finding.get('severity') not in {'LOW', 'MEDIUM', 'HIGH'}
                or finding.get('change_risk') != 'LOW' or finding.get('classification') != 'FINDING'):
            raise Blocked('schema_invalid', 'Fixed finding needs identity, evidence, resolution and LOW risk')
    fixed_ids = [f['id'] for f in fixed]
    if len(set(fixed_ids)) != len(fixed_ids) or set(fixed_ids) & {f['id'] for f in result['findings']}:
        raise Blocked('schema_invalid', 'Fixed and open finding identities overlap or repeat')
    if status == 'PLANNED' and not result['tasks']:
        raise Blocked('schema_invalid', 'PLANNED requires bounded tasks')
    for task in result['tasks']:
        if not isinstance(task, dict) or not isinstance(task.get('goal'), str) or not task['goal'].strip():
            raise Blocked('schema_invalid', 'Task goal is required')
        for key in ('finding_ids', 'write_scope', 'steps', 'verification', 'stop_conditions'):
            if (not isinstance(task.get(key), list)
                    or (not task[key] and not (key == 'finding_ids' and req['operation'] == 'plan'))
                    or not all(isinstance(x, str) and x.strip() for x in task[key])):
                raise Blocked('schema_invalid', 'Incomplete bounded task: ' + key)
        # Task scope is a proposal, never permission to write it.
        for path in task['write_scope']:
            relative_file(Path(req['repo']), path)


def check_changes(before, after, allowed):
    if before['head'] != after['head'] or before['index'] != after['index']:
        raise Blocked('write_scope_violation', 'HEAD or index changed; Git actions are not authorized')
    changed = sorted(k for k in set(before['files']) | set(after['files'])
                     if before['files'].get(k) != after['files'].get(k))
    if not set(changed).issubset(allowed):
        raise Blocked('write_scope_violation', 'Unauthorized changed paths: ' + ', '.join(changed))
    return changed


def build_command(req, spec):
    values = {'model': req['model'], 'effort_toml': json.dumps(req['effort']),
              'model_variant': req['model'] + ('' if req['effort'] == 'default' else '#' + req['effort']),
              'session': req.get('session', '')}
    form = 'resume' if req.get('session') else 'initial'
    template = spec.get(form)
    if not isinstance(template, list) or not template or not all(isinstance(x, str) for x in template):
        raise Blocked('configuration_invalid', 'Missing collaboration command template')
    try:
        return [arg.format(**values) for arg in template]
    except (KeyError, ValueError):
        raise Blocked('configuration_invalid', 'Invalid collaboration command template')


def dispatch(req, state_dir=None, provider=None):
    result = {'schema': RESULT_SCHEMA, 'status': 'BLOCKED', 'closure_candidate': False,
              'failure_category': None, 'evidence': []}
    before = None
    repo = None
    lock = None
    try:
        repo = validate_request(req)
        spec = configuration().get(req['backend'], {}).get('collaboration')
        if not isinstance(spec, dict):
            raise Blocked('configuration_invalid', 'Backend has no collaboration transport; ChatGPT uses its read-only contract')
        state_dir = Path(state_dir or Path.home() / '.cache' / 'dd-strong-collaboration').resolve()
        if state_dir == repo or repo in state_dir.parents:
            raise Blocked('configuration_invalid', 'Session metadata must be outside the candidate repository')
        state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = digest([str(repo), req['workflow_id']])
        lock = (state_dir / (digest(str(repo)) + '.lock')).open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked('session_busy', 'Only one in-flight turn per workflow')
        binding = {k: req[k] for k in ('workflow_id', 'backend', 'model', 'effort', 'repo')}
        state_path = state_dir / (key + '.json')
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if req.get('session'):
            if not state or state.get('binding') != binding or state.get('session') != req['session'] or state.get('tainted'):
                raise Blocked('session_resume_mismatch', 'Session is not registered to this workflow, model and repository')
            if state.get('resumes', 0) >= 2:
                raise Blocked('rework_limit', 'Default two rework turns exhausted')
        elif state:
            raise Blocked('session_resume_mismatch', 'Existing workflow requires explicit session continuation')
        before = snapshot(repo)
        result['baseline_before'] = before['digest']
        if before['digest'] != req['baseline']:
            raise Blocked('baseline_mismatch', 'Candidate no longer matches approved fingerprint')
        if req['operation'] == 'review':
            result['verification'] = verify(req, repo)
            check_changes(before, snapshot(repo), set())
        contract = (ROOT / 'collaboration-prompt.md').read_text()
        prompt = contract + '\n\nREQUEST:\n' + json.dumps({k: v for k, v in req.items() if k != 'authorization'}, ensure_ascii=False)
        command = build_command(req, spec)
        result['outbound_digest'] = hashlib.sha256(prompt.encode()).hexdigest()
        # Reserve this continuation before execution; failure must not allow
        # unlimited automatic retries. Initial failures require explicit recovery.
        reservation = {'binding': binding, 'session': req.get('session'),
                       'resumes': state.get('resumes', 0) + 1 if state else 0, 'tainted': True}
        state_path.write_text(json.dumps(reservation))
        code, stdout = (provider or execute)(command, prompt, repo, 600)
        after = snapshot(repo)
        result['baseline_after'] = after['digest']
        changed = check_changes(before, after, set(req['write_scope']))
        result['changed_paths'] = changed
        if code:
            raise Blocked('backend_execution_failed', 'Provider exited with code ' + str(code))
        session, payload, usage = parse_stream(req['backend'], stdout)
        result['session'] = session
        if req.get('session') and session != req['session']:
            raise Blocked('session_resume_mismatch', 'Engine session differs from requested handle')
        reservation['session'] = session
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(reservation))
        temporary.replace(state_path)
        validate_result(req, payload)
        if payload.get('fixed_findings') and (not changed or not req['write_scope']):
            raise Blocked('verification_failed', 'Fixed finding claims require actual authorized changes')
        if req['operation'] == 'review' and changed and not payload.get('fixed_findings'):
            raise Blocked('schema_invalid', 'Review writes require explicit fixed finding records')
        if (req['operation'] == 'repair' and payload['status'] == 'REPAIRED') or changed:
            if not changed:
                raise Blocked('verification_failed', 'REPAIRED requires actual authorized changes')
            for path in req['write_scope']:
                relative_file(repo, path)
            result['verification'] = verify(req, repo)
            verified = snapshot(repo)
            if verified['digest'] != after['digest']:
                raise Blocked('baseline_mismatch', 'Validation changed candidate; re-review required')
        reservation.update(session=session, tainted=payload['status'] == 'BLOCKED')
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(reservation))
        temporary.replace(state_path)
        result.update(payload)
        result.update(session=session, backend=req['backend'], model=req['model'], effort=req['effort'],
                      usage=usage, requested_identity=True,
                      closure_candidate=payload['status'] in {'PASS', 'REPAIRED'},
                      closure_candidates=([f['id'] for f in payload.get('fixed_findings', [])]
                          or (req.get('repair', {}).get('finding_ids', []) if payload['status'] == 'REPAIRED' else []))
                          if changed and not payload['unreadable'] and payload['status'] != 'BLOCKED' else [],
                      closure_basis='strong-self-fix' if changed else 'strong-review')
        # Provider output never owns adapter provenance or closure flags.
        result.update(schema=RESULT_SCHEMA, baseline_before=before['digest'], baseline_after=after['digest'],
                      changed_paths=changed, failure_category=None if payload['status'] != 'BLOCKED' else 'reviewer_blocked')
    except (Blocked, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        category = exc.category if isinstance(exc, Blocked) else 'configuration_invalid'
        result.update(status='BLOCKED', closure_candidate=False, failure_category=category,
                      evidence=[str(exc)])
        if repo is not None and before is not None:
            try:
                after = snapshot(repo)
                result['baseline_after'] = after['digest']
                check_changes(before, after, set(req.get('write_scope', [])))
            except Blocked as drift:
                result.update(failure_category=drift.category, evidence=[str(exc), str(drift)])
    finally:
        if lock:
            lock.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Read-only candidate fingerprint; does not invoke a provider')
    parser.add_argument('--context-digest', action='store_true', help='Hash stdin request for outbound approval')
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    try:
        if args.snapshot:
            candidate = snapshot(args.snapshot)
            print(json.dumps({key: candidate[key] for key in ('digest', 'head', 'index')}
                             | {'file_count': len(candidate['files'])}, ensure_ascii=False))
            return 0
        req = json.load(sys.stdin)
        if args.context_digest:
            print(context_digest(req))
            return 0
        result = dispatch(req, args.state_dir)
    except (ValueError, OSError, Blocked) as exc:
        result = {'schema': RESULT_SCHEMA, 'status': 'BLOCKED', 'closure_candidate': False,
                  'failure_category': 'schema_invalid', 'evidence': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())

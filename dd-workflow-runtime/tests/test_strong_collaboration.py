"""Same-session collaboration; providers are fakes, never external services."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'agents' / 'dispatch-collaboration.py'
SPEC = importlib.util.spec_from_file_location('strong_collaboration', SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.state = Path(self.tmp.name) / 'sessions'
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'a.py').write_text('value = 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.calls = []

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args]).decode().strip()

    def request(self, **overrides):
        req = dict(schema='dd-collaboration-request/1', workflow_id='W1',
                   backend='codex-cli', model='test-model', effort='high',
                   repo=str(self.repo), operation='review', scope=['a.py'], write_scope=[],
                   context='Check the approved value invariant.',
                   verification=[{'command': ['python3', '-c', 'assert True']}],
                   baseline=MOD.snapshot(self.repo)['digest'])
        req.update(overrides)
        req['authorization'] = {'approved': True, 'context_digest': MOD.context_digest(req)}
        return req

    def provider(self, req, mutate=None, status=None, session='thread-1', **extra):
        def call(command, prompt, cwd, timeout):
            self.calls.append((command, prompt))
            if mutate:
                mutate()
            payload = dict(status=status or ('REPAIRED' if req['operation'] == 'repair' else 'PASS'),
                           reviewed=req['scope'], unreadable=[], findings=[], tasks=[],
                           evidence=['Read actual source and diff.'])
            payload.update(extra)
            events = [dict(type='thread.started', thread_id=session),
                      dict(type='item.completed', item=dict(type='agent_message', text=json.dumps(payload)))]
            return 0, '\n'.join(json.dumps(e) for e in events)
        return call

    def run_request(self, req, provider=None):
        return MOD.dispatch(req, self.state, provider or self.provider(req))

    def test_dirty_candidate_can_be_reviewed_without_commit(self):
        (self.repo / 'a.py').write_text('value = 2\n')
        req = self.request()
        result = self.run_request(req)
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(result['closure_candidate'])
        self.assertEqual(result['baseline_after'], req['baseline'])
        self.assertIn('--model', self.calls[0][0])

    def test_stale_candidate_never_calls_provider(self):
        req = self.request()
        (self.repo / 'a.py').write_text('drift')
        result = self.run_request(req)
        self.assertEqual(result['failure_category'], 'baseline_mismatch')
        self.assertEqual(self.calls, [])

    def test_approval_binds_actual_outbound_request(self):
        req = self.request()
        req['context'] += ' not approved'
        result = self.run_request(req)
        self.assertEqual(result['failure_category'], 'authorization_violation')
        self.assertEqual(self.calls, [])

    def test_review_write_voids_round_and_preserves_evidence(self):
        req = self.request()
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('changed')))
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['failure_category'], 'write_scope_violation')
        self.assertEqual((self.repo / 'a.py').read_text(), 'changed')

    def test_small_fix_runs_validation_and_binds_new_candidate(self):
        req = self.request(operation='repair', write_scope=['a.py'],
                           repair={'risk': 'LOW', 'behavior_defined': True, 'bounded': True,
                                   'rationale': 'Internal constant fixed by approved specification.', 'finding_ids': ['F1']})
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n')))
        self.assertEqual(result['status'], 'REPAIRED')
        self.assertTrue(result['closure_candidate'])
        self.assertEqual(result['closure_basis'], 'strong-self-fix')
        self.assertNotEqual(result['baseline_after'], result['baseline_before'])

    def test_high_risk_repair_rejected_before_provider(self):
        req = self.request(operation='repair', write_scope=['a.py'],
                           repair={'risk': 'HIGH', 'behavior_defined': True, 'bounded': True,
                                   'rationale': 'Public API migration', 'finding_ids': ['F1']})
        self.assertEqual(self.run_request(req)['failure_category'], 'authorization_violation')
        self.assertFalse(self.calls)

    def test_failed_validation_does_not_close(self):
        req = self.request(verification=[{'command': ['python3', '-c', 'raise SystemExit(3)']}])
        result = self.run_request(req)
        self.assertEqual(result['failure_category'], 'verification_failed')
        self.assertFalse(self.calls)

    def test_unread_scope_cannot_pass(self):
        req = self.request()
        result = self.run_request(req, self.provider(req, reviewed=[], unreadable=['a.py']))
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result['closure_candidate'])

    def test_resume_identity_and_model_are_pinned(self):
        req = self.request()
        self.run_request(req)
        resumed = self.request(session='thread-1')
        result = self.run_request(resumed, self.provider(resumed, session='wrong'))
        self.assertEqual(result['failure_category'], 'session_resume_mismatch')
        changed = self.request(session='thread-1', model='different')
        self.assertEqual(self.run_request(changed)['failure_category'], 'session_resume_mismatch')

    def test_chatgpt_has_no_repair_transport(self):
        req = self.request(backend='chatgpt-tunnel')
        self.assertEqual(self.run_request(req)['failure_category'], 'configuration_invalid')
        self.assertFalse(self.calls)

    def test_symlink_write_scope_rejected(self):
        (self.repo / 'linked.py').symlink_to(self.repo / 'a.py')
        req = self.request(write_scope=['linked.py'])
        self.assertEqual(self.run_request(req)['status'], 'BLOCKED')

    def test_untracked_files_are_part_of_candidate(self):
        before = MOD.snapshot(self.repo)['digest']
        (self.repo / 'new.py').write_text('new')
        self.assertNotEqual(MOD.snapshot(self.repo)['digest'], before)

    def test_task_handoff_does_not_start_another_agent(self):
        req = self.request(operation='plan', verification=[])
        tasks = [{'finding_ids': ['F1'], 'goal': 'Replace expensive parser', 'write_scope': ['a.py'],
                  'steps': ['Implement approved parser'], 'verification': ['Run parser regression suite'],
                  'stop_conditions': ['Specification conflict']}]
        result = self.run_request(req, self.provider(req, status='PLANNED', tasks=tasks))
        self.assertEqual(result['status'], 'PLANNED')
        self.assertEqual(result['tasks'], tasks)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(result['closure_candidate'])

    def repair_request(self, **overrides):
        return self.request(operation='repair', write_scope=['a.py'],
                            repair={'risk': 'LOW', 'behavior_defined': True, 'bounded': True,
                                    'rationale': 'Approved local constant invariant', 'finding_ids': ['F1']},
                            **overrides)

    def test_repair_cannot_write_an_unapproved_file(self):
        req = self.repair_request()
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'unapproved.py').write_text('oops')))
        self.assertEqual(result['failure_category'], 'write_scope_violation')
        self.assertFalse(result['closure_candidate'])
        self.assertTrue((self.repo / 'unapproved.py').exists())

    def test_failed_post_repair_verification_preserves_changes(self):
        req = self.repair_request(verification=[{'command': ['python3', '-c', 'raise SystemExit(4)']}])
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n')))
        self.assertEqual(result['failure_category'], 'verification_failed')
        self.assertFalse(result['closure_candidate'])
        self.assertEqual((self.repo / 'a.py').read_text(), 'value = 2\n')

    def test_provider_cannot_forge_actual_verification(self):
        req = self.request()
        result = self.run_request(req, self.provider(req, verification=[{'exit_code': 0}], closure_candidate=True))
        self.assertEqual(result['failure_category'], 'schema_invalid')
        self.assertFalse(result['closure_candidate'])

    def test_stage_is_not_authorized_even_for_in_scope_repair(self):
        req = self.repair_request()
        def mutate():
            (self.repo / 'a.py').write_text('value = 3\n')
            self.git('add', 'a.py')
        result = self.run_request(req, self.provider(req, mutate))
        self.assertEqual(result['failure_category'], 'write_scope_violation')

    def test_rework_limit_counts_resumes(self):
        req = self.request()
        self.assertEqual(self.run_request(req)['status'], 'PASS')
        resumed = self.request(session='thread-1')
        for _ in range(2):
            self.assertEqual(self.run_request(resumed)['status'], 'PASS')
        count = len(self.calls)
        self.assertEqual(self.run_request(resumed)['failure_category'], 'rework_limit')
        self.assertEqual(len(self.calls), count)

    def test_failed_turn_is_not_silently_retried(self):
        req = self.request()
        self.run_request(req, self.provider(req, status='BLOCKED'))
        result = self.run_request(self.request(session='thread-1'))
        self.assertEqual(result['failure_category'], 'session_resume_mismatch')
        self.assertEqual(len(self.calls), 1)

    def test_unknown_handle_is_not_reused(self):
        req = self.request(session='someone-elses-session')
        self.assertEqual(self.run_request(req)['failure_category'], 'session_resume_mismatch')
        self.assertFalse(self.calls)

    def test_timeout_after_out_of_scope_write_reports_drift(self):
        req = self.request()
        def timeout(*args):
            (self.repo / 'extra.py').write_text('unexpected')
            raise MOD.Blocked('backend_execution_failed', 'timeout')
        result = self.run_request(req, timeout)
        self.assertEqual(result['failure_category'], 'write_scope_violation')
        self.assertFalse(result['closure_candidate'])

    def test_validation_cannot_change_candidate(self):
        req = self.request(verification=[{'command': ['python3', '-c', "open('a.py','w').write('mutated')"]}])
        result = self.run_request(req)
        self.assertEqual(result['failure_category'], 'write_scope_violation')
        self.assertFalse(self.calls)

    def test_plan_does_not_invoke_test_commands(self):
        req = self.request(operation='plan', verification=[{'command': ['does-not-exist']}])
        result = self.run_request(req, self.provider(req, status='BLOCKED'))
        self.assertEqual(result['failure_category'], 'reviewer_blocked')
        self.assertEqual(len(self.calls), 1)

    def test_opencode_pins_model_and_variant_and_checks_identity(self):
        req = self.request(backend='opencode-cli', model='provider/model', effort='high')
        def provider(command, prompt, cwd, timeout):
            self.calls.append((command, prompt))
            payload = dict(status='PASS', reviewed=['a.py'], unreadable=[], findings=[], tasks=[], evidence=['source read'])
            return 0, json.dumps({'sessionID': 'ses_test', 'part': {'type': 'text', 'text': json.dumps(payload), 'time': {'end': 1}}})
        result = self.run_request(req, provider)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['session'], 'ses_test')
        self.assertIn('provider/model#high', self.calls[0][0])
        self.assertIn('build', self.calls[0][0])
        self.assertNotIn('--auto', self.calls[0][0])

    def test_model_override_never_changes_canonical_config(self):
        config = MOD.ROOT / 'model-bindings.yaml'
        before = config.read_bytes()
        req = self.request(model='chosen-model', effort='medium')
        self.run_request(req)
        self.assertIn('chosen-model', self.calls[0][0])
        self.assertIn('model_reasoning_effort="medium"', self.calls[0][0])
        self.assertEqual(config.read_bytes(), before)

    def test_malformed_stream_and_multiple_final_results_are_rejected(self):
        for stream in ['not json', '{}',
                       '\n'.join([json.dumps({'type': 'thread.started', 'thread_id': 't1'}),
                                  *[json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"status":"PASS"}'}})] * 2])]:
            with self.subTest(stream=stream):
                with self.assertRaises(MOD.Blocked):
                    MOD.parse_stream('codex-cli', stream)

    def test_path_traversal_and_git_metadata_cannot_be_authorized(self):
        for path in ['../outside', '.git/config', '/tmp/outside', 'a/../a.py']:
            with self.subTest(path=path):
                req = self.request(scope=[path])
                self.assertEqual(self.run_request(req)['status'], 'BLOCKED')
        self.assertFalse(self.calls)

    def test_session_state_cannot_be_inside_candidate(self):
        req = self.request()
        result = MOD.dispatch(req, self.repo / 'session-state', self.provider(req))
        self.assertEqual(result['failure_category'], 'configuration_invalid')
        self.assertFalse((self.repo / 'session-state').exists())

    def test_low_risk_label_without_required_justification_is_rejected(self):
        req = self.request(operation='repair', write_scope=['a.py'], repair={'risk': 'LOW'})
        self.assertEqual(self.run_request(req)['failure_category'], 'authorization_violation')
        self.assertFalse(self.calls)

    def test_contract_changes_invalidate_outbound_approval(self):
        req = self.request()
        original = MOD.context_digest(req)
        # Same request with another installed contract is different outbound context.
        from unittest import mock
        original_read = Path.read_bytes
        def changed(path):
            data = original_read(path)
            return data + b'\nchanged contract' if path.name == 'collaboration-prompt.md' else data
        with mock.patch.object(Path, 'read_bytes', changed):
            self.assertNotEqual(MOD.context_digest(req), original)
            self.assertEqual(self.run_request(req)['failure_category'], 'authorization_violation')
        self.assertFalse(self.calls)

    def test_execute_timeout_terminates_descendant_writer(self):
        destination = Path(self.tmp.name) / 'must-not-appear'
        child = "import time; from pathlib import Path; time.sleep(0.5); Path(" + repr(str(destination)) + ").write_text('bad')"
        parent = 'import subprocess, time; subprocess.Popen(["python3", "-c", ' + repr(child) + ']); time.sleep(10)'
        with self.assertRaises(MOD.Blocked):
            MOD.execute(['python3', '-c', parent], '', self.repo, 0.2)
        threading.Event().wait(0.7)
        self.assertFalse(destination.exists())

    def test_snapshot_cli_does_not_invoke_provider(self):
        output = subprocess.check_output(['python3', str(SCRIPT), '--snapshot', str(self.repo)])
        summary = json.loads(output)
        self.assertEqual(summary['digest'], MOD.snapshot(self.repo)['digest'])
        self.assertEqual(summary['file_count'], 1)
        self.assertNotIn('files', summary)

    def test_ignored_build_files_do_not_drift_candidate(self):
        (self.repo / '.gitignore').write_text('build/\n')
        before = MOD.snapshot(self.repo)['digest']
        (self.repo / 'build').mkdir()
        (self.repo / 'build' / 'cache').write_text('generated')
        self.assertEqual(MOD.snapshot(self.repo)['digest'], before)
        req = self.request(scope=['build/cache'])
        self.assertEqual(self.run_request(req)['failure_category'], 'authorization_violation')

    def test_syntax_only_fix_cannot_claim_repaired_without_changes(self):
        req = self.repair_request()
        self.assertEqual(self.run_request(req)['failure_category'], 'verification_failed')

    def test_preapproved_small_fix_in_same_review_call(self):
        policy = {'risk': 'LOW', 'behavior_defined': True, 'bounded': True,
                  'rationale': 'Approved internal value invariant', 'finding_ids': []}
        req = self.request(write_scope=['a.py'], repair=policy)
        fixed = [{'id': 'F1', 'location': 'a.py:1', 'classification': 'FINDING', 'change_risk': 'LOW',
                  'severity': 'LOW', 'required_fix': 'Correct the constant',
                  'evidence': 'Explicit value invariant', 'resolution': 'Corrected the local constant'}]
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n'), fixed_findings=fixed))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['closure_candidates'], ['F1'])
        self.assertEqual(result['closure_basis'], 'strong-self-fix')
        self.assertEqual(len(self.calls), 1)

    def test_mixed_batch_keeps_large_finding_open_after_small_fix(self):
        req = self.request(write_scope=['a.py'], repair={'risk': 'LOW', 'behavior_defined': True,
                           'bounded': True, 'rationale': 'Approved small fixes only', 'finding_ids': []})
        fixed = [{'id': 'F1', 'location': 'a.py:1', 'classification': 'FINDING', 'change_risk': 'LOW',
                  'severity': 'LOW', 'required_fix': 'Correct the constant',
                  'evidence': 'Explicit invariant', 'resolution': 'Local fix'}]
        pending = [{'id': 'F2', 'severity': 'HIGH', 'classification': 'FINDING', 'change_risk': 'HIGH',
                    'location': 'a.py:2', 'evidence': 'Module contract violation', 'required_fix': 'Return large task to worker'}]
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n'),
                                  status='FINDINGS', fixed_findings=fixed, findings=pending))
        self.assertEqual(result['status'], 'FINDINGS')
        self.assertFalse(result['closure_candidate'])
        self.assertEqual(result['closure_candidates'], ['F1'])
        self.assertEqual(result['findings'], pending)

    def test_preapproval_cannot_turn_high_risk_change_into_self_fix(self):
        req = self.request(write_scope=['a.py'], repair={'risk': 'LOW', 'behavior_defined': True,
                           'bounded': True, 'rationale': 'Only small fixes', 'finding_ids': []})
        fixed = [{'id': 'F1', 'location': 'a.py:1', 'classification': 'FINDING', 'change_risk': 'HIGH',
                  'severity': 'LOW', 'required_fix': 'Migrate API',
                  'evidence': 'Changed public API', 'resolution': 'Migrated API'}]
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n'), fixed_findings=fixed))
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result['closure_candidate'])

    def test_review_write_requires_fixed_finding_records(self):
        req = self.request(write_scope=['a.py'], repair={'risk': 'LOW', 'behavior_defined': True,
                           'bounded': True, 'rationale': 'Only small fixes', 'finding_ids': []})
        result = self.run_request(req, self.provider(req, lambda: (self.repo / 'a.py').write_text('value = 2\n')))
        self.assertEqual(result['failure_category'], 'schema_invalid')

    def test_new_work_plan_does_not_require_inventing_a_finding(self):
        req = self.request(operation='plan', verification=[])
        tasks = [{'finding_ids': [], 'goal': 'Implement approved capability', 'write_scope': ['a.py'],
                  'steps': ['Implement approved behavior'], 'verification': ['Run acceptance test'],
                  'stop_conditions': ['Undefined product behavior']}]
        self.assertEqual(self.run_request(req, self.provider(req, status='PLANNED', tasks=tasks))['status'], 'PLANNED')

    def test_nonobject_event_parts_fail_closed(self):
        for backend, event in [('codex-cli', {'item': None}), ('opencode-cli', {'part': None})]:
            with self.subTest(backend=backend), self.assertRaises(MOD.Blocked):
                MOD.parse_stream(backend, json.dumps(event))


if __name__ == '__main__':
    unittest.main()

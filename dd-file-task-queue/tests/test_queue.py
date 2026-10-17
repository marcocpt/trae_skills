import importlib.util
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'queue.py'


class QueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('file_queue', SCRIPT)
        cls.q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.q)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'queue'
        self.q.initialize(self.root)

    def publish(self, task='T1', dependencies=None, scope=None):
        p = self.root / 'pending' / task
        p.mkdir()
        (p / 'task.json').write_text(json.dumps({
            'task_id': task, 'depends_on': dependencies or [],
            'write_scope': scope or [],
            'required_outputs': ['REPORT.md', 'baseline.json'],
        }))
        (p / 'prompt.md').write_text('Only synthetic files. No Git actions.')
        return p

    def done(self, task='T1', status='completed', extra=None):
        p = self.root / 'running' / task
        (p / 'REPORT.md').write_text('Synthetic report')
        (p / 'baseline.json').write_text('{}')
        hashes = {n: hashlib.sha256((p / n).read_bytes()).hexdigest()
                  for n in ['REPORT.md', 'baseline.json']}
        hashes.update(extra or {})
        (p / 'DONE.json').write_text(json.dumps({
            'task': task, 'status': status, 'outputs': hashes,
        }))
        return p

    def test_competing_claims_have_one_winner(self):
        self.publish()
        def attempt(owner):
            try:
                return self.q.claim(self.root, 'T1', owner)
            except self.q.QueueError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            winners = [x for x in pool.map(attempt, map(str, range(8))) if x]
        self.assertEqual(len(winners), 1)
        self.assertFalse((self.root / 'pending/T1').exists())

    def test_dependencies_require_primary_acceptance(self):
        self.publish('T1')
        self.publish('T2', ['T1'])
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        self.done()
        self.q.submit(self.root, 'T1', token)
        with self.assertRaises(self.q.QueueError):
            self.q.claim(self.root, 'T2', 'worker')
        self.q.close(self.root, 'T1', 'accepted', 'primary checked synthetic evidence')
        self.q.claim(self.root, 'T2', 'worker')

    def test_rejected_dependency_stays_blocked(self):
        self.publish('T1')
        self.publish('T2', ['T1'])
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        self.done()
        self.q.submit(self.root, 'T1', token)
        self.q.close(self.root, 'T1', 'rejected', 'missing evidence')
        with self.assertRaises(self.q.QueueError):
            self.q.claim(self.root, 'T2', 'worker')

    def test_write_scope_overlap(self):
        self.publish('T1', scope=['/synthetic/module'])
        self.publish('T2', scope=['/synthetic/module/file.py'])
        self.q.claim(self.root, 'T1', 'one')
        with self.assertRaises(self.q.QueueError):
            self.q.claim(self.root, 'T2', 'two')

    def test_siblings_can_run(self):
        self.publish('T1', scope=['/synthetic/a.py'])
        self.publish('T2', scope=['/synthetic/b.py'])
        self.q.claim(self.root, 'T1', 'one')
        self.q.claim(self.root, 'T2', 'two')

    def test_wrong_token_rejected(self):
        self.publish()
        self.q.claim(self.root, 'T1', 'worker')
        self.done()
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', 'wrong')

    def test_hash_drift_blocks_submit(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        p = self.done()
        (p / 'REPORT.md').write_text('changed')
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', token)
        self.assertTrue(p.exists())

    def test_hash_drift_blocks_close(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        self.done()
        self.q.submit(self.root, 'T1', token)
        (self.root / 'submitted/T1/REPORT.md').write_text('changed')
        with self.assertRaises(self.q.QueueError):
            self.q.close(self.root, 'T1', 'accepted', 'checked')

    def test_traversal_and_absolute_paths_rejected(self):
        for name in ['../outside', '/tmp/outside', 'sub/../../outside']:
            with self.subTest(name=name):
                self.publish('X' + str(len(list((self.root / 'running').iterdir()))))
                task = next(p.name for p in (self.root / 'pending').iterdir())
                token = self.q.claim(self.root, task, 'worker')['token']
                self.done(task, extra={name: '0' * 64})
                with self.assertRaises(self.q.QueueError):
                    self.q.submit(self.root, task, token)

    def test_symlink_output_rejected(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        p = self.done()
        (p / 'REPORT.md').unlink()
        (p / 'REPORT.md').symlink_to(p / 'baseline.json')
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', token)

    def test_task_identity_and_missing_output(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        p = self.done()
        obj = json.loads((p / 'DONE.json').read_text())
        obj['task'] = 'OTHER'
        (p / 'DONE.json').write_text(json.dumps(obj))
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', token)
        obj['task'] = 'T1'
        del obj['outputs']['baseline.json']
        (p / 'DONE.json').write_text(json.dumps(obj))
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', token)

    def test_packet_drift_after_claim_is_rejected(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        p = self.done()
        (p / 'prompt.md').write_text('changed scope')
        with self.assertRaises(self.q.QueueError):
            self.q.submit(self.root, 'T1', token)

    def test_submitted_done_cannot_be_replaced(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        self.done()
        self.q.submit(self.root, 'T1', token)
        p = self.root / 'submitted/T1/DONE.json'
        obj = json.loads(p.read_text())
        obj['extra'] = 'changed after publication'
        p.write_text(json.dumps(obj))
        with self.assertRaises(self.q.QueueError):
            self.q.verify(self.root, 'T1')

    def test_blocked_is_not_accepted_completion(self):
        self.publish()
        token = self.q.claim(self.root, 'T1', 'worker')['token']
        self.done(status='blocked')
        self.q.submit(self.root, 'T1', token)
        with self.assertRaises(self.q.QueueError):
            self.q.close(self.root, 'T1', 'accepted', 'checked')
        self.q.close(self.root, 'T1', 'rejected', 'needs upstream')

    def test_duplicate_task_and_symlink_state_rejected(self):
        self.publish()
        (self.root / 'closed/T1').mkdir()
        with self.assertRaises(self.q.QueueError):
            self.q.claim(self.root, 'T1', 'worker')
        (self.root / 'closed/T1').rmdir()
        (self.root / 'running').rmdir()
        (self.root / 'running').symlink_to(self.root / 'pending')
        with self.assertRaises(self.q.QueueError):
            self.q.claim(self.root, 'T1', 'worker')


if __name__ == '__main__':
    unittest.main()

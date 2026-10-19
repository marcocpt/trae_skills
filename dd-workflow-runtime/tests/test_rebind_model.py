"""Rebind actual isolated configuration copies without contacting providers."""
import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

AGENTS = Path(__file__).resolve().parents[1] / 'agents'


class RebindModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agents = self.root / 'dd-workflow-runtime/agents'
        shutil.copytree(AGENTS, self.agents, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.script = self.agents / 'rebind-model.py'
        self.bindings = self.agents / 'model-bindings.yaml'
        spec = importlib.util.spec_from_file_location('isolated_bindings', self.agents / 'validate-bindings.py')
        self.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.validator)

    def manifest(self):
        return {str(p.relative_to(self.agents)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.agents.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def run_rebind(self, *args):
        return subprocess.run([sys.executable, str(self.script), *args], text=True, capture_output=True)

    def test_codex_reviewer_only_and_native_products_match(self):
        before = self.validator.load_bindings(self.bindings)
        worker = (self.agents / 'codex/luna-worker.toml').read_bytes()
        run = self.run_rebind('codex', 'test-strong-model')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        after = self.validator.load_bindings(self.bindings)
        self.assertEqual(after['codex']['worker'], before['codex']['worker'])
        self.assertEqual((self.agents / 'codex/luna-worker.toml').read_bytes(), worker)
        self.assertEqual(after['codex']['reviewer']['model'], 'test-strong-model')
        for profile in ('strong-reviewer.toml', 'strong-reviewer-advisory.toml'):
            self.assertEqual(tomllib.loads((self.agents / 'codex' / profile).read_text())['model'], 'test-strong-model')
        self.assertEqual(after['codex']['reviewer']['effort'], before['codex']['reviewer']['effort'])
        for host in set(before) - {'codex'}:
            self.assertEqual(after[host], before[host])

    def test_opencode_updates_both_roles_and_all_declared_profiles(self):
        run = self.run_rebind('opencode', 'provider/test-model')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        bindings = self.validator.load_bindings(self.bindings)['opencode']
        self.assertEqual(bindings['worker']['model'], 'provider/test-model')
        self.assertEqual(bindings['reviewer']['model'], 'provider/test-model')
        self.assertEqual(self.validator.check_native(self.validator.load_bindings(self.bindings)), [])

    def test_dry_run_validates_without_changing_any_source_file(self):
        before = self.manifest()
        run = self.run_rebind('codex', 'test-strong-model', '--dry-run')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn('dry-run', run.stdout)
        self.assertEqual(self.manifest(), before)

    def test_validator_failure_leaves_all_original_bytes_intact(self):
        (self.agents / 'validate-review-routing.py').write_text('raise SystemExit(1)\n')
        before = self.manifest()
        run = self.run_rebind('codex', 'test-strong-model')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.manifest(), before)

    def test_missing_declared_product_is_rejected_before_writes(self):
        (self.agents / 'codex/strong-reviewer-advisory.toml').unlink()
        before = self.manifest()
        run = self.run_rebind('codex', 'test-strong-model')
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(self.manifest(), before)

    def test_shared_old_model_id_does_not_rebind_another_host(self):
        text = self.bindings.read_text().replace('model: performance', 'model: gpt-5.6-sol')
        self.bindings.write_text(text)
        qoder = self.agents / 'qoder/strong-reviewer.md'
        qoder.write_text(qoder.read_text().replace('model: performance', 'model: gpt-5.6-sol'))
        before = self.validator.load_bindings(self.bindings)['qoder']
        run = self.run_rebind('codex', 'test-strong-model')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.validator.load_bindings(self.bindings)['qoder'], before)

    def test_current_model_is_a_verified_no_op(self):
        model = self.validator.load_bindings(self.bindings)['codex']['reviewer']['model']
        before = self.manifest()
        run = self.run_rebind('codex', model)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.manifest(), before)

    def load_rebinder(self):
        spec = importlib.util.spec_from_file_location('isolated_rebinder', self.script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_io_failure_rolls_back_already_replaced_files(self):
        module = self.load_rebinder()
        plan = module._plan('codex', 'test-strong-model')
        before = self.manifest()
        real_write = module._atomic_write
        calls = []
        def fail_second(path, content):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('simulated write failure')
            real_write(path, content)
        with mock.patch.object(module, '_atomic_write', side_effect=fail_second):
            with self.assertRaises(OSError):
                module._publish(plan)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.manifest(), before)

    def test_concurrent_edit_is_preserved_before_publication(self):
        module = self.load_rebinder()
        plan = module._plan('codex', 'test-strong-model')
        self.bindings.write_text(self.bindings.read_text() + '\n# concurrent owner edit\n')
        before = self.manifest()
        with self.assertRaisesRegex(ValueError, 'Concurrent change'):
            module._publish(plan)
        self.assertEqual(self.manifest(), before)

    def test_failed_model_listing_never_writes(self):
        module = self.load_rebinder()
        before = self.manifest()
        with mock.patch.object(module.subprocess, 'run', return_value=mock.Mock(returncode=1, stdout='provider/test-model')):
            self.assertFalse(module._check_models('opencode', 'provider/test-model'))
        self.assertEqual(self.manifest(), before)


if __name__ == '__main__':
    unittest.main()

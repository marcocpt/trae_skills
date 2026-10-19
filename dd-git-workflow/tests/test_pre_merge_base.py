"""Local merge target must not inherit the remote tracking branch's age."""
import datetime
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pre-merge-check.sh'


class PreMergeBaseTests(unittest.TestCase):
    def setUp(self):
        version = subprocess.check_output(['git', '--version'], text=True)
        numbers = tuple(map(int, re.search(r'(\d+)\.(\d+)', version).groups()))
        if numbers < (2, 38):
            self.skipTest('merge-tree --write-tree needs Git 2.38+')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'develop')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        (self.repo / 'a.py').write_text('first')
        self.git('add', '.')
        self.commit('remote baseline', 3)
        self.git('update-ref', 'refs/remotes/origin/develop', self.git('rev-parse', 'HEAD'))
        (self.repo / 'a.py').write_text('local develop')
        self.git('add', '.')
        self.commit('local develop work', 2)
        self.git('switch', '-qc', 'feature/test')
        (self.repo / 'a.py').write_text('feature')
        self.git('add', '.')
        self.git('commit', '-qm', 'feat: feature\n\nPublicFile: a.py')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def commit(self, message, days):
        when = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', message], env=env, check=True)

    def checklist(self, *args):
        return json.loads(subprocess.check_output(['bash', str(SCRIPT), *args], cwd=self.repo, text=True))['PreMergeChecklist']

    def test_local_target_uses_local_merge_base(self):
        result = self.checklist('develop')
        self.assertEqual(result['base'], 'develop')
        self.assertTrue(result['all_pass'])
        self.assertEqual(result['checks']['sync']['ahead'], 1)
        self.assertEqual(result['checks']['public_file_age']['age_days'], 0)

    def test_default_preserves_remote_target_policy(self):
        result = self.checklist()
        self.assertEqual(result['base'], 'origin/develop')
        self.assertFalse(result['all_pass'])
        self.assertGreaterEqual(result['checks']['public_file_age']['age_days'], 2)


if __name__ == '__main__':
    unittest.main()

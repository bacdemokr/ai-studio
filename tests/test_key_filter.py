import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class KeyFilterTests(unittest.TestCase):
    def test_git_stages_empty_placeholder_without_changing_local_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root/'scripts').mkdir()
            shutil.copy2(ROOT/'scripts/setup-key-filter.sh', root/'scripts/setup-key-filter.sh')
            shutil.copy2(ROOT/'.gitattributes', root/'.gitattributes')
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            git('init')
            subprocess.run(['bash','scripts/setup-key-filter.sh'],cwd=root,check=True)
            (root/'api.cfg').write_text('fixture-secret-not-real\n')
            git('add','api.cfg','.gitattributes')
            self.assertEqual(git('show',':api.cfg'), b'')
            self.assertEqual((root/'api.cfg').read_text(), 'fixture-secret-not-real\n')
            (root/'api.cfg').write_text('fixture-replacement\n')
            git('add','-A')
            self.assertEqual(git('show',':api.cfg'), b'')
            self.assertEqual((root/'api.cfg').read_text(), 'fixture-replacement\n')
            self.assertEqual(git('diff','--','api.cfg'), b'')

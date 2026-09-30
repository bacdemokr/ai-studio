"""Legacy credential files stay outside version control."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class KeyIgnoreTests(unittest.TestCase):
    def test_legacy_key_is_ignored_without_a_git_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            subprocess.run(['git','init','-q',directory],check=True)
            source=Path(__file__).resolve().parents[1]
            (root/'.gitignore').write_bytes((source/'.gitignore').read_bytes())
            (root/'api.cfg').write_text('fixture-key-not-real')
            result=subprocess.run(['git','check-ignore','api.cfg'],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stdout.strip(),'api.cfg')

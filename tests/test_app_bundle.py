"""App patches reuse dependencies, load a snapshot, and leave data alone."""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', ROOT/'docker/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class AppBundleTests(unittest.TestCase):
    def test_patch_isolated_until_restart_and_runtime_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'source'; app = root/'app'; app.mkdir()
            for name in bootstrap.INPUTS:
                path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('dependency')
            for name in ('scripts','src','crew','skills','runtime/research-guard'):
                (source/name).mkdir(parents=True, exist_ok=True)
            for name in ('index.mjs', 'openclaw.plugin.json'):
                (source/'runtime/research-guard'/name).write_text('guard-v1')
            (source/'README.md').write_text('app')
            (source/'scripts/container_runtime.py').write_text('')
            (source/'scripts/build.py').write_text("from pathlib import Path\nPath('built').write_text(Path('src/studio.js').read_text())")
            (source/'src/studio.js').write_text('v1')
            manifest = root/'manifest.json'; manifest.write_text(json.dumps(bootstrap.fingerprint(source)))
            data = root/'data'; data.mkdir(); (data/'chat').write_text('keep')
            bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'runtime/research-guard/index.mjs').read_text(), 'guard-v1')
            (source/'runtime/research-guard/index.mjs').write_text('guard-v2')
            (source/'src/studio.js').write_text('v2')
            bootstrap.check(source, manifest)
            self.assertEqual((app/'built').read_text(), 'v1')
            bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'built').read_text(), 'v2')
            self.assertEqual((app/'runtime/research-guard/index.mjs').read_text(), 'guard-v2')
            (source/'runtime/research-guard/openclaw.plugin.json').unlink()
            with self.assertRaisesRegex(RuntimeError, 'Incomplete app bundle.*research-guard'):
                bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'runtime/research-guard/index.mjs').read_text(), 'guard-v2')
            self.assertEqual((data/'chat').read_text(), 'keep')
            (source/'docker/runtime-lock.json').write_text('different')
            with self.assertRaisesRegex(RuntimeError, 'different runtime'):
                bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'built').read_text(), 'v2')


@unittest.skipUnless(shutil.which('node'), 'Node is needed to check bundled JavaScript')
class AppPreflightTests(unittest.TestCase):
    def test_incomplete_or_broken_patch_rejected_without_changing_built_page(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('scripts', 'src', 'crew', 'skills', 'runtime'):
                shutil.copytree(ROOT / name, root / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            (root / 'app').mkdir()
            page = root / 'app/index.html'
            page.write_text('last working page')
            def check():
                return subprocess.run([sys.executable, str(root / 'scripts/build.py'), '--check'],
                                      capture_output=True, text=True, timeout=30)
            result = check()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(page.read_text(), 'last working page')
            guard = root / 'runtime/research-guard/index.mjs'
            guard_source = guard.read_text()
            guard.unlink()
            self.assertIn('Incomplete app bundle: missing runtime/research-guard/index.mjs', check().stderr)
            guard.write_text(guard_source)
            module = root / 'src/studio-settings.js'
            saved = module.read_text()
            module.write_text(saved + '\nconst broken = ;')
            self.assertNotEqual(check().returncode, 0)
            module.write_text(saved)
            module.unlink()
            self.assertNotEqual(check().returncode, 0)
            module.write_text(saved)
            (root / 'skills/bac-writer/SKILL.md').unlink()
            self.assertIn('Incomplete app bundle', check().stderr)
            self.assertEqual(page.read_text(), 'last working page')


if __name__ == '__main__':
    unittest.main()

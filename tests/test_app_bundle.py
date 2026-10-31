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
    def test_resources_are_grouped_in_header(self):
        page = (ROOT / 'app/index.html').read_text(encoding='utf-8')
        header = page[page.index('<header class="topbar'):page.index('</header>')]
        self.assertIn('id="studio-resources"', header)
        for url in ('https://www.nvidia.com/en-us/ai/build-a-claw/', 'https://brev.nvidia.com/', 'https://brev.nvidia.com/launchables?tab=explore',
                    'https://openclaw.ai/', 'https://www.nvidia.com/en-us/ai/openshell/'):
            self.assertIn(f'href="{url}" target="_blank" rel="noopener noreferrer"', header)
        self.assertNotIn('id="campus-openclaw-link"', page)
        self.assertNotIn('id="campus-openshell-link"', page)
        self.assertIn("'interface-design':'UX design'", page)
        self.assertNotIn("'interface-design':'Interface design'", page)
        self.assertIn('data-goal-hint="${escape(goalHint(g))}"', page)
        self.assertIn('content:attr(data-goal-hint)', page)
        self.assertIn("data-term-overview=\"'+guide.overview+'\">Overview</a>", page)
        self.assertIn("window.BacOverviewImages={agent:'data:image/png;base64,", page)
        self.assertIn(",openshell:'data:image/png;base64,", page)
        self.assertIn("termOverview.className='world-term-overview'", page)
        self.assertIn('class="world-room-paper-drag" title="Drag to move"', page)
        self.assertIn('movablePaper(termOverview,{width:1920,height:1080})', page)
        self.assertIn('overflow:auto;resize:both;', page)
        self.assertIn('id="studio-mission-reasoning"', page)
        self.assertIn('Advanced reasoning', page)
        self.assertIn('Opening this view does not run the model again.', page)
        self.assertIn('width:80%;min-width:280px;min-height:180px;max-width:min(calc(100% - 20px),1920px)', page)
        self.assertIn('width:min(calc(100% - 20px),1920px);height:min(calc(100% - 20px),1080px)', page)
        self.assertNotIn('__AGENT_BIG_PICTURE_DATA_URL__', page)
        self.assertNotIn('__OPENSHELL_OVERVIEW_DATA_URL__', page)

    def test_patch_isolated_until_restart_and_runtime_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'source'; app = root/'app'; app.mkdir()
            for name in bootstrap.INPUTS:
                path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('dependency')
            for name in ('scripts','src','skills','scenario','runtime/research-guard'):
                (source/name).mkdir(parents=True, exist_ok=True)
            for name in ('index.mjs', 'openclaw.plugin.json'):
                (source/'runtime/research-guard'/name).write_text('guard-v1')
            (source/'README.md').write_text('app')
            (source/'VERSION').write_text('0.1.0')
            (source/'source-version.json').write_text('{"commit":"source-1"}')
            (source/'scenario/email.txt').write_text('sample input')
            (source/'scripts/container_runtime.py').write_text('')
            (source/'scripts/build.py').write_text("from pathlib import Path\nPath('built').write_text(Path('src/studio.js').read_text())")
            (source/'src/studio.js').write_text('v1')
            (source/'src/avatar-catalog.json').write_text('{"bodies":[]}')
            manifest = root/'manifest.json'; manifest.write_text(json.dumps(bootstrap.fingerprint(source)))
            data = root/'data'; data.mkdir(); (data/'chat').write_text('keep')
            bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'runtime/research-guard/index.mjs').read_text(), 'guard-v1')
            self.assertEqual((app/'scenario/email.txt').read_text(), 'sample input')
            self.assertEqual(json.loads((app/'src/avatar-catalog.json').read_text()), {'bodies': []})
            self.assertEqual((app/'VERSION').read_text(), '0.1.0')
            self.assertEqual(json.loads((app/'source-version.json').read_text())['commit'], 'source-1')
            (source/'source-version.json').unlink()
            (source/'runtime/research-guard/index.mjs').write_text('guard-v2')
            (source/'src/studio.js').write_text('v2')
            bootstrap.check(source, manifest)
            self.assertEqual((app/'built').read_text(), 'v1')
            bootstrap.stage(source, app, manifest)
            self.assertEqual((app/'built').read_text(), 'v2')
            self.assertFalse((app/'source-version.json').exists())
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
            for name in ('scripts', 'src', 'skills', 'runtime', 'scenario'):
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
            catalog = root / 'src/avatar-catalog.json'
            catalog_source = catalog.read_text()
            catalog.unlink()
            self.assertIn('Incomplete app bundle: missing src/avatar-catalog.json', check().stderr)
            self.assertEqual(page.read_text(), 'last working page')
            catalog.write_text(catalog_source)
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
            document = root/'scenario/demo-france-store-status-email-thread.txt'
            content = document.read_text()
            document.unlink()
            self.assertIn('Incomplete app bundle: missing scenario/', check().stderr)
            document.write_text(content)
            (root / 'skills/bac-writer/SKILL.md').unlink()
            self.assertIn('Incomplete app bundle', check().stderr)
            self.assertEqual(page.read_text(), 'last working page')


if __name__ == '__main__':
    unittest.main()

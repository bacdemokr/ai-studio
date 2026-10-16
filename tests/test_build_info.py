import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_info


class BuildIdentityTests(unittest.TestCase):
    def test_bundle_keeps_provenance_without_git_and_bump_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'BAC_DEMO_VERSION':''}):
            root=Path(folder);(root/'VERSION').write_text('0.3.9\n')
            (root/'source-version.json').write_text(json.dumps({'commit':'a'*40,'branch':'preview/visitor-agent-teams','modified':False}))
            self.assertEqual(build_info.read(root)['version'],'0.3.9')
            self.assertEqual(build_info.read(root)['commit'],'a'*40)
            self.assertEqual(build_info.bump('patch',root),'0.3.010')
            self.assertEqual(build_info.bump('minor',root),'0.4.000')
            self.assertEqual(build_info.bump('major',root),'1.0.000')

    def test_publication_sequence_preserves_padding_and_grows_past_999(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'VERSION').write_text('0.2.001\n')
            self.assertEqual(build_info.bump('patch', root), '0.2.002')
            self.assertEqual(build_info.bump('patch', root), '0.2.003')
            (root/'VERSION').write_text('0.2.999\n')
            self.assertEqual(build_info.bump('patch', root), '0.2.1000')

    def test_legacy_local_preview_env_does_not_hide_version(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'BAC_DEMO_VERSION':'local-preview'}):
            root=Path(folder);(root/'VERSION').write_text('0.3.0\n')
            self.assertEqual(build_info.read(root)['version'],'0.3.0')
        with patch.dict(os.environ, {'BAC_DEMO_VERSION':'0.4.1'}):
            self.assertEqual(build_info.read()['version'],'0.4.1')

    def test_repeated_read_does_not_mutate_version_or_expose_lock_downloads(self):
        value=build_info.read();self.assertEqual(value,build_info.read())
        self.assertEqual(set(value['runtime']),{'node','openclaw','openshell'})
        self.assertNotIn('downloads',value)

if __name__=='__main__':unittest.main()

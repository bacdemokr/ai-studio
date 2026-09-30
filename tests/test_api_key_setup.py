import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import tempfile
import unittest
from unittest.mock import patch
import api_key_setup as api


class KeySetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'api.cfg'
        self.path.write_text('')

    def test_empty_file_prompts_and_saves_only_valid_key(self):
        def validate(key):
            if key != 'fixture-valid': raise api.InvalidKey('Rejected')
            return []
        with patch.object(api, 'validate', side_effect=validate), patch.object(api.getpass, 'getpass', side_effect=['bad', 'fixture-valid']) as prompt, patch.object(api, 'save_connection') as save, patch.object(api.os, 'geteuid', return_value=1000):
            api.setup(self.path, interactive=True)
        self.assertEqual(prompt.call_count, 2)
        self.assertEqual(self.path.read_text(), 'fixture-valid\n')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        save.assert_called_once_with('fixture-valid', [])

    def test_valid_file_does_not_prompt(self):
        self.path.write_text('fixture-valid\n')
        with patch.object(api, 'validate', return_value=[]), patch.object(api.getpass, 'getpass') as prompt, patch.object(api, 'save_connection'), patch.object(api.os, 'geteuid', return_value=1000):
            api.setup(self.path, interactive=False)
        prompt.assert_not_called()

    def test_outage_preserves_key_without_prompting(self):
        self.path.write_text('existing')
        with patch.object(api, 'validate', side_effect=api.ServiceUnavailable('Offline')), patch.object(api.getpass, 'getpass') as prompt, patch.object(api, 'save_connection') as save:
            with self.assertRaises(api.ServiceUnavailable): api.setup(self.path, interactive=True)
        self.assertEqual(self.path.read_text(), 'existing')
        prompt.assert_not_called(); save.assert_not_called()

    def test_empty_noninteractive_does_not_use_old_persisted_key(self):
        with self.assertRaisesRegex(api.InvalidKey, 'terminal'):
            api.setup(self.path, interactive=False)
        self.assertEqual(self.path.read_text(), '')

    def test_checks_inference_not_only_model_listing(self):
        with patch.object(api, 'request', side_effect=[{'data':[{'id':m} for m in api.MODELS]}, {'choices':[{'message':{'content':'OK'}}]}]) as req:
            self.assertTrue(api.validate('fixture-valid'))
        self.assertEqual(req.call_args_list[1].args[1], '/chat/completions')

    def test_auth_rejected_but_rate_limit_not_labeled_invalid(self):
        import urllib.error
        for status, expected in [(401, api.InvalidKey), (403, api.InvalidKey), (429, api.ServiceUnavailable), (503, api.ServiceUnavailable)]:
            with patch.object(api.urllib.request, 'urlopen', side_effect=urllib.error.HTTPError(api.BASE_URL,status,'error',{},None)):
                with self.assertRaises(expected): api.request('fixture', '/models')

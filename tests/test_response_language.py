"""Language preference must reach native requests without changing their contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent_runtime as runtime
from response_language import RESPONSE_LANGUAGE


class ResponseLanguageTests(unittest.TestCase):
    def test_chat_control_and_image_requests_keep_payloads_and_model_output(self):
        result = '{"done":true,"outcome":"complete","answer":"완료: artifacts/page.html"}'
        def gateway(path, *args, **kwargs):
            if path == '/v1/models':
                return {'data': [{'id': 'openclaw/language-test'}]}
            return {'choices': [{'message': {'content': result}}]}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(runtime, 'root', return_value=Path(directory)), \
             patch.object(runtime, 'gateway', side_effect=gateway) as call, \
             patch.object(runtime, 'observed_activity', return_value={'calls': []}), \
             patch.object(runtime, 'model_endpoint', return_value={}), \
             patch('user_location.context', return_value='User location: Seoul'), \
             patch('telemetry.measure', return_value={}):
            for structured, images in ((False, None), (True, None),
                                       (False, [{'mime': 'image/png', 'data': 'aW1hZ2U='}])):
                with self.subTest(structured=structured, images=bool(images)):
                    original = 'Please answer in English. Keep `const x = 1;` and artifacts/page.html.'
                    answer = runtime.respond('language-test', 'test', original,
                                             json_response=structured, images=images)
                    payload = call.call_args.args[1]
                    content = payload['messages'][0]['content']
                    prompt = content[0]['text'] if images else content
                    self.assertTrue(prompt.startswith(original))
                    self.assertTrue(prompt.endswith(RESPONSE_LANGUAGE))
                    self.assertEqual(prompt.count(RESPONSE_LANGUAGE), 1)
                    self.assertIn('User location: Seoul', prompt)
                    self.assertEqual(str(answer), result)  # No translation/rewrite of returned code or JSON.
                    self.assertEqual(json.loads(answer)['outcome'], 'complete')
                    self.assertEqual(payload.get('response_format'),
                                     {'type': 'json_object'} if structured else None)
                    if images:
                        self.assertEqual(content[1]['image_url']['url'], 'data:image/png;base64,aW1hZ2U=')

    def test_native_workspace_preference_preserves_user_edited_documents(self):
        with tempfile.TemporaryDirectory() as directory, patch('user_location.sync'):
            workspace = Path(directory)
            profile = {'name': 'Fixture', 'persona': 'guide', 'skills': ['radar']}
            runtime.write_workspace(workspace, profile)
            self.assertIn(RESPONSE_LANGUAGE, (workspace / 'AGENTS.md').read_text())
            self.assertTrue((workspace / 'HEARTBEAT.md').is_file())
            custom = '# My instructions\nReply in English when I explicitly ask.\n'
            (workspace / 'AGENTS.md').write_text(custom)
            with patch('document_edits.edited_paths', return_value={'AGENTS.md'}):
                runtime.write_workspace(workspace, profile)
            self.assertEqual((workspace / 'AGENTS.md').read_text(), custom)


if __name__ == '__main__':
    unittest.main()

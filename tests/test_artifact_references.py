import json
import unittest
from artifact_references import relative_references
from telemetry import Reply


class ArtifactReferencesTests(unittest.TestCase):
    def test_deployment_paths_and_nested_files(self):
        for root in ('/Users/sample/My Demo', '/home/demo/workspace', '/srv/bac/agents/abc'):
            with self.subTest(root=root):
                path = root + '/artifacts/reports/brief (1).md'
                self.assertEqual(relative_references('Saved `' + path + '`', root),
                                 'Saved `artifacts/reports/brief (1).md`')
                self.assertEqual(relative_references('[Brief](<' + path + '>)', root),
                                 '[Brief](<artifacts/reports/brief (1).md>)')

    def test_unrelated_paths_urls_and_code_preserved(self):
        root = '/home/demo'
        code = '```python\nopen("/home/demo/artifacts/report.md")\n```'
        url = 'https://example.com/home/demo/artifacts/report.md'
        other = '/home/other/artifacts/report.md'
        text = code + '\n' + url + '\n' + other + '\n/home/demo/artifacts/report.md'
        self.assertEqual(relative_references(text, root), code + '\n' + url + '\n' + other + '\nartifacts/report.md')
        unfinished = '```python\nopen("/home/demo/artifacts/report.md")'
        self.assertEqual(relative_references(unfinished, root), unfinished)

    def test_json_and_reply_metadata_preserved(self):
        text = json.dumps({'done': True, 'answer': 'Saved /srv/agent/artifacts/brief.md',
                           'files': ['artifacts/shared-abc.md']})
        reply = Reply(text, {'tokens': 42})
        reply.activity = {'observed': True}
        result = relative_references(reply, '/srv/agent', structured=True)
        self.assertEqual(json.loads(result), {'done': True, 'answer': 'Saved artifacts/brief.md',
                                             'files': ['artifacts/shared-abc.md']})
        self.assertEqual(result.metrics, reply.metrics)
        self.assertEqual(result.activity, reply.activity)
        self.assertEqual(relative_references('{bad json', '/srv/agent', structured=True), '{bad json')

    def test_relative_download_reference_and_file_uri(self):
        self.assertEqual(relative_references('artifacts/shared-job-r5.html', '/srv/agent'),
                         'artifacts/shared-job-r5.html')
        self.assertEqual(relative_references('file:///srv/agent/artifacts/report.md', '/srv/agent'),
                         'artifacts/report.md')

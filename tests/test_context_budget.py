import tempfile
import json
import unittest
from pathlib import Path
from agent_activity import context_failure
from runtime_settings import apply_context_limits

class ContextBudgetTests(unittest.TestCase):
    def test_compaction_leaves_headroom_and_preserves_stricter_limits(self):
        config=apply_context_limits({})
        self.assertEqual(config['agents']['defaults']['compaction']['keepRecentTokens'],8192)
        self.assertEqual(config['tools']['web']['fetch']['maxCharsCap'],4000)
        config['agents']['defaults']['compaction']['keepRecentTokens']=4096
        config['tools']['web']['fetch']['maxCharsCap']=2000
        apply_context_limits(config)
        self.assertEqual(config['agents']['defaults']['compaction']['keepRecentTokens'],4096)
        self.assertEqual(config['tools']['web']['fetch']['maxChars'],2000)
    def test_native_precheck_diagnosis_is_scoped_and_redacted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'state').mkdir()
            (p/'gateway.log').write_text('2026-09-30T13:33:57+02:00 [agent/embedded] [context-overflow-diag] sessionKey=agent:a:openai-user:s private-details\n')
            result=context_failure(p/'state','a','s',0)
            self.assertEqual(result['code'],'context-overflow')
            self.assertNotIn('private-details',str(result))
            self.assertIsNone(context_failure(p/'state','b','s',0))
            self.assertIsNone(context_failure(p/'state','a','s',9999999999))
            self.assertIsNone(context_failure(p/'state','a','s-other',0))

    def test_persistent_native_json_log_and_normal_precheck(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            log = p/'gateway-native.log'
            def record(tag):
                return json.dumps({'0': json.dumps({'subsystem':'agent/embedded'}),
                    '1': tag+' sessionKey=agent:a:openai-user:s private-details',
                    'time':'2026-09-30T13:33:57+00:00'})
            log.write_text(record('[context-overflow-precheck]'))
            self.assertIsNone(context_failure(p/'state','a','s',0))
            log.write_text('invalid partial line\n'+record('[context-overflow-diag]'))
            result = context_failure(p/'state','a','s',0)
            self.assertEqual(result['code'],'context-overflow')
            self.assertNotIn('private-details',str(result))
            self.assertIsNone(context_failure(p/'state','other','s',0))
            self.assertIsNone(context_failure(p/'state','a','s',9999999999))

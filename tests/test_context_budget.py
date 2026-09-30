import tempfile
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

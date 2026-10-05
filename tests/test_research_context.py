"""Regression for web research ending as a generic HTTP 500 after tool reads."""
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import agent_runtime as runtime
import runtime_settings as settings
from agent_activity import model_failure


class ResearchContextTests(unittest.TestCase):
    def test_native_length_hidden_by_500_is_diagnosed_without_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'state/agents/a/agent/openclaw-agent.sqlite'
            path.parent.mkdir(parents=True)
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE session_windows(session_id TEXT, session_key TEXT); '
                    'CREATE TABLE transcript_events(session_id TEXT,seq INTEGER,created_at INTEGER,event_json TEXT);')
                db.execute('INSERT INTO session_windows VALUES (?,?)', ('one', 'agent:a:openai-user:s'))
                # The observed failure had no content/errorMessage and only one
                # output token. It must not depend on hitting max output tokens.
                message = {'role':'assistant', 'stopReason':'length', 'content':[],
                           'usage':{'input':30873, 'output':1}}
                db.execute('INSERT INTO transcript_events VALUES (?,?,?,?)',
                    ('one', 1, int((time.time()+1)*1000), json.dumps({'message':message})))
            posts = []
            def gateway(route, *args, **kwargs):
                if route == '/v1/models':return {'data':[{'id':'openclaw/a'}]}
                posts.append(route)
                raise runtime.GatewayError('HTTP 500', 'request_failed')
            with patch.object(runtime, 'root', return_value=root), \
                 patch.object(runtime, 'gateway', side_effect=gateway), \
                 patch.object(runtime, 'observed_activity', return_value={'calls':[]}), \
                 patch('user_location.context', return_value=''):
                with self.assertRaises(runtime.GatewayError) as raised:
                    runtime.respond('a', 's', 'Research')
            self.assertEqual(raised.exception.reason, 'output-limit')
            self.assertNotIn('HTTP 500', str(raised.exception))
            self.assertEqual(len(posts), 1)
            self.assertIsNone(model_failure(root/'state', 'a', 'other', 0, 8192))
            self.assertIsNone(model_failure(root/'state', 'a', 's', time.time()+10, 8192))
            with sqlite3.connect(path) as db:
                db.execute('INSERT INTO transcript_events VALUES (?,?,?,?)',
                    ('one', 2, int((time.time()+2)*1000), json.dumps({'message':{'role':'assistant', 'stopReason':'stop'}})))
            self.assertIsNone(model_failure(root/'state', 'a', 's', 0, 8192))

    def test_bootstrap_and_reconnect_install_native_limits_without_changing_policy(self):
        config = runtime.initial_config()
        self.assertEqual(config['tools']['web']['fetch'], {'maxChars':3000, 'maxCharsCap':4000})
        config['tools']['web']['fetch'] = {'enabled':False, 'maxChars':1000, 'maxCharsCap':2000}
        config['agents']['entries']['protected'] = {'tools':{'deny':['web_fetch']}, 'sandbox':{'mode':'all'}}
        config['agents']['defaults']['compaction'] = {'keepRecentTokens':4000}
        profile = {'model':'test-model','baseUrl':'http://127.0.0.1:8000/v1','apiKey':'','contextWindow':32768}
        settings.apply_to_config(config, 'local', profile)
        self.assertEqual(config['tools']['web']['fetch'], {'enabled':False, 'maxChars':1000, 'maxCharsCap':2000})
        self.assertEqual(config['agents']['defaults']['compaction'], {'keepRecentTokens':4000, 'enabled':True, 'midTurnPrecheck':{'enabled':True}})
        self.assertEqual(config['agents']['entries']['protected']['tools'], {'deny':['web_fetch']})
        self.assertEqual(config['agents']['entries']['protected']['sandbox'], {'mode':'all'})


if __name__ == '__main__':unittest.main()

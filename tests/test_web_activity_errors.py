import unittest
import socket
import errno
import urllib.error
from types import SimpleNamespace
from agent_activity import web_failure_status, web_failure_reason, observed_access, collect
from collaboration_plan import compact_contributions
from live_plan_activity import snapshot
from session_secrets import connection_failure, CredentialExpired

class ActivityErrorTests(unittest.TestCase):
    def test_provider_and_demo_limits_are_not_policy_denials(self):
        for text,tool,reason in [
            ("Parallel MCP error: You've hit the free-tier rate limit", 'web_search', 'search-rate-limit'),
            ('Research budget reached. Save the evidence already retrieved.', 'web_fetch', 'research-budget'),
            ('Demo research budget reached. Save the evidence already retrieved.', 'web_fetch', 'research-budget'),
            ('Unspecified failure', 'web_fetch', 'tool-error')]:
            result={'isError':True,'content':[{'type':'text','text':text+' private token=secret'}]}
            self.assertEqual(web_failure_reason(result,tool),reason)
            result['isError']=False
            self.assertIsNone(web_failure_reason(result,tool))

    def test_observed_failures_reach_captain_without_raw_errors(self):
        reply=SimpleNamespace(activity={'calls':[
            {'tool':'web_search','status':'failed','failureReason':'search-rate-limit','target':'secret'},
            {'tool':'web_fetch','status':'failed','failureReason':'research-budget'},
            {'tool':'web_fetch','status':'completed','failureReason':'tool-error'},
        ]})
        access=observed_access({'protection':'standard'},reply)
        self.assertFalse(access['openShellEnabled'])
        self.assertFalse(access['confirmedPolicyDenial'])
        self.assertEqual([f['reason'] for f in access['toolFailures']],['Search service rate limit','Demo research limit'])
        contribution=compact_contributions([{'answer':'OpenShell blocked NVIDIA.', 'observedAccess':access, 'activity':reply.activity}])[0]
        self.assertEqual(contribution['observedAccess'],access)
        self.assertNotIn('secret',str(contribution))
        reply.policy_denials=['example.com']
        self.assertTrue(observed_access({'protection':'openshell'},reply)['confirmedPolicyDenial'])

    def test_native_transcript_classifies_only_actual_tool_errors(self):
        import tempfile, sqlite3, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'agents/scout/agent/openclaw-agent.sqlite'
            path.parent.mkdir(parents=True)
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE session_windows (session_id TEXT, session_key TEXT); CREATE TABLE transcript_events (session_id TEXT, seq INT, created_at INT, event_json TEXT);')
                db.execute('INSERT INTO session_windows VALUES (?,?)',('s','agent:scout:openai-user:task'))
                for seq,message in enumerate([
                    {'role':'assistant','content':[{'type':'toolCall','id':'search','name':'web_search','arguments':{'query':'earnings'}}]},
                    {'role':'toolResult','toolCallId':'search','isError':True,'content':[{'type':'text','text':'Parallel MCP error: free-tier rate limit token=secret'}]},
                    {'role':'assistant','content':[{'type':'text','text':'OpenShell blocked NVIDIA.'}]},
                ]):
                    db.execute('INSERT INTO transcript_events VALUES (?,?,?,?)',('s',seq,1,json.dumps({'message':message})))
            activity=collect(directory,'scout','task')
            self.assertEqual(activity['calls'][0]['failureReason'],'search-rate-limit')
            self.assertNotIn('secret',str(activity))
            public=snapshot(SimpleNamespace(observed_activity=lambda *args:activity),{'agent':'scout','session':'task','role':8,'started':0})
            self.assertEqual(public['calls'][0]['errorLabel'],'Search service rate limit')

    def test_only_status_leaves_failed_response(self):
        message={'content':[{'type':'text','text':'Web fetch failed (404): secret-page-content token=secret'}]}
        self.assertEqual(web_failure_status(message),404)
        activity=snapshot(SimpleNamespace(observed_activity=lambda *a:{'available':True,'calls':[{'tool':'web_fetch','status':'failed','httpStatus':404,'target':'https://example.com/?token=secret','errorLabel':'secret'}]}),{'agent':'a','session':'s','started':0,'role':8})
        self.assertEqual(activity['calls'][0]['errorLabel'],'404 - Page not found')
        self.assertNotIn('secret',str(activity))
        self.assertIsNone(web_failure_status({'content':[{'type':'text','text':'a page mentions 404 birds'}]}))

    def test_network_and_credentials_are_distinct(self):
        for error,code in [(CredentialExpired(),'model-credential-expired'),(socket.gaierror(),'model-dns-failed'),(TimeoutError(),'model-connection-timeout'),(OSError(errno.ENETUNREACH,'private'),'model-network-unreachable'),(urllib.error.URLError('private'),'model-connection-failed')]:
            status,actual,message=connection_failure(error)
            self.assertEqual(actual,code);self.assertNotIn('private',message)

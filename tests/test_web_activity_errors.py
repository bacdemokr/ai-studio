import unittest
import socket
import errno
import urllib.error
from types import SimpleNamespace
from agent_activity import web_failure_status
from live_plan_activity import snapshot
from session_secrets import connection_failure, CredentialExpired

class ActivityErrorTests(unittest.TestCase):
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

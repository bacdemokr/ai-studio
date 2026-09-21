"""Unchanged poll bodies disappear; mutations and owner checks stay observable."""
import http.client
import json
import tempfile
import threading
import unittest

from test_studio import Studio, Adapter
from serve import create_server


class StatePollingTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.studio=Studio(temporary.name,Adapter(),start_worker=False)
        self.person=self.studio.session()[0];self.owner=self.person['id']
        self.studio.onboard(self.owner,{'name':'Scout','skills':['documents']})
        self.server=create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def fetch(self,etag=None,owner=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            headers={'Cookie':'bac_session='+self.person['token'],'X-BaC-Agent':owner or self.owner}
            if etag:headers['If-None-Match']=etag
            connection.request('GET','/api/state',headers=headers)
            response=connection.getresponse()
            return response.status,response.getheader('ETag'),response.read()
        finally:connection.close()

    def test_unchanged_large_state_has_no_body_but_file_changes_refresh(self):
        memory=self.studio.workspace(self.owner)/'MEMORY.md';memory.write_text('Example saved preference.\n'*5000)
        status,etag,body=self.fetch()
        self.assertEqual(status,200);self.assertGreater(len(body),100000)
        status,same,body=self.fetch(etag)
        self.assertEqual((status,same,body),(304,etag,b''))
        memory.write_text('A new preference.')
        status,new,body=self.fetch(etag)
        self.assertEqual(status,200);self.assertNotEqual(new,etag)
        self.assertEqual(json.loads(body)['memory'],'A new preference.')

    def test_conditional_request_never_bypasses_agent_ownership(self):
        _,etag,_=self.fetch()
        foreign=self.studio.session()[0]['id'];self.studio.onboard(foreign,{'name':'Private','skills':['documents']})
        status,_,body=self.fetch(etag,foreign)
        self.assertEqual(status,404);self.assertNotIn(b'Private',body)


if __name__=='__main__':unittest.main()

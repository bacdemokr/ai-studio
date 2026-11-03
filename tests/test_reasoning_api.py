"""Reasoning is an account-owned on-demand resource, never part of polling state."""
import http.client,json,tempfile,threading,unittest
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from test_studio import Studio,Adapter
from serve import create_server
import model_reasoning as reasoning

class ReasoningAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.studio=Studio(self.temp.name,Adapter(),start_worker=False)
        self.person=self.studio.session()[0];self.owner=self.person['id']
        self.studio.onboard(self.owner,{'name':'Pixel','skills':['builder']})
        self.team=self.studio.crew_owner(self.owner)
        self.job=self.studio.enqueue(self.team,{'kind':'crew-chat','crewRole':0,'prompt':'Hello'})['id']
        def run():
            _,c=reasoning.request(json.dumps({'messages':[{'role':'user','content':reasoning.tag('task')}]}).encode(),'nvidia')
            c.feed(b'{"choices":[{"message":{"reasoning_content":"Published sentinel text"}}]}');c.finish()
        reasoning.call(self.studio,self.job,0,'Casey','Planning',run)
        self.server=create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
    def get(self,path,person=None,owner=None):
        person=person or self.person
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            c.request('GET','/api/'+path,headers={'Cookie':'bac_session='+person['token'],'X-BaC-Agent':owner or person['id']})
            r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()
    def test_read_and_polling_exclusion(self):
        code,data=self.get('model-reasoning?id='+self.job)
        self.assertEqual(code,200);self.assertIn('Published sentinel text',json.dumps(data))
        self.assertNotIn('Published sentinel text',json.dumps(self.get('state')[1]))
        with self.studio.db() as db:before=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        for _ in range(3):self.assertEqual(self.get('model-reasoning?id='+self.job)[0],200)
        with self.studio.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],before)
    def test_other_account_and_malformed_query(self):
        other=self.studio.session()[0]
        # Authentication can reject the second browser earlier (409), or ownership
        # rejects its mission (404). It must never return the trace.
        code,data=self.get('model-reasoning?id='+self.job,person=other)
        self.assertIn(code,(404,409));self.assertNotIn('Published sentinel text',json.dumps(data))
        self.assertEqual(self.get('model-reasoning?id='+self.job+'&id=another')[0],400)
        self.assertEqual(self.get('model-reasoning?id=unknown')[0],404)
    def test_deleted_job_cannot_be_read(self):
        with self.studio.db() as db:db.execute('DELETE FROM jobs WHERE id=?',(self.job,))
        self.assertEqual(self.get('model-reasoning?id='+self.job)[0],404)
        with self.studio.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM model_reasoning').fetchone()[0],0)

if __name__=='__main__':unittest.main()

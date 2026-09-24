"""Account-owned crew resources are independent of personal deletion."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from test_studio import Studio, Adapter, Problem
from serve import create_server


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=Adapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.person=self.studio.session()[0];self.owner=self.person['id']
        self.studio.onboard(self.owner,{'name':'Personal','skills':['weather']})

    def finish(self):
        while True:
            row=self.studio.next_job()
            if not row:return
            self.studio.execute(row)

    def test_hiring_and_deleting_twelve_agents_keeps_one_team_and_policy(self):
        team=self.studio.crew_owner(self.owner)
        self.studio.crew_policy_change(team,{'role':1,'permission':'host:blogs.nvidia.com','allow':False})
        owners=[self.owner]+[self.studio.add_agent(self.owner,{'name':'QA'+str(i),'skills':['weather'],'protection':'openshell' if i%2 else 'standard'})['agentId'] for i in range(11)]
        self.assertEqual({self.studio.crew_owner(o) for o in owners},{team})
        self.assertEqual(len(self.studio.state(self.owner)['agents']),12)
        with self.assertRaises(Problem):self.studio.add_agent(self.owner,{'name':'Overflow','skills':['weather']})
        self.finish()
        self.assertEqual(sum(1 for p in (self.studio.directory/'workspaces').iterdir() if p.name.endswith(('-0','-1','-2','-3'))),4)
        for owner in owners:
            self.assertFalse(list(self.studio.workspace(owner).parent.glob(owner+'-*')))
            with patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
                result=self.studio.delete_agent(owner,{'name':self.studio.profile(owner)['name']})
                self.assertEqual(remove.call_count,1)
        fresh=result['agentId']
        self.assertEqual(self.studio.resolve_agent(self.person['id']),fresh)
        self.assertEqual(self.studio.crew_owner(fresh),team)
        self.assertEqual(self.studio.crew_policy_report(team,1)['requested'],[])
        self.assertIn(self.studio.crew_native_id(team,1),self.adapter.agents)
        self.assertEqual(self.studio.state(fresh)['agents'],[])
        with self.assertRaises(Problem):self.studio.resolve_agent(self.person['id'],team)

    def test_explicit_team_resources_survive_personal_delete_and_restart(self):
        team=self.studio.crew_owner(self.owner)
        # Resource names are independently registered, not derived by traversing
        # a personal owner's children. Keep an existing native identity intact.
        resource=self.studio.crew_resources[(team,1)]
        old_path=self.studio.workspace(team,1)
        resource.update(native_id='bac-'+self.owner+'-r1',workspace_name=self.owner+'-1',chat_session='existing-dylan-session')
        old_path.rename(self.studio.directory/'workspaces'/resource['workspace_name'])
        with self.studio.db() as db:
            db.execute('UPDATE crew_resources SET native_id=:native_id,workspace_name=:workspace_name,chat_session=:chat_session WHERE owner=:owner AND role=:role',resource)
        job=self.studio.enqueue(team,{'kind':'crew','preset':True,'brief':{'schema':2}})['id']
        self.finish()
        before=self.studio.evidence(team,job)['mission']
        paths={p['path']:(self.studio.workspace(team)/p['path']).read_bytes() for p in self.studio.files(team) if p['kind']=='artifacts'}
        self.assertTrue(paths)
        self.studio.crew_policy_change(team,{'role':1,'permission':'host:blogs.nvidia.com','allow':False})
        native=self.studio.crew_native_id(team,1);native_path=self.adapter.agents[native]
        self.studio=Studio(self.temp.name,self.adapter,start_worker=False,recover=True)
        self.assertEqual(self.studio.workspace(team,1),native_path)
        self.assertEqual(self.studio.crew_native_id(team,1),native)
        self.assertEqual(self.studio.crew_chat_session(team,1),'existing-dylan-session')
        with patch.object(self.adapter,'remove',wraps=self.adapter.remove) as remove:
            fresh=self.studio.delete_agent(self.owner,{'name':'Personal'})['agentId']
            self.assertEqual(remove.call_count,1)
        self.assertEqual(self.studio.crew_policy_report(team,1)['requested'],[])
        self.assertTrue(native_path.exists())
        self.assertEqual(self.studio.survey_report(team,job)['total'],0)
        self.assertEqual(self.studio.evidence(team,job)['mission'],before)
        for relative,value in paths.items():self.assertEqual(self.studio.available_file(fresh,relative).read_bytes(),value)
        outsider=self.studio.session()[0]['id']
        with self.assertRaises(Problem):self.studio.job_owner(outsider,job)
        with self.assertRaises(Problem):self.studio.available_file(outsider,next(iter(paths)))

    def test_delete_only_stops_crew_when_personal_agent_is_an_actual_guest(self):
        team=self.studio.crew_owner(self.owner)
        job=self.studio.enqueue(team,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'guestKeys':[]})['id']
        self.studio.delete_agent(self.owner,{'name':'Personal'})
        self.assertEqual(self.studio.evidence(team,job)['mission']['status'],'queued')
        self.finish()
        self.assertEqual(self.studio.evidence(team,job)['mission']['status'],'done')
        fresh=self.studio.resolve_agent(self.person['id'])
        self.studio.onboard(fresh,{'name':'Guest','skills':['weather']})
        job=self.studio.enqueue(team,{'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2},'guestKeys':[fresh]})['id']
        self.studio.delete_agent(fresh,{'name':'Guest'})
        self.assertEqual(self.studio.evidence(team,job)['mission']['status'],'cancelled')

    def test_only_one_team_per_account_and_no_automatic_import(self):
        import sqlite3
        team=self.studio.crew_owner(self.owner)
        # Stray old directories cannot cause new teams to appear on startup.
        stray=self.studio.workspace(self.owner,0);stray.mkdir(parents=True)
        self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.assertEqual(self.studio.crew_owner(self.owner),team)
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0],1)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO crew_contexts VALUES (?,?)',('other',self.person['id']))
        self.assertFalse(hasattr(self.studio,'crew_aliases'))
        self.assertFalse(hasattr(self.studio,'migrate_legacy_crew'))

    def test_simultaneous_team_requests_cannot_create_duplicate_crews(self):
        from concurrent.futures import ThreadPoolExecutor
        owners=[self.owner]+[self.studio.add_agent(self.owner,{'name':'Concurrent'+str(i),'skills':['weather']})['agentId'] for i in range(11)]
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0],0)
        self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0],0)
        barrier=threading.Barrier(len(owners))
        def request(owner):
            barrier.wait(timeout=10)
            return self.studio.crew_owner(owner)
        with ThreadPoolExecutor(max_workers=len(owners)) as pool:
            teams=set(pool.map(request,owners))
        self.assertEqual(len(teams),1)
        team=teams.pop()
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0],1)
        for owner in owners:
            self.assertFalse(list((self.studio.directory/'workspaces').glob(owner+'-*')))
        for role in range(4):
            self.assertTrue((self.studio.workspace(team,role)/'SOUL.md').is_file())

    def test_reading_session_state_does_not_allocate_crew_resources(self):
        before=set((self.studio.directory/'workspaces').iterdir())
        for _ in range(3):
            other=self.studio.session()[0]['id']
            self.assertIsNone(self.studio.state(other)['crewOwner'])
            self.assertIsNone(self.studio.state(self.owner)['crewOwner'])
        with self.studio.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM crew_contexts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM crew_resources').fetchone()[0],0)
        self.assertEqual(set((self.studio.directory/'workspaces').iterdir()),before)
        team=self.studio.crew_owner(self.owner)
        self.assertEqual(self.studio.state(self.owner)['crewOwner'],team)

    def test_custom_crew_uses_shared_storage_with_explicit_personal_lead(self):
        team=self.studio.crew_owner(self.owner)
        job=self.studio.enqueue(team,{'kind':'crew','brief':{'schema':2}},lead=self.owner)['id']
        self.finish()
        mission=self.studio.evidence(team,job)['mission']
        self.assertEqual(mission['status'],'done')
        self.assertEqual(mission['payload']['roster'][0]['key'],self.owner)
        self.assertFalse(list(self.studio.workspace(self.owner).parent.glob(self.owner+'-*')))

    def test_http_uses_team_for_chat_preparation_policy_and_files_after_switch(self):
        server=create_server('127.0.0.1',0,self.studio)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        second=self.studio.add_agent(self.owner,{'name':'Other','skills':['weather']})['agentId']
        def request(path,data=None,owner=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            try:
                headers={'Cookie':'bac_session='+self.person['token'],'X-BaC-CSRF':self.person['csrf'],'X-BaC-Agent':owner or self.owner,'Content-Type':'application/json'}
                conn.request('POST' if data is not None else 'GET','/api/'+path,body=json.dumps(data) if data is not None else None,headers=headers)
                r=conn.getresponse();return r.status,json.loads(r.read())
            finally:conn.close()
        self.assertEqual(request('prepare-demo',{'background':True})[0],200)
        team=self.studio.crew_owner(self.owner)
        self.finish()
        self.assertEqual(request('state',owner=second)[1]['preparation']['status'],'done')
        self.assertEqual(request('crew-policy',{'role':1,'permission':'host:blogs.nvidia.com','allow':False})[0],200)
        self.assertEqual(request('crew-policy?role=1',owner=second)[1]['requested'],[])
        status,job=request('jobs',{'kind':'crew-chat','crewRole':0,'prompt':'Hello'})
        self.assertEqual(status,200);self.finish()
        self.assertEqual(request('evidence?id='+job['id'],owner=second)[0],200)
        self.assertEqual(len(request('state',owner=second)[1]['crewChats']),1)
        self.assertEqual(request('state',owner=team)[0],404)
        personal=request('jobs',{'prompt':'Private chat'})[1]['id'];self.finish()
        self.assertEqual(request('evidence?id='+personal,owner=second)[0],404)
        # Crew output must not resolve to a same-named personal file.
        path='artifacts/output.json'
        (self.studio.workspace(team)/path).write_text('{"team":true}')
        (self.studio.workspace(second)/path).write_text('{"team":false}')
        self.assertEqual(request('file?path='+path+'&job='+job['id'],owner=second)[1]['content'],'{"team":true}')
        self.studio.delete_agent(self.owner,{'name':'Personal'})
        self.assertEqual(request('state',owner=second)[1]['crewChats'][0]['id'],job['id'])
        self.assertEqual(request('bac-reset',{},owner=second)[0],200)
        self.assertEqual(request('state',owner=second)[1]['crewChats'],[])
        self.assertIsNotNone(self.studio.profile(second))

if __name__=='__main__':unittest.main()

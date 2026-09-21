"""Observed skill reads, turn isolation, and persistent chat handoff evidence."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from test_studio import Adapter, Studio
from telemetry import Reply
import agent_activity


class CustomSkillActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.workspace=self.root/'workspace'
        self.config={'agents':{'entries':{'ours':{'workspace':str(self.workspace),'skills':['bac-documents','bac-nvidia-webpage','weather'],'sandbox':{'mode':'off'}}}}}
        self.catalog={'bac-documents':'Document Q&A','bac-nvidia-webpage':'NVIDIA event page'}
        self.dbpath=self.root/'agents/ours/agent/openclaw-agent.sqlite';self.dbpath.parent.mkdir(parents=True)
        with sqlite3.connect(self.dbpath) as db:
            db.execute('create table session_windows(session_id text,session_key text)')
            db.execute('create table transcript_events(session_id text,seq integer,event_json text,created_at integer)')
            for session in ('current','other'):
                db.execute('insert into session_windows values(?,?)',(session,'agent:ours:openai-user:'+session))
        self.seq=0

    def call(self,identifier,path,tool='read',failed=False,at=2000,session='current',complete=True):
        events=[{'message':{'role':'assistant','content':[{'type':'toolCall','id':identifier,'name':tool,'arguments':{'path':path}}]}}]
        if complete:events.append({'message':{'role':'toolResult','toolCallId':identifier,'isError':failed}})
        with sqlite3.connect(self.dbpath) as db:
            for event in events:
                self.seq+=1;db.execute('insert into transcript_events values(?,?,?,?)',(session,self.seq,json.dumps(event),at))

    def activity(self):
        paths=agent_activity.custom_skill_paths(self.config,'ours',self.catalog)
        return agent_activity.collect(self.root,'ours','current',1,skill_paths=paths)

    def test_only_successful_equipped_custom_skill_reads_in_this_turn_are_marked(self):
        self.call('relative','./skills/bac-documents/SKILL.md')
        self.call('absolute',str(self.workspace/'skills/bac-nvidia-webpage/SKILL.md'))
        self.call('failed','skills/bac-documents/SKILL.md',failed=True)
        self.call('pending','skills/bac-documents/SKILL.md',complete=False)
        self.call('builtin','skills/weather/SKILL.md')
        self.call('unequipped','skills/bac-weather/SKILL.md')
        self.call('foreign','/another-agent/skills/bac-documents/SKILL.md')
        self.call('written','skills/bac-documents/SKILL.md',tool='write')
        self.call('mention','inbox/bac-documents.txt')
        self.call('prior-turn','skills/bac-documents/SKILL.md',at=500)
        self.call('other-session','skills/bac-documents/SKILL.md',session='other')
        calls=self.activity()['calls']
        self.assertEqual({c['id']:c['customSkill']['label'] for c in calls if 'customSkill' in c},
                         {'relative':'Document Q&A','absolute':'NVIDIA event page'})
        self.assertNotIn('prior-turn',[c['id'] for c in calls]);self.assertNotIn('other-session',[c['id'] for c in calls])

    def test_openshell_uses_configured_workspace_without_marking_host_agent_paths(self):
        entry=self.config['agents']['entries']['ours'];entry['sandbox']={'mode':'all','backend':'openshell'}
        self.config['plugins']={'entries':{'openshell':{'config':{'remoteWorkspaceDir':'/sandbox/workspace'}}}}
        self.call('remote','/sandbox/workspace/skills/bac-documents/SKILL.md')
        self.call('wrong-root','/sandbox/skills/bac-documents/SKILL.md')
        self.assertEqual([c['id'] for c in self.activity()['calls'] if 'customSkill' in c],['remote'])
        entry['sandbox']={'mode':'off'}
        self.assertFalse(any('customSkill' in c for c in self.activity()['calls']))

    def test_lounge_and_crew_replies_preserve_evidence_across_restart(self):
        self.call('loaded','skills/bac-documents/SKILL.md');activity=self.activity()
        adapter=Adapter();studio=Studio(self.root/'studio',adapter,start_worker=False)
        owner=studio.session()[0]['id'];studio.onboard(owner,{'name':'Scout','persona':'analyst','skills':['documents']})
        def answer(*args):
            reply=Reply('Summary with a supporting source.',{});reply.activity=activity;return reply
        with patch.object(adapter,'respond',side_effect=answer):
            for request in ({'kind':'chat','prompt':'Summarize my document'},
                            {'kind':'crew-chat','crewRole':0,'prompt':'Review this brief'}):
                studio.enqueue(owner,request);studio.execute(studio.next_job())
        restarted=Studio(self.root/'studio',adapter,start_worker=False)
        state=restarted.state(owner)
        self.assertEqual(state['jobs'][0]['result']['activity'],activity)
        self.assertEqual(state['crewChats'][0]['result']['activity'],activity)
        other=restarted.session()[0]['id'];self.assertEqual(restarted.state(other)['jobs'],[])


if __name__=='__main__':unittest.main()

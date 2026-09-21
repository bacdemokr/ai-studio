import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from fixture_studio import BrowserAdapter
from event_planner import plan
from event_insights import insights
from crew_roundtable import reaction_context, reaction_prompt


class ReviewAdapter(BrowserAdapter):
    def __init__(self):
        super().__init__()
        self.prompts = {}; self.started = {}; self.finished = {}; self.lock = threading.Lock()
        self.active = 0; self.maximum = 0; self.fail = ''; self.before_review = None

    def respond(self, agent, session, prompt):
        with self.lock:
            self.active += 1; self.maximum = max(self.active, self.maximum)
            self.prompts[agent] = prompt; self.started[agent] = time.time()
        try:
            if 'bac-roundtable-' in session:
                if self.before_review: self.before_review(agent)
                if agent == self.fail: raise RuntimeError('Fixture failure')
                time.sleep(.02)
                name = self.profiles[agent]['name']
                return name+': One visit per attendee is focused. Check the 15-minute transition before calling this ready.'
            if agent.endswith('-r1'):
                return json.dumps({'demos':[{'topic':'agents','title':'Evidence, not magic','action':'Ask for a fact','outcome':'Read the cited source','why':'A source lets the visitor check the answer.','proof':'Open the cited passage.','risk':'Network access is untested.','presenterExpertise':'OpenClaw'}]})
            if agent.endswith('-r2'):
                return json.dumps({'summary':'One visit per attendee, not a full tour.','tradeoff':'Short visits keep the rota within the booth limit.','check':'Verify presenter relief.'})
            if agent.endswith('-r3'):
                return json.dumps({'subject':'A source you can check','body':'Try Evidence, not magic. Date and venue TBC.'})
            return 'Dylan and Alex work in parallel; Morgan receives both.'
        finally:
            with self.lock:
                self.active -= 1; self.finished[agent] = time.time()


class RoundtableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.adapter = ReviewAdapter(); self.studio = Studio(self.tmp.name, self.adapter, start_worker=False)
        self.person = self.studio.session()[0]; self.owner = self.person['id']

    def hire(self, count):
        keys = []
        for i in range(count):
            data = dict(name='Guest '+str(i), persona='analyst', skills=['documents'], purpose='Find evidence in documents.', tone='cynical' if i%2 else 'kind', tonePrompt='Dry humor & skepticism' if i%2 else 'Warm and practical', avatar={'body':'fox' if i%2 else 'round','color':'violet' if i%2 else 'cyan','accessory':'glasses'})
            if not i:
                self.studio.onboard(self.owner, data); keys.append(self.owner)
            else:
                keys.append(self.studio.add_agent(self.person['id'], data)['agentId'])
        return keys

    def queue(self):
        return self.studio.enqueue(self.owner, {'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})

    def execute(self):
        self.studio.execute(self.studio.next_job())
        return self.studio.state(self.owner)['jobs'][0]

    def test_all_hired_identities_react_after_deliverables_with_own_voice(self):
        keys = self.hire(7); self.queue(); job = self.execute(); p = job['payload']; meeting=p['roundtable']
        self.assertEqual(job['status'],'done'); self.assertEqual(meeting['status'],'done')
        self.assertEqual([m['key'] for m in meeting['members']],keys)
        self.assertEqual(set(meeting['replies']),set(keys)); self.assertLessEqual(self.adapter.maximum,2)
        marketing = p['roster'][3]['id']
        for index,key in enumerate(keys):
            agent = 'bac-'+key
            self.assertGreaterEqual(self.adapter.started[agent], self.adapter.finished[marketing])
            self.assertIn('Evidence, not magic', self.adapter.prompts[agent])
            self.assertIn('Dry humor & skepticism' if index%2 else 'Warm and practical', self.adapter.prompts[agent])
            self.assertIn('Guest '+str(index), meeting['replies'][key]['answer'])
            turns = self.studio.state(key)['roundtableTurns']; self.assertEqual(len(turns),1)
            self.assertIn('Guest '+str(index),turns[0]['result']['answer'])
        page=(self.studio.workspace(self.owner)/p['website']['path']).read_text()
        for text in ('The decisions behind this plan','What would prove it worked','Verify presenter relief.','Guest 6','Your agents’ take'):
            self.assertIn(text,page)
        self.assertEqual(len(self.adapter.prompts),4+len(keys))
        restarted=Studio(self.tmp.name,self.adapter,start_worker=False)
        self.assertEqual(restarted.state(keys[-1])['roundtableTurns'][0]['result']['answer'],meeting['replies'][keys[-1]]['answer'])

    def test_reactions_keep_distinct_interests_and_literal_custom_voices(self):
        profiles = [
            dict(name='Cloud', persona='analyst', skills=['weather'], purpose='Weather and comfortable outdoor plans.', tone='kind', tonePrompt='Cynical. Complain fondly about umbrellas.'),
            dict(name='Muse', persona='maker', skills=['writer'], purpose='Poetry, rhythm and unexpected metaphors.', tone='cynical', tonePrompt='Gentle and dreamy. Never sarcastic.'),
            dict(name='Scout', persona='analyst', skills=['web'], purpose='Find and compare research papers.', tone='direct', tonePrompt='Quiet, curious and precise.'),
        ]
        keys=[]
        for profile in profiles:
            if not keys:
                self.studio.onboard(self.owner, profile);keys.append(self.owner)
            else:
                keys.append(self.studio.add_agent(self.person['id'], profile)['agentId'])
        self.queue();job=self.execute()
        for profile,key in zip(profiles,keys):
            prompt=self.adapter.prompts['bac-'+key]
            self.assertIn('Interests and role: '+profile['purpose'],prompt)
            self.assertIn('Your exact voice: '+profile['tonePrompt'],prompt)
            for other in profiles:
                if other is not profile:self.assertNotIn(other['tonePrompt'],prompt)
            self.assertIn('not as an event reviewer',prompt)
            self.assertIn('at most 75 words total' if 'writer' in profile['skills'] else '1–2 short sentences, at most 55 words',prompt)
            self.assertNotIn('ONE specific concern or improvement',prompt)
            self.assertNotIn('Mention a concrete supplied detail',prompt)
            self.assertIn('Hopes and hypothetical conditions are fine',prompt)
            self.assertIn('Do not invent a forecast',prompt)
            self.assertEqual(job['payload']['roundtable']['replies'][key]['status'],'done')
        self.assertEqual(len(self.adapter.prompts),4+len(keys))

    def test_guests_take_turns_with_completed_peer_comments(self):
        keys = self.hire(3)
        self.queue(); job = self.execute()
        for index, key in enumerate(keys):
            prompt = self.adapter.prompts['bac-' + key]
            for earlier in keys[:index]:
                reply = job['payload']['roundtable']['replies'][earlier]['answer']
                self.assertIn(reply, prompt)
                self.assertGreaterEqual(self.adapter.started['bac-' + key], self.adapter.finished['bac-' + earlier])
            for later in keys[index + 1:]:
                self.assertNotIn(job['payload']['roundtable']['replies'][later]['answer'], prompt)
            self.assertNotIn('Optional personal angle:', prompt)

    def test_context_keeps_every_experience_without_repeating_review_criteria(self):
        payload = {'brief': {'city': 'Zurich', 'venue': 'StageOne', 'startDate': '2026-10-01'},
            'capacity': {'session': 15, 'boothCount': 3, 'staff': 6, 'topics': [
                {'topic': title, 'demo': title + ' demo', 'action': 'Try ' + title,
                 'outcome': 'Take home ' + title, 'risk': 'Prepared material only',
                 'proof': 'Inspect the log timestamp', 'why': 'Assess evidence quality'}
                for title in ('Documents', 'Agent teams', 'Robots')]},
            'decisionNotes': {'check': 'Inspect the log timestamp again'},
            'campaign': {'body': 'Inspect the log timestamp a third time'}}
        context = json.loads(reaction_context(payload))
        self.assertEqual([x['topic'] for x in context['experiences']], ['Documents', 'Agent teams', 'Robots'])
        self.assertEqual(context['event']['venue'], 'StageOne')
        self.assertTrue(all(x['risk'] == 'Prepared material only' for x in context['experiences']))
        self.assertNotIn('timestamp', json.dumps(context))

    def test_shared_specialty_and_custom_voice_are_not_replaced_by_seat_order(self):
        member = dict(name='Cloud', purpose='Weather and outdoor comfort.', skills=['weather'],
                      tone='cynical', tonePrompt='Soft and dreamy, never sarcastic.', reactionAngle='Review a robot booth')
        earlier = [{'name':'Rain', 'comment':'I hope the walk stays dry.'}]
        prompt = reaction_prompt(member, 'English', '{}', earlier)
        self.assertIn('Weather and outdoor comfort.', prompt)
        self.assertIn('Soft and dreamy, never sarcastic.', prompt)
        self.assertIn('I hope the walk stays dry.', prompt)
        self.assertNotIn('Review a robot booth', prompt)
        self.assertNotIn('a dry quip', prompt)
        self.assertIn('Keep that specialty', prompt)

    def test_failed_reaction_does_not_discard_package_or_other_guests(self):
        keys=self.hire(3);self.adapter.fail='bac-'+keys[1];self.queue()
        with self.assertLogs(level='ERROR'):job=self.execute()
        self.assertEqual(job['status'],'done')
        replies=job['payload']['roundtable']['replies']
        self.assertEqual([replies[k]['status'] for k in keys],['done','error','done'])
        self.assertNotIn('answer',replies[keys[1]])
        self.assertIn(replies[keys[0]]['answer'], self.adapter.prompts['bac-' + keys[2]])
        self.assertTrue((self.studio.workspace(self.owner)/job['payload']['website']['path']).exists())

    def test_retry_gets_completed_comments_without_regenerating_other_guests(self):
        keys = self.hire(3); self.adapter.fail = 'bac-' + keys[1]; self.queue()
        with self.assertLogs(level='ERROR'): job = self.execute()
        started = dict(self.adapter.started)
        self.adapter.fail = ''
        self.studio.retry_reaction(self.owner, {'id':job['id'], 'member':keys[1]})
        retried = self.execute()
        replies = retried['payload']['roundtable']['replies']
        self.assertEqual(replies[keys[1]]['status'], 'done')
        self.assertEqual(replies[keys[1]]['attempt'], 2)
        for key in (keys[0], keys[2]):
            self.assertEqual(self.adapter.started['bac-' + key], started['bac-' + key])
            self.assertIn(replies[key]['answer'], self.adapter.prompts['bac-' + keys[1]])

    def test_members_are_frozen_fenced_and_scoped(self):
        keys=self.hire(2);other=self.studio.session()[0]
        self.studio.onboard(other['id'],dict(name='Other attendee',persona='guide',skills=['writer']))
        self.queue()
        with self.studio.db() as db:
            with self.assertRaises(Problem):self.studio.require_idle(db,keys[1])
        with self.assertRaises(Problem):self.studio.configure(keys[1],dict(name='Changed guest',persona='guide',skills=['writer']))
        late=self.studio.add_agent(self.person['id'],dict(name='Late guest',persona='guide',skills=['writer']))
        job=self.execute()
        self.assertEqual([m['key'] for m in job['payload']['roundtable']['members']],keys)
        self.assertEqual(self.studio.state(other['id'])['roundtableTurns'],[])
        self.assertEqual(self.studio.state(late['agentId'])['roundtableTurns'],[])

    def test_stop_during_roundtable_preserves_completed_package(self):
        self.hire(5);queued=self.queue()
        def stop(agent):self.studio.decision(self.owner,queued['id'],'cancel')
        self.adapter.before_review=stop
        job=self.execute()
        self.assertEqual(job['status'],'cancelled')
        self.assertEqual(len(job['payload']['roundtable']['replies']),1)
        self.assertTrue((self.studio.workspace(self.owner)/job['payload']['website']['path']).exists())

    def test_no_hired_agents_needs_no_extra_model_calls(self):
        self.queue();job=self.execute()
        self.assertEqual(job['status'],'done');self.assertEqual(len(self.adapter.prompts),4)

    def test_protection_failure_does_not_invoke_guest_or_drop_other_reactions(self):
        keys=self.hire(2);self.queue()
        original=self.studio.check_protected_run
        def check(key, profile):
            if key == keys[0]:
                from studio_policy import ProtectionNotVerified
                raise ProtectionNotVerified('unavailable')
            return original(key, profile)
        self.studio.check_protected_run=check
        with self.assertLogs(level='ERROR'):job=self.execute()
        self.assertEqual(job['status'],'done')
        self.assertNotIn('bac-'+keys[0],self.adapter.prompts)
        self.assertEqual(job['payload']['roundtable']['replies'][keys[0]]['status'],'error')
        self.assertIn('OpenShell protection could not be verified',job['payload']['roundtable']['replies'][keys[0]]['error'])
        self.assertEqual(job['payload']['roundtable']['replies'][keys[1]]['status'],'done')

    def test_full_collection_has_no_fixed_guest_count_limit(self):
        keys=self.hire(12);self.queue();job=self.execute()
        self.assertEqual(set(job['payload']['roundtable']['replies']),set(keys))
        self.assertTrue(all(r['status']=='done' for r in job['payload']['roundtable']['replies'].values()))

    def test_calculated_insights_escape_inputs_and_handle_capacity_limit(self):
        b,c=plan({'schema':2,'city':'<script>alert(1)</script>','attendees':180,'duration':30,'session':5,'boothLimit':6})
        rendered=insights(b,c,{'check':'<script>bad</script>'})
        self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
        self.assertIn('cannot fit',rendered)

if __name__=='__main__':unittest.main()

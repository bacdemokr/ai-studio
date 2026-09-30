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


    def test_calculated_insights_escape_inputs_and_handle_capacity_limit(self):
        b,c=plan({'schema':2,'city':'<script>alert(1)</script>','attendees':180,'duration':30,'session':5,'boothLimit':6})
        rendered=insights(b,c,{'check':'<script>bad</script>'})
        self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
        self.assertIn('cannot fit',rendered)

if __name__=='__main__':unittest.main()

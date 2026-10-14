import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parent)]
from studio import Studio, Problem
from crew_roundtable import reaction_context, reaction_prompt




class RoundtableTests(unittest.TestCase):





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



if __name__=='__main__':unittest.main()

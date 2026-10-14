import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from agent_runtime import collaboration_capabilities
from protection_activity import ProtectionActivity
from studio_policy import PolicyControls
from telemetry import Reply


class ProtectedTeamFeedbackTests(unittest.TestCase):
    def run_reply(self, evidence=(), structured=False):
        app = PolicyControls()
        app.profile = lambda owner: {'protection': 'openshell'}
        app.remember_policy_denials = lambda *args: None
        app.protection_activity = ProtectionActivity()
        original = Reply('HTTP 403; no source contents verified.', {'input': 31})
        original.sources = [{'url': 'https://allowed.example.org', 'text': 'Observed excerpt'}]
        original.activity = {'toolCount': 1}

        def respond(*args, **kwargs):
            now = time.time()
            for owner, role, action, reason, offset in evidence:
                app.protection_activity.observe(owner, role, owner, [dict(
                    host='example.com', action=action, reason=reason, time=now+offset,
                    fingerprint=str((owner, role, action, reason, offset)))], now-100)
            return original

        app.adapter = SimpleNamespace(respond=respond, policy_events=lambda agent: [])
        return app.protected_response('bac-personal', 'test', 'Read a page', 'owner',
                                      json_response=structured), original

    def test_verified_current_personal_denial_is_shared_without_losing_telemetry(self):
        answer, original = self.run_reply([('owner', None, 'deny', 'policy-denied', 0)])
        self.assertIn('OpenShell blocked: example.com.', answer)
        self.assertIn('this agent', answer)
        self.assertEqual(answer.policy_denials, ['example.com'])
        for attribute in ('metrics', 'sources', 'activity'):
            self.assertEqual(getattr(answer, attribute), getattr(original, attribute))

    def test_errors_other_agents_crew_old_denials_and_allows_are_not_relabelled(self):
        for evidence in ([], [('other', None, 'deny', 'policy-denied', 0)],
                         [('owner', 1, 'deny', 'policy-denied', 0)],
                         [('owner', None, 'deny', 'policy-denied', -10)],
                         [('owner', None, 'deny', 'dns-failed', 0)],
                         [('owner', None, 'allow', None, 0)]):
            with self.subTest(evidence=evidence):
                answer, original = self.run_reply(evidence)
                self.assertIs(answer, original)

    def test_structured_response_contract_is_unchanged(self):
        answer, original = self.run_reply([('owner', None, 'deny', 'policy-denied', 0)], True)
        self.assertIs(answer, original)

    def test_current_turn_evidence_outlives_visual_and_is_removed_on_reset(self):
        activity = ProtectionActivity()
        now = time.time()
        activity.observe('owner', None, 'native', [dict(host='example.com', action='deny',
                         reason='destination-blocked', time=now)], now)
        with patch('protection_activity.time.time', return_value=now+40):
            self.assertEqual(activity.snapshot({'owner'}, 'owner'), [])
            self.assertEqual(activity.denials_since('owner', None, now), ['example.com'])
        activity.forget('owner')
        self.assertEqual(activity.denials_since('owner', None, now), [])

    def test_protected_capabilities_describe_sandbox_route_without_exposing_host_tools(self):
        for skills in (['web'], ['weather'], ['builder']):
            caps = collaboration_capabilities({'skills': skills, 'protection': 'openshell'})
            self.assertNotIn('web_fetch', caps['tools'])
            self.assertNotIn('web_search', caps['tools'])
            self.assertIn('exec', caps['tools'])
            self.assertIn('explicit policy approval', ' '.join(caps['limits']))
        standard = collaboration_capabilities({'skills': ['builder'], 'protection': 'standard'})
        self.assertNotIn('exec', standard['tools'])
        self.assertNotIn('OpenShell public reads', ' '.join(standard['limits']))

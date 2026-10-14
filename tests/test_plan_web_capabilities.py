import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent_runtime as runtime
from studio import CREW_CATALOG
import test_collaboration_plan as fixture


class PlanWebCapabilities(unittest.TestCase):
    setUp = fixture.CollaborationTests.setUp
    start = fixture.CollaborationTests.start

    def test_planner_receives_specialist_tools_without_search_account(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'root', return_value=Path(directory)):
            self.start('/plan Research AMD and build a webpage.')
            self.app.execute(self.app.next_job())
        prompt = self.adapter.calls[0][2]
        pool = json.JSONDecoder().raw_decode(prompt.split('available pool to match the current request: ', 1)[1])[0]
        members = {member['name']: member for member in pool}
        self.assertIn('web_fetch', members['Scout']['tools'])
        self.assertNotIn('web_search', members['Scout']['tools'])
        self.assertNotIn('web_fetch', members['Cody']['tools'])
        self.assertIn('write', members['Cody']['tools'])
        self.assertNotIn('Dylan', members)
        self.assertIn('not for your Captain session', prompt)
        self.assertIn('research brief alone does not satisfy a requested working webpage', prompt)

    def test_optional_search_and_openshell_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'root', return_value=Path(directory)):
            researcher = CREW_CATALOG[8]
            self.assertIn('web_fetch', runtime.tool_allowlist(researcher, researcher['role']))
            Path(directory, 'search-enabled').touch()
            self.assertIn('web_search', runtime.tool_allowlist(researcher, researcher['role']))
            protected = {**researcher, 'protection': 'openshell'}
            tools = runtime.tool_allowlist(protected, researcher['role'])
            self.assertNotIn('web_fetch', tools)
            self.assertNotIn('web_search', tools)
            self.assertIn('exec', tools)
            self.assertNotIn('web_fetch', runtime.tool_allowlist(CREW_CATALOG[0], CREW_CATALOG[0]['role']))

    def test_keyless_search_does_not_depend_on_legacy_secret_marker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime,'root',return_value=Path(directory)):
            config=runtime.initial_config()
            config['tools']['web']={'search':{'enabled':True,'provider':'parallel-free'}}
            config['plugins']['entries']['parallel']={'enabled':True}
            runtime.save_config(config)
            self.assertTrue(runtime.search_enabled())
            config['tools']['web']['search']['enabled']=False
            runtime.save_config(config)
            self.assertFalse(runtime.search_enabled())

    def test_captain_and_scout_share_single_search_handoff_contract(self):
        self.start('/plan Research the latest NVIDIA developments and build a webpage.')
        self.app.execute(self.app.next_job())
        captain=self.adapter.calls[0][2]
        scout=next(prompt for agent,session,prompt in self.adapter.calls if agent.endswith('-r8'))
        self.assertIn('finish without follow-up searches or page reads',captain)
        self.assertIn('Current UTC date:',scout)
        self.assertIn('Immediately write the assigned brief with native write',scout)
        self.assertIn('Do not run a follow-up search or open result pages',scout)
        self.assertIn('attributed search excerpts are sufficient evidence',scout)
        self.assertIn('One relevant supported finding is acceptable',scout)
        self.assertNotIn('search snippets and home-page navigation are not evidence',scout)
        self.assertNotIn('then read the relevant result pages',scout)
        self.assertIn('Current agent access: OpenShell is off',scout)
        self.assertIn('search service reports a rate limit or unavailable service',scout)
        self.assertIn('within the five-fetch budget',scout)
        self.assertIn('openShellEnabled and confirmedPolicyDenial',captain)

    def test_scout_stops_after_required_evidence_and_single_save(self):
        self.start('/plan Research the key NVIDIA developments and save an evidence brief.')
        self.app.execute(self.app.next_job())
        captain=self.adapter.calls[0][2]
        scout=next(prompt for agent,session,prompt in self.adapter.calls if agent.endswith('-r8'))
        self.assertIn('Do not add multiple sources, extra topics',captain)
        self.assertIn('SCOUT FINISH RULE',scout)
        self.assertIn('If no required fact is missing, stop browsing immediately',scout)
        self.assertIn('After successful write, do not read the brief back',scout)
        self.assertIn('dates and timestamps while gathering the evidence, BEFORE saving',scout)
        self.assertIn('user’s requested scope is supported',scout)
        self.assertIn('never search again only',scout.lower())

    def test_captain_receives_actual_access_when_scout_misreports_policy(self):
        from telemetry import Reply
        respond=self.adapter.respond
        def observed(agent,session,prompt,**kwargs):
            answer=respond(agent,session,prompt,**kwargs)
            if agent.endswith('-r8'):
                answer=Reply('OpenShell blocked the source.',{})
                answer.activity={'calls':[{'tool':'web_search','status':'failed','failureReason':'search-rate-limit'}]}
            return answer
        self.adapter.respond=observed
        self.start('/plan Research NVIDIA and analyze the findings.')
        self.app.execute(self.app.next_job())
        checks=[prompt for agent,session,prompt in self.adapter.calls if agent.endswith('-r0') and 'observedAccess' in prompt and 'Search service rate limit' in prompt]
        self.assertTrue(checks)
        self.assertIn('"openShellEnabled": false',checks[0])
        self.assertIn('"confirmedPolicyDenial": false',checks[0])

    def test_research_handoff_disables_edit_but_keeps_input_reads(self):
        researcher={**CREW_CATALOG[8],'_researchBrief':True}
        tools=runtime.tool_allowlist(researcher,researcher['role'])
        self.assertIn('read',tools);self.assertIn('write',tools);self.assertIn('web_fetch',tools)
        self.assertNotIn('edit',tools)
        ordinary=runtime.tool_allowlist(CREW_CATALOG[5],CREW_CATALOG[5]['role'])
        self.assertIn('edit',ordinary)

    def test_existing_scout_switches_to_research_brief_tools(self):
        member={**CREW_CATALOG[8], 'id':'test-scout'}
        with patch.object(self.adapter,'register',wraps=self.adapter.register) as register:
            self.app.prepare_builtin_crew(self.owner,8,dict(member))
            self.app.prepare_builtin_crew(self.owner,8,{**member,'_researchBrief':True})
            self.assertEqual(register.call_count,2)
            profile=register.call_args.args[2]
            self.assertNotIn('edit',runtime.tool_allowlist(profile,profile['role']))
            self.app.prepare_builtin_crew(self.owner,8,{**member,'_researchBrief':True})
            self.assertEqual(register.call_count,2)
            self.app.prepare_builtin_crew(self.owner,8,dict(member))
            self.assertEqual(register.call_count,3)
            profile=register.call_args.args[2]
            self.assertIn('edit',runtime.tool_allowlist(profile,profile['role']))

    def test_research_skill_keeps_evidence_budgets_and_distinguishes_chat_from_handoff(self):
        instruction = runtime.SKILLS['web'][1]
        self.assertIn('Read a supplied URL first', instruction)
        self.assertIn('one focused query with at most three results', instruction)
        self.assertIn('For a research question in ordinary conversation, answer briefly with citations', instruction)
        self.assertIn('without browsing or writing files', instruction)
        self.assertIn('two searches and five page fetch attempts', instruction)
        self.assertIn('two searches OR five direct fetch attempts', instruction)
        self.assertIn('For a handoff, use the assigned path and available file tools', instruction)
        self.assertIn('Do not reread or rewrite a successful brief', instruction)
        self.assertIn('never claim research succeeded', instruction)
        self.assertIn('check article dates and reporting periods', instruction)
        self.assertIn('start with a confidently known topic-specific newsroom', instruction)
        self.assertIn('Cite exact URLs successfully read', instruction)
        self.assertIn('A policy denial is not permission to try another route', instruction)
        self.assertNotIn('otherwise ask for a source URL', instruction)


if __name__ == '__main__':
    unittest.main()

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

    def test_research_skill_attempts_official_sources_before_asking_for_urls(self):
        instruction = runtime.SKILLS['web'][1]
        self.assertIn('start with a confidently known official homepage', instruction)
        self.assertIn('Cite exact URLs successfully read', instruction)
        self.assertIn('A policy denial is not permission to try another route', instruction)
        self.assertNotIn('otherwise ask for a source URL', instruction)


if __name__ == '__main__':
    unittest.main()

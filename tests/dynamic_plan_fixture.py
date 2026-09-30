"""Disposable browser fixture. Never imports the real runtime adapter."""
import json
import os
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_collaboration_plan import PlanAdapter
from studio import Studio
from serve import create_server


class DynamicAdapter(PlanAdapter):
    def status(self):
        return {'ready': True, 'gateway': True, 'model': True, 'testFixture': True}

    def respond(self, agent, session, prompt, **kwargs):
        time.sleep(.4)
        task=prompt.split('Current user task:')[-1]
        if session.endswith('-planning'):
            order = [2, 5, 4] if 'CALCULATOR_QA' in prompt.split('Current user task:')[-1] else [6, 7, 5] if 'DATA_UI_QA' in prompt.split('Current user task:')[-1] else [8, 4] if 'RESEARCH_QA' in prompt.split('Current user task:')[-1] else [3, 4]
            if 'EARLY_QA' in task: order=[8,3,4]
            if 'PARTIAL_QA' in task: order=[6,5,4]
            if 'ASSEMBLY_QA' in task: order=[8,5,4]
            if 'SINGLE_QA' in task: order=[3]
            if 'SOLO_QA' in task or 'UNSUPPORTED_QA' in task: order=[]
            self.plan = {'summary': 'Choose expertise for this request.', 'tasks': [
                {'role': role, 'expected': 'Deliver a usable calculator with clear controls.' if role==5 else 'Provide a concise, source-grounded contribution with limitations.', 'task': {2: 'Define requirements.', 5: 'Implement calculator.', 3: 'Draft clear copy.', 4: 'Inspect the supplied work.', 6: 'Interpret the provided table.', 7: 'Design the comparison screen.', 8: 'Research public sources and cite findings.'}[role]}
                for role in order]}
            if not order:
                unsupported='UNSUPPORTED_QA' in task
                self.plan.update(outcome='unavailable' if unsupported else 'complete',answer='No deployment tool is available.' if unsupported else 'A short direct answer.',summary='No deployment specialist is available.' if unsupported else 'I can answer this directly; no additional agents are needed.')
        if 'ASSEMBLY_QA' in task and agent.endswith('-r8') and session.endswith('-working'):
            time.sleep(18)  # Observe all planned members seated while only Avery is running.
        answer = super().respond(agent, session, prompt, **kwargs)
        if '-checking-' in session and 'EARLY_QA' in task:
            return json.dumps({'done':True,'reason':'The research answers the request; no additional agents are needed.','answer':'Here are the complete research findings.'})
        if session.endswith('-reviewing') and 'PARTIAL_QA' in task:
            return json.dumps({'done':True,'outcome':'partial','reason':'The local prototype is ready, but deployment is unavailable.',
                               'answer':'Preview the local prototype. It has not been deployed.', 'remaining':['Public deployment']})
        if agent.endswith('-r5') and session.endswith('-working'):
            (self.agents[agent] / 'artifacts/calculator.html').write_text('<html><body><h1>Calculator QA</h1></body></html>')
        return answer


if __name__ == '__main__':
    studio = Studio(os.environ['BAC_DATA_DIR'], DynamicAdapter())
    create_server('127.0.0.1', int(os.environ.get('TEST_PORT', 8098)), studio).serve_forever()

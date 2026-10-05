"""Disposable Stage 3 browser fixture. No real model, key or user data.

Run python3 -B tests/fixture_scenarios.py, then tests/stage-scenarios.cjs.
"""
import sys,tempfile,copy
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'tests'),str(root/'scripts')]
from test_stage_scenarios import AgentToolsAdapter,SOURCES
from studio import Studio
from serve import create_server
class Fixture(AgentToolsAdapter):
 def status(self):return {'ready':True,'gateway':True,'model':True,'testFixture':True,'version':'TEST FIXTURE','openshell':'fixture'}
 def respond(self,agent,session,prompt):
  if 'Your role for this mission:' not in prompt and not prompt.startswith('LINKEDIN-FIRST:') and 'actual brief in your final response' not in prompt:
   return 'Fixture reply: '+('event hello' if 'event hello' in prompt else 'plan hello')
  return super().respond(agent,session,prompt)
with tempfile.TemporaryDirectory(prefix='bac-scenarios-ui-') as folder,patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])),patch('event_agent_tools.read_article',return_value='Fixture article read by the agent tool.'):
 app=Studio(folder,Fixture());server=create_server('127.0.0.1',8083,app)
 print('Scenario fixture 8083',flush=True)
 try:server.serve_forever()
 finally:app.stop.set();server.server_close()

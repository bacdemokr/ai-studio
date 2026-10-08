"""Disposable Stage 3 browser fixture. No real model, key or user data.

Run python3 -B tests/fixture_scenarios.py, then node tests/stage-scenarios.cjs
and node tests/scenario-isolation-browser.cjs (requires Playwright and Chrome).
"""
import sys,tempfile,copy,os,time
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'tests'),str(root/'scripts')]
from test_stage_scenarios import AgentToolsAdapter,SOURCES
from dynamic_plan_fixture import DynamicAdapter
from studio import Studio
from serve import create_server
class Fixture(AgentToolsAdapter):
 def __init__(self):
  super().__init__();self.plan_adapter=DynamicAdapter()
  self.plan_adapter.agents=self.agents;self.plan_adapter.profiles=self.profiles
 def status(self):return {**self.plan_adapter.status(),'testFixture':False,'version':'SCENARIO TEST FIXTURE','openshell':'fixture'}
 def respond(self,agent,session,prompt,**kwargs):
  if session.startswith('bac-plan-'):return self.plan_adapter.respond(agent,session,prompt,**kwargs)
  if '[fixture:slow]' in prompt:time.sleep(4)
  if '[fixture:error]' in prompt:raise RuntimeError('TEST FIXTURE: model unavailable')
  if 'Your role for this mission:' not in prompt and not prompt.startswith('LINKEDIN-FIRST:') and 'actual brief in your final response' not in prompt:
   return 'Fixture reply: '+('event hello' if 'event hello' in prompt else 'plan hello')
  return super().respond(agent,session,prompt)
with tempfile.TemporaryDirectory(prefix='bac-scenarios-ui-') as folder,patch.dict(os.environ,{'BAC_DATA_DIR':folder}),patch('nvidia_research.search_one',return_value=copy.deepcopy(SOURCES['sources'])),patch('event_agent_tools.read_article',return_value='Fixture article read by the agent tool.'),patch('runtime_settings.request',return_value={'data':[{'id':m} for m in ('fixture-local-model','fixture-other-model','nvidia/nvidia/nemotron-3-ultra-nvfp4','nvidia/nvidia/nemotron-3.5-lightning')]}):
 app=Studio(folder,Fixture());server=create_server('127.0.0.1',8083,app)
 print('Scenario fixture 8083',flush=True)
 try:server.serve_forever()
 finally:app.stop.set();server.server_close()

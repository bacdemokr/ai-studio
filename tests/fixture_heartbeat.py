"""Browser fixture only: no external Telegram or LLM calls."""
import os
from pathlib import Path
import sys
import tempfile
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
from fixture_studio import BrowserAdapter
from studio import Studio
from serve import create_server
import runtime_settings as settings
import telegram_notifications
import tech_radar
import time
from radar_fixture_data import sample

class Adapter(BrowserAdapter):
    def status(self):return {**super().status(),'event':settings.event(),'location':settings.location(),'installed':False}
    def policy_events(self,agent):return self.policy_logs.get(agent,[])
    def set_radar_heartbeat(self,agent,enabled):
        if enabled and agent in self.agents and agent not in getattr(self,'published',set()):
            self.published=getattr(self,'published',set())|{agent}
            root=self.agents[agent];now=time.time()
            if os.environ.get('BAC_TEST_RADAR_DENIED')=='1':
                self.policy_logs[agent]=[{'time':now,'action':'deny','reason':'policy-denied','host':source['host']} for source in tech_radar.SOURCES]
                return True
            poll=tech_radar.run(root,'poll',lambda source,cache:(sample(source,now),{}),now)
            tech_radar.save(root,tech_radar.DRAFT,{'token':poll['token'],'articleId':poll['articles'][0]['id'],'answer':'TEST FIXTURE: Explore a Python inference SDK with a practical developer tutorial.'})
            tech_radar.run(root,'publish')
        return agent in self.agents

def telegram_request(token,method,payload=None):
    if not token.endswith('x'*30):raise RuntimeError('Telegram could not confirm the request. Check the bot token.')
    return {'username':'bac_test_bot'} if method=='getMe' else {'message_id':1}

settings.request=lambda *args,**kwargs:{'data':[{'id':'fixture-model-one'},{'id':'fixture-model-two'}]}
settings.model_available=lambda:True
telegram_notifications.request=telegram_request
with tempfile.TemporaryDirectory() as tmp:
    os.environ['BAC_DATA_DIR']=tmp
    studio=Studio(Path(tmp)/'studio',Adapter())
    server=create_server('127.0.0.1',int(os.environ.get('BAC_TEST_PORT','8087')),studio)
    print('HEARTBEAT BROWSER FIXTURE - NO REAL MODEL OR TELEGRAM',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.stop.set();server.server_close()

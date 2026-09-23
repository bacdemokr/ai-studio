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
import notes_watch

class Adapter(BrowserAdapter):
    def status(self):return {**super().status(),'event':settings.event(),'location':settings.location(),'installed':False}
    def set_notes_heartbeat(self,agent,enabled):return True

class FixtureStudio(Studio):
    def upload(self,owner,data):
        result=super().upload(owner,data)
        if 'notes' in self.profile(owner)['skills']:
            root=self.workspace(owner);poll=notes_watch.run(root,'poll')
            notes_watch.save(root,'artifacts/notes-draft.json',{'token':poll['token'],'answer':'TEST FIXTURE: Review the design tomorrow. Pat owns the follow-up.'})
            notes_watch.run(root,'publish')
        return result

def telegram_request(token,method,payload=None):
    if not token.endswith('x'*30):raise RuntimeError('Telegram could not confirm the request. Check the bot token.')
    return {'username':'bac_test_bot'} if method=='getMe' else {'message_id':1}

settings.request=lambda *args,**kwargs:{'data':[{'id':'fixture-model-one'},{'id':'fixture-model-two'}]}
settings.model_available=lambda:True
telegram_notifications.request=telegram_request
with tempfile.TemporaryDirectory() as tmp:
    os.environ['BAC_DATA_DIR']=tmp
    studio=FixtureStudio(Path(tmp)/'studio',Adapter())
    server=create_server('127.0.0.1',int(os.environ.get('BAC_TEST_PORT','8087')),studio)
    print('HEARTBEAT BROWSER FIXTURE - NO REAL MODEL OR TELEGRAM',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.stop.set();server.server_close()

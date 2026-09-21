import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
import runtime_settings as settings
from fixture_studio import BrowserAdapter
from studio import Studio
from serve import create_server
class Adapter(BrowserAdapter):
 def status(self):return {**super().status(),'event':settings.event(),'location':settings.location(),'installed':False}
def fixture_request(provider,profile,suffix,payload=None,timeout=25):
 return {'data':[{'id':'fixture-model-one'},{'id':'fixture-model-two'}]}
settings.request=fixture_request
with tempfile.TemporaryDirectory() as folder:
 os.environ['BAC_DATA_DIR']=folder
 server=create_server('127.0.0.1',int(os.environ.get('BAC_TEST_PORT','8082')),Studio(Path(folder)/'studio',Adapter()))
 print('SETTINGS TEST FIXTURE',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()

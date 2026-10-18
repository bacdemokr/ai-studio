"""Disposable Open Task HTTP fixture, with simulated models and isolated data."""
import os,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).resolve().parents[1]/'scripts')]
from fixture_visitor_teams import BrowserAdapter
from studio import Studio
from serve import create_server
class Fixture(BrowserAdapter):
    def respond(self,agent,session,prompt,**kwargs):
        if '[fixture:slow]' in prompt:time.sleep(4)
        if '[fixture:error]' in prompt:raise RuntimeError('TEST FIXTURE: model unavailable')
        return super().respond(agent,session,prompt,**kwargs)
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='bac-open-task-ui-') as folder,patch.dict(os.environ,{'BAC_DATA_DIR':folder}),patch('runtime_settings.request',return_value={'data':[{'id':m} for m in ('fixture-local-model','fixture-other-model','nvidia/nvidia/nemotron-3.5-super-vl','nvidia/nvidia/nemotron-3.5-lightning')]}):
        app=Studio(folder,Fixture());server=create_server(os.environ.get('BAC_TEST_HOST','127.0.0.1'),int(os.environ.get('BAC_TEST_PORT','8083')),app)
        print('Open Task fixture ready',flush=True)
        try:server.serve_forever()
        finally:app.stop.set();server.server_close()

"""Disposable recorded handoffs for the browser regression; no model or user data."""
import sys,tempfile,json
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).parent)]
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as directory:
    studio=Studio(directory,Adapter(),start_worker=False)
    owner=studio.session()[0]['id']
    studio.enqueue(owner,{'kind':'crew','preset':True,'brief':{'schema':2},'enabledRoles':[0,1,2,3]})
    studio.execute(studio.next_job())
    state=studio.state(owner)
    state.update(runtime={'ready':True,'model':True,'gateway':True,'testFixture':True},csrf='fixture',canConfigure=False)
    print(json.dumps(state))

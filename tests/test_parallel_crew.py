import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parent)]
from studio import Studio
from fixture_studio import BrowserAdapter

class ParallelAdapter(BrowserAdapter):
    def __init__(self):
        super().__init__();self.barrier=threading.Barrier(2);self.lock=threading.Lock();self.active=0;self.peak=0;self.finished=[];self.prompts={};self.failure=False;self.on_pair=None
    def respond(self,agent,session,prompt):
        stage=int(session.rsplit('-',1)[-1]) if session.startswith('bac-crew-') else 0
        with self.lock:self.active+=1;self.peak=max(self.peak,self.active);self.prompts[stage]=prompt
        try:
            if stage in [1,2]:
                self.barrier.wait(timeout=5)
                if stage==1:
                    time.sleep(.15)
                    if self.failure:raise RuntimeError('Demo failed')
                elif self.on_pair:self.on_pair()
            answer=super().respond(agent,session,prompt)
            with self.lock:self.finished.append(stage)
            return answer
        finally:
            with self.lock:self.active-=1

class ParallelCrewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.adapter=ParallelAdapter();self.studio=Studio(self.temp.name,self.adapter,start_worker=False)
        self.owner=self.studio.session()[0]['id'];self.job=self.studio.enqueue(self.owner,{'kind':'crew','preset':True,'brief':{'schema':2}})['id']

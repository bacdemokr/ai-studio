"""Browser test server with explicit fixture status; never used by start.sh or bac."""
import sys
import json
import tempfile
import time
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parent)]
from test_studio import Adapter
from studio import Studio
from serve import create_server


class BrowserAdapter(Adapter):
    def status(self):
        return {'ready': True, 'gateway': True, 'model': True, 'testFixture': True,
                'version': 'TEST FIXTURE', 'openshell': 'not configured'}

    def respond(self, agent_id, session, prompt):
        if '[fixture:fail-once]' in prompt and agent_id not in getattr(self, 'failed_agents', set()):
            self.failed_agents = getattr(self, 'failed_agents', set()) | {agent_id}
            raise RuntimeError('TEST FIXTURE: model unavailable; saved files remain.')
        time.sleep(.25)
        if 'reaction-time game' in prompt:
            prompt += ' app fixture'
        if 'Act as venue scout and marketing writer.' in prompt:
            return 'TEST FIXTURE — no website was fetched.\n```json\n'+json.dumps({'subject':'Build your next agent with us · Zurich', 'body':'Hello [First name],\n\nJoin our Build-a-Claw demo event. Explore personal agents, multi-agent teams and CUDA-X ideas.\n\nDate: [TBC]\nVenue: Fixture Hotel — fictional test candidate, not booked.\nRegistration: [TBC]\n\nThis invitation is a test fixture, not a live model response.', 'venue':{'name':'Fixture Hotel · fictional','url':''}})+'\n```'
        if 'Act as audience host and independent reviewer.' in prompt:
            return 'TEST FIXTURE review.\n```json\n'+json.dumps({'survey':{'title':'Help shape your BaC demos','intro':'Test fixture questions. No name or email is collected.','topicQuestion':'Which topic would you try first?','experienceQuestion':'Have you worked with agents before?','ratingQuestion':'How useful does this event sound?'}})+'\n```'
        return super().respond(agent_id, session, prompt)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='bac-browser-test-') as folder:
        studio = Studio(folder, BrowserAdapter())
        server = create_server('127.0.0.1', 8082, studio)
        print('BROWSER TEST FIXTURE: http://127.0.0.1:8082', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            studio.stop.set()
            server.server_close()

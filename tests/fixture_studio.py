"""Browser test server with explicit fixture status; never used by start.sh or bac."""
import sys
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
                'version': 'TEST FIXTURE', 'openshell': 'not configured', 'telegram': False}

    def respond(self, agent_id, session, prompt):
        if '[fixture:fail-once]' in prompt and agent_id not in getattr(self, 'failed_agents', set()):
            self.failed_agents = getattr(self, 'failed_agents', set()) | {agent_id}
            raise RuntimeError('TEST FIXTURE: model unavailable; saved files remain.')
        time.sleep(.25)
        if 'reaction-time game' in prompt:
            prompt += ' app fixture'
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

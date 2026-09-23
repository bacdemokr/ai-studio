"""Disposable twelve-agent HTTP fixture. No native services, model or Telegram calls."""
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).parent)]
from test_twelve_agents import CapacityAdapter
from studio import Studio
from serve import create_server

class BrowserAdapter(CapacityAdapter):
    def status(self):
        return {'ready': True, 'model': True, 'gateway': True, 'testFixture': True}

    def respond(self, *args):
        time.sleep(.5)  # Keep jobs pending long enough to exercise collection backpressure.
        return super().respond(*args)

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='bac-capacity-browser-') as folder:
        os.environ['BAC_DATA_DIR'] = folder
        studio = Studio(Path(folder) / 'studio', BrowserAdapter())
        server = create_server('127.0.0.1', int(os.environ.get('BAC_TEST_PORT', '8092')), studio)
        print('TWELVE AGENT TEST FIXTURE - no real model or Telegram', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            studio.stop.set(); studio.signal.set()
            studio.worker.join(5); studio.heartbeat_worker.join(5)
            server.server_close()

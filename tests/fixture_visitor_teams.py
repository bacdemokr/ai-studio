"""Disposable real HTTP/SQLite dispatcher with simulated model replies."""
import os
from pathlib import Path
import signal
import sys
import tempfile
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1] / 'scripts')]
from test_visitor_teams import VisitorAdapter
from studio import Studio
from serve import create_server


class BrowserAdapter(VisitorAdapter):
    def status(self):
        return {**super().status(), 'teamReady': True, 'teamModel': True,
                'testFixture': True, 'sharedModel': 'SIMULATED MODEL', 'openshell': 'Not configured'}


if __name__ == '__main__':
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='bac-visitor-fixture-') as folder, patch.dict(os.environ, {'BAC_DATA_DIR': folder}):
        studio = Studio(Path(folder) / 'studio', BrowserAdapter())
        server = create_server('127.0.0.1', int(os.environ.get('BAC_TEST_PORT', '18240')), studio)
        print('VISITOR FIXTURE READY', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            studio.stop.set()
            server.server_close()

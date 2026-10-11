"""Isolated browser fixture with prepared connections and simulated inference."""
import os
from pathlib import Path
import signal
import sys
import tempfile
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).resolve().parents[1] / 'scripts')]
from fixture_visitor_teams import BrowserAdapter
import model_connections as connections
import runtime_settings as settings
import team_models
from serve import create_server
from studio import Studio


class ModelAdapter(BrowserAdapter):
    def respond(self, agent, session, prompt, **kwargs):
        answer = super().respond(agent, session, prompt, **kwargs)
        if answer == 'Fixture personal reply.':
            return 'Simulated model: ' + self.profiles[agent]['_connectionConfig']['models'][0]['id']
        return answer


if __name__ == '__main__':
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    rows = {'data': [{'id': model} for model in ['fixture-a', 'fixture-b', *team_models.MODELS, *[f'example/model-{i:03}' for i in range(90)]]]}
    with tempfile.TemporaryDirectory(prefix='bac-personal-models-') as folder, \
         patch.dict(os.environ, {'BAC_DATA_DIR': folder}), patch.object(settings, 'request', return_value=rows):
        studio = Studio(Path(folder) / 'studio', ModelAdapter())
        connections.initialize()
        connections.configure(studio, {'source': 'api', 'provider': 'nvidia', 'apiKey': 'fixture-key',
                                      'model': 'fixture-a', 'contextWindow': 32768})
        connections.preferences(studio, {'lounge': 'api', 'disable': 'local'})
        server = create_server('0.0.0.0', int(os.environ.get('BAC_TEST_PORT', '18243')), studio)
        print('PERSONAL MODEL FIXTURE READY', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            studio.stop.set()
            server.server_close()

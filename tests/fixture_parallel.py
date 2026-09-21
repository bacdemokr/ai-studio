import tempfile,time
from pathlib import Path
from fixture_studio import BrowserAdapter,Studio,create_server
class ParallelPreview(BrowserAdapter):
    def respond(self,agent,session,prompt):
        if 'Act as the event lead' in prompt:time.sleep(4)
        if session.startswith('bac-crew-') and session.endswith(('-1','-2')):time.sleep(5)
        return super().respond(agent,session,prompt)
with tempfile.TemporaryDirectory() as folder:
    studio=Studio(folder,ParallelPreview());server=create_server('127.0.0.1',8082,studio)
    print('Parallel test fixture',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.stop.set();server.server_close()

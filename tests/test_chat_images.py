import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chat_images import validate_images
from studio import Studio,Problem
from test_studio import Adapter
import agent_runtime
PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg=='
IMAGE={'dataUrl':'data:image/png;base64,'+PNG}
class Images(unittest.TestCase):
 def test_storage_scope_and_request(self):
  class Vision(Adapter):
   def respond(self,agent,session,prompt,images=None):
    self.received=images
    return 'Image received'
  with tempfile.TemporaryDirectory() as folder:
   adapter=Vision();studio=Studio(folder,adapter,start_worker=False);owner=studio.session()[0]['id'];studio.onboard(owner,{'name':'Vision','skills':['documents']})
   job=studio.enqueue(owner,{'kind':'chat','prompt':'','images':[IMAGE]});studio.execute(studio.next_job());state=studio.state(owner);saved=state['jobs'][0]['payload']['images'][0]
   self.assertEqual(adapter.received,[{'mime':'image/png','data':PNG}]);self.assertNotIn('dataUrl',saved)
   self.assertEqual((studio.workspace(owner)/saved['path']).read_bytes(),base64.b64decode(PNG))
   other=studio.session()[0]['id'];self.assertFalse((studio.workspace(other)/saved['path']).exists())
 def test_reject_urls_and_invalid_payloads(self):
  for images in [[{'dataUrl':'https://example.com/image.png'}],[IMAGE]*5,[{'dataUrl':'data:image/png;base64,aGVsbG8='}]]:
   with self.assertRaises(ValueError):validate_images(images)
 def test_native_multimodal_payload(self):
  calls=[]
  def gateway(path,payload=None,**kwargs):
   if path=='/v1/models':return {'data':[{'id':'openclaw/test-image'}]}
   calls.append(payload);return {'choices':[{'message':{'content':'I see the image'}}]}
  with patch('agent_runtime.gateway',side_effect=gateway),patch('telemetry.measure',return_value={}):
   agent_runtime.respond('test-image','session','Describe',images=[{'mime':'image/png','data':PNG}])
  self.assertEqual(calls[0]['messages'][0]['content'][1],{'type':'image_url','image_url':{'url':IMAGE['dataUrl']}})

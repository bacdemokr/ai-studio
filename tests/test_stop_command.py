"""Exercise the shutdown entry point with fake Docker/model commands only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ShutdownCommandTests(unittest.TestCase):
    def run_stop(self,*args,fail_sandboxes=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);bin_dir=root/'bin';bin_dir.mkdir()
            shutil.copy2(ROOT/'bac',root/'bac')
            (root/'compose.yaml').write_text('name: bac-demo\n')
            (root/'.env').write_text('')
            (root/'scripts').mkdir()
            (root/'scripts/local_model.py').write_text('')
            (root/'scripts/container_remove.py').write_text('')
            log=root/'calls.jsonl'
            shim='#!'+sys.executable+'\n'+'''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name;a=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f:f.write(json.dumps([name,*a])+'\\n')
if name=='uname':print('Linux')
elif name=='docker':
 if a[:2]==['compose','version']:print('2.24.0')
 elif a[:2]==['context','inspect']:print('unix:///var/run/docker.sock')
 elif a and a[0]=='info':print('28.0.0 aarch64 []')
 elif a and a[-1]=='config':print('services:\\n  studio:\\n    image: bac-studio:dev')
 elif a and a[0]=='run' and os.environ.get('FAIL_SANDBOX')=='1':sys.exit(1)
'''
            for name in ('uname','docker','python3','flock'):
                p=bin_dir/name;p.write_text(shim);p.chmod(0o755)
            result=subprocess.run(['/bin/bash','./bac','stop',*args],cwd=root,env={**os.environ,'PATH':str(bin_dir)+':/usr/bin:/bin','CALL_LOG':str(log),'FAIL_SANDBOX':str(int(fail_sandboxes))},capture_output=True,text=True)
            calls=[json.loads(line) for line in log.read_text().splitlines()]
            return result,calls

    def test_all_stops_stack_sandboxes_and_managed_model_then_deletes_volumes(self):
        result,calls=self.run_stop('--all')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['python3','scripts/local_model.py','stop'],calls)
        self.assertTrue(any(c[0]=='docker' and c[-1]=='--stop' for c in calls))
        self.assertIn(['docker','compose','-f','compose.yaml','down','--volumes'],calls)

    def test_normal_stop_leaves_model_and_failure_still_attempts_model_stop(self):
        result,calls=self.run_stop()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn(['python3','scripts/local_model.py','stop'],calls)
        self.assertNotIn(['docker','compose','-f','compose.yaml','down','--volumes'],calls)
        result,calls=self.run_stop('--all',fail_sandboxes=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(['python3','scripts/local_model.py','stop'],calls)
        self.assertIn(['docker','compose','-f','compose.yaml','down','--volumes'],calls)
        self.assertIn('incomplete',result.stderr)

if __name__=='__main__':unittest.main()

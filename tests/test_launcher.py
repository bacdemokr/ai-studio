"""Exercise the shipped Bash entry point with a deterministic Docker executable."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bac launch ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root/'bin'
        self.bin.mkdir()
        shutil.copy2(ROOT/'bac', self.root/'bac')
        (self.root/'scripts').mkdir()
        shutil.copy2(ROOT/'scripts/setup-key-filter.sh', self.root/'scripts/setup-key-filter.sh')
        (self.root/'compose.yaml').write_text('services: {}\n')
        (self.root/'.env').write_text('BAC_IMAGE=bac-studio:test\n')
        (self.root/'release.json').write_text('{}')
        (self.root/'remove.py').touch(); (self.root/'runtime-lock.json').write_text('{}')
        self.state = self.root/'docker-state.json'
        self.state.write_text(json.dumps({'image': False}))
        self.log = self.root/'calls.jsonl'
        self.env = {**os.environ, 'PATH': str(self.bin)+os.pathsep+os.environ['PATH'],
                    'TEST_STATE': str(self.state), 'TEST_CALLS': str(self.log)}
        self.env.pop('DOCKER_HOST', None)
        self.tool('uname', "print('Linux')\n")
        self.tool('rmdir', "import sys\nprint('Removed release directory: '+sys.argv[-1])\n")
        self.tool('docker', '''import json, os, sys
from pathlib import Path
args=sys.argv[1:]
state_file=Path(os.environ['TEST_STATE'])
s=json.loads(state_file.read_text())
with open(os.environ['TEST_CALLS'],'a') as f:f.write(json.dumps(args)+'\\n')
if args[:2]==['compose','-f']:args=['compose']+args[3:]
if args[:2]==['compose','version']:print(s.get('compose','2.24.0'))
elif args[:2]==['context','inspect']:print('unix:///var/run/docker.sock')
elif args[0]=='info':
    if s.get('offline'):sys.exit(1)
    print('29.8.0 '+s.get('hostarch','aarch64')+' '+ ('["rootless"]' if s.get('rootless') else '[]'))
elif args[:2]==['compose','config']:
    print('services:\\n  studio:\\n    environment:\\n      PORT: "8087"\\n    image: bac-studio:test\\n')
elif args[:2]==['image','inspect']:
    if not s['image'] or args[-1] in s.get('removed',[]):sys.exit(1)
    print(s.get('imagearch','arm64') if '--format' in args else '[]')
elif args[:2]==['image','rm']:
    if s.get('rm_retry') and args[-1]=='parent:old' and 'child:old' not in s.get('removed',[]):sys.exit(1)
    s.setdefault('removed',[]).append(args[-1]);state_file.write_text(json.dumps(s))
elif args[0]=='load' or args[:2] in (['compose','build'],['compose','pull']):
    s['image']=True;state_file.write_text(json.dumps(s))
elif args[:2]==['compose','run']:
    if s.get('invalid_key'):sys.exit(1)
elif args[:2]==['compose','up']:
    if s.get('fail_up'):sys.exit(1)
    print('Studio Healthy')
elif args[0]=='run':
    if '/opt/bac/source/scripts/build.py' in args:
        sys.exit(1 if s.get('invalid_app') else 0)
    if '--check' in args:
        sys.exit(1 if s.get('runtime_mismatch') else 0)
    if '--record' in args:
        sys.exit(1 if s.get('fail_record') else 0)
    if s.get('fail_remove'):sys.exit(1)
    print('Removed BaC containers.\\n'+('BAC_IMAGE parent:old\\nBAC_IMAGE child:old' if s.get('rm_retry') else 'BAC_IMAGE bac-studio:test'))
elif args[0]=='ps':
    if s.get('image_in_use'):print('other-container')
''')
        self.tool('sha256sum', '''import hashlib,sys
from pathlib import Path
for row in sys.stdin.read().splitlines():
    expected,name=row.split('  ',1)
    if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected:sys.exit(1)
''')

    def tool(self, name, code):
        path = self.bin/name
        path.write_text('#!'+sys.executable+'\n'+code)
        path.chmod(0o755)

    def configure(self, **changes):
        state=json.loads(self.state.read_text());state.update(changes)
        self.state.write_text(json.dumps(state))

    def run_bac(self, *args, input=''):
        return subprocess.run(['bash', str(self.root/'bac'), *args], cwd=self.root.parent,
                              env=self.env, text=True, input=input, capture_output=True, timeout=15)

    def calls(self):
        return [json.loads(row) for row in self.log.read_text().splitlines()] if self.log.exists() else []

    def operations(self):
        return [a[3:] for a in self.calls() if a[:3]==['compose','-f','compose.yaml']]

    def archive(self):
        name='bac-image.tar.gz';(self.root/name).write_bytes(b'fixture image archive')
        (self.root/'image-archive.txt').write_text(name+'\n')
        checksum=hashlib.sha256((self.root/name).read_bytes()).hexdigest()
        (self.root/'SHA256SUMS').write_text(checksum+'  '+name+'\n')
        return self.root/name

    def enable_local_model(self):
        (self.root/'local-model.json').write_text('{"enabled":true}')
        (self.root/'scripts/local_model.py').write_text("""import json,os,sys
from pathlib import Path
state=json.loads(Path(os.environ['TEST_STATE']).read_text())
action=sys.argv[1]
with open(os.environ['TEST_CALLS'],'a') as out:out.write(json.dumps(['local-model',*sys.argv[1:]])+'\\n')
if action=='start':
    if state.get('model_failure'):sys.exit(1)
    folder=Path('.local-model');folder.mkdir(exist_ok=True)
    (folder/'connection.json').write_text('{}')
if action=='connect' and state.get('connection_failure'):sys.exit(1)
""")

    def test_ready_defaults_to_qwen_without_docker_or_api_key(self):
        self.enable_local_model();self.configure(offline=True)
        result=self.run_bac('vllm')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.calls(),[['local-model','start','--model','qwen'],['local-model','commit']])
        self.assertFalse((self.root/'api.cfg').exists())

    def test_ready_accepts_explicit_model_and_separate_lifecycle(self):
        self.enable_local_model()
        result=self.run_bac('vllm','--model','gemma')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['local-model','start','--model','gemma'],self.calls())
        for option,action in (('--stop','stop'),('--status','status'),('--logs','logs')):
            self.log.unlink(missing_ok=True)
            result=self.run_bac('vllm',option)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(self.calls(),[['local-model',action]])

    def test_start_and_stop_leave_local_model_alone(self):
        self.enable_local_model();self.configure(image=True,model_failure=True)
        for action in ('start','stop'):
            self.log.unlink(missing_ok=True)
            result=self.run_bac(action)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(any(c[0]=='local-model' for c in self.calls()))

    def test_failed_ready_never_starts_studio(self):
        self.enable_local_model();self.configure(model_failure=True)
        result=self.run_bac('vllm')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.calls(),[['local-model','start','--model','qwen']])

    def test_vllm_restart_is_one_command_without_starting_studio(self):
        self.enable_local_model();self.configure(offline=True)
        result=self.run_bac('vllm','--restart')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.calls(),[['local-model','restart','--model','qwen']])

    def test_help_needs_no_docker_and_lists_only_daily_commands(self):
        result=self.run_bac()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('./bac start',result.stdout)
        self.assertNotIn('./bac restart',result.stdout)
        self.assertEqual(self.calls(),[])
        self.assertNotIn('--model qwen',result.stdout)

    def test_archive_first_start_verifies_loads_and_waits_then_reuses_image(self):
        self.archive()
        result=self.run_bac('start')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Ready: http://localhost:8087',result.stdout)
        self.assertEqual(sum(a[0]=='load' for a in self.calls()),1)
        self.assertIn(['up','-d','--force-recreate','--no-build','--pull','missing','--wait','--wait-timeout','180'],self.operations())
        self.assertEqual(self.run_bac('start').returncode,0)
        self.assertEqual(sum(a[0]=='load' for a in self.calls()),1)

    def test_invalid_key_stops_before_service_restart(self):
        self.configure(image=True, invalid_key=True)
        result=self.run_bac('start')
        self.assertNotEqual(result.returncode,0)
        self.assertTrue((self.root/'api.cfg').is_file())
        self.assertEqual((self.root/'api.cfg').read_text(), '')
        self.assertFalse(any(a[0] in ('stop','up') for a in self.operations()))

    def test_corrupt_or_missing_archive_never_starts(self):
        archive=self.archive();archive.write_bytes(b'corrupt')
        result=self.run_bac('start')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('checksum failed',result.stderr)
        self.assertFalse(any(a[0]=='load' for a in self.calls()))
        archive.unlink()
        self.assertIn('archive is missing',self.run_bac('start').stderr)
        self.assertFalse(any(a[0]=='up' for a in self.operations()))

    def test_app_only_patch_reuses_image_and_recreates_services(self):
        self.configure(image=True)
        result=self.run_bac('start')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(any(a[0] in ('build','pull') for a in self.operations()))
        self.assertTrue(any('--force-recreate' in a for a in self.operations()))
        self.assertTrue(any('--check' in a for a in self.calls()))

    def test_mismatched_release_stops_before_touching_services(self):
        self.configure(image=True,runtime_mismatch=True)
        result=self.run_bac('start')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('matching complete release',result.stderr)
        self.assertFalse(any(a[0] in ('stop','up') for a in self.operations()))

    def test_broken_app_patch_does_not_stop_existing_services(self):
        self.configure(image=True, invalid_app=True)
        result = self.run_bac('start')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(a[0] in ('stop', 'up') for a in self.operations()))
        self.assertFalse(any('--record' in a for a in self.calls()))

    def test_registry_kit_pulls_only_when_missing(self):
        self.assertEqual(self.run_bac('start').returncode,0)
        self.assertIn(['pull','studio','init'],self.operations())
        self.assertFalse(any(a[0]=='build' for a in self.operations()))

    def test_source_start_creates_env_and_builds_without_host_python(self):
        (self.root/'release.json').unlink();(self.root/'Dockerfile').touch()
        (self.root/'.env').unlink();(self.root/'.env.example').write_text('BAC_IMAGE=bac-studio:dev\n')
        result=self.run_bac('start')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.root/'.env').exists())
        self.assertIn(['build'],self.operations())

    def test_start_stops_both_services_then_waits_without_deleting_data(self):
        self.configure(image=True)
        sentinel=self.root/'shared/keep.txt';sentinel.parent.mkdir();sentinel.write_text('keep')
        result=self.run_bac('start')
        self.assertEqual(result.returncode,0,result.stderr)
        ops=self.operations();stop=ops.index(['stop','studio','openshell'])
        self.assertEqual(ops[stop+1][0],'up')
        self.assertFalse(any(a[0] in ('down','build','pull') for a in ops))
        self.assertEqual(sentinel.read_text(),'keep')

    def test_failed_readiness_is_not_reported_as_ready(self):
        self.configure(image=True,fail_up=True)
        result=self.run_bac('start')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('Ready:',result.stdout)
        self.assertIn('./bac logs',result.stderr)

    def test_status_logs_stop_do_not_install_or_start_anything(self):
        for command in ('status','logs','stop'):
            with self.subTest(command=command):
                self.log.unlink(missing_ok=True)
                result=self.run_bac(command)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertFalse(any(a[0] in ('up','build','pull') for a in self.operations()))
                self.assertFalse(any(a[0]=='load' for a in self.calls()))

    def test_wrong_architecture_old_compose_and_offline_docker_have_remedies(self):
        self.configure(image=True,imagearch='amd64')
        self.assertIn('use the arm64 release',self.run_bac('start').stderr)
        self.configure(imagearch='arm64',compose='2.23.0')
        self.assertIn('2.24 or newer',self.run_bac('start').stderr)
        self.configure(compose='5.5.1',offline=True)
        self.assertIn('Docker is not reachable',self.run_bac('start').stderr)
        self.assertFalse(any(a[0]=='up' for a in self.operations()))

    def test_rootless_remote_and_macos_are_rejected_before_start(self):
        self.configure(rootless=True)
        self.assertIn('rootful',self.run_bac('start').stderr)
        self.env['DOCKER_HOST']='ssh://another-host'
        self.assertIn('local Docker',self.run_bac('start').stderr)
        self.tool('uname',"print('Darwin')\n")
        self.assertIn('./bac dev preview',self.run_bac('start').stderr)

    def test_env_is_not_executed_and_old_host_command_requires_dev(self):
        marker=self.root/'should-not-exist'
        (self.root/'.env').write_text('BAD=$(touch '+str(marker)+')\n')
        self.configure(image=True)
        self.assertEqual(self.run_bac('status').returncode,0)
        self.assertFalse(marker.exists())
        self.assertIn('./bac dev COMMAND',self.run_bac('setup').stderr)

    def test_remove_cancel_and_eof_never_load_or_delete(self):
        for response in ('', 'no\n'):
            result=self.run_bac('remove',input=response)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('Cancelled',result.stdout)
        self.assertFalse(any(a[0] in ('run','load','image') for a in self.calls()))

    def remove_fixture(self, **state):
        self.configure(image=True,**state)
        (self.root/'remove.py').touch(); (self.root/'runtime-lock.json').write_text('{}')
        return self.run_bac('remove',input='remove\n')

    def test_remove_uses_scoped_helper_then_nonforced_image_removal(self):
        result=self.remove_fixture()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('BaC removed.',result.stdout)
        call=next(a for a in self.calls() if a[0]=='run')
        self.assertIn('com.nvidia.bac.cleanup=true',call)
        self.assertIn('type=bind,src='+str(self.root/'remove.py')+',dst=/remove.py,readonly',call)
        self.assertIn('type=bind,src='+str(self.root.resolve())+',dst=/installation',call)
        self.assertEqual(call[-1],'release')
        self.assertIn('Removed release directory:',result.stdout)
        self.assertIn(['image','rm','bac-studio:test'],self.calls())
        self.assertFalse(any('prune' in a or '--force' in a for a in self.calls()))

    def test_failed_cleanup_does_not_delete_images_or_claim_success(self):
        result=self.remove_fixture(fail_remove=True)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('BaC removed.',result.stdout)
        self.assertFalse(any(a[:2]==['image','rm'] for a in self.calls()))

    def test_images_used_by_other_containers_are_kept(self):
        result=self.remove_fixture(image_in_use=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Image still in use or not removed:',result.stderr)
        self.assertNotIn('BaC removed.',result.stdout)
        self.assertFalse(any(a[:2]==['image','rm'] for a in self.calls()))

    def test_source_remove_preserves_checkout(self):
        (self.root/'release.json').unlink()
        (self.root/'scripts').mkdir(exist_ok=True); (self.root/'scripts/container_remove.py').touch()
        (self.root/'docker').mkdir(); (self.root/'docker/runtime-lock.json').write_text('{}')
        self.configure(image=True)
        result=self.run_bac('remove',input='remove\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Source code remains.',result.stdout)
        self.assertNotIn('Removed release directory:',result.stdout)
        self.assertEqual(next(a for a in self.calls() if a[0]=='run')[-1],'source')

    def test_image_history_is_recorded_before_provisioning_without_docker_socket(self):
        self.configure(image=True)
        result=self.run_bac('start')
        self.assertEqual(result.returncode,0,result.stderr)
        calls=self.calls(); record=next(a for a in calls if '--record' in a)
        self.assertIn('--record',record); self.assertNotIn('/var/run/docker.sock',' '.join(record))
        self.assertLess(calls.index(record),next(i for i,a in enumerate(calls) if 'up' in a))

    def test_failed_history_recording_does_not_provision(self):
        self.configure(image=True,fail_record=True)
        self.assertNotEqual(self.run_bac('start').returncode,0)
        self.assertFalse(any(a[0]=='up' for a in self.operations()))

    def test_parent_image_is_retried_after_its_child_is_removed(self):
        result=self.remove_fixture(rm_retry=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([a for a in self.calls() if a[:2]==['image','rm']],
                         [['image','rm','parent:old'],['image','rm','child:old'],['image','rm','parent:old']])


if __name__=='__main__':unittest.main()

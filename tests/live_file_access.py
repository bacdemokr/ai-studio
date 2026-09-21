"""Opt-in integration with real OpenShell; only inference is replaced by deterministic tool commands."""
import os,sys,tempfile,json,subprocess,shlex,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
if os.environ.get('BAC_LIVE_POLICY_TEST')!='1':raise SystemExit('Set BAC_LIVE_POLICY_TEST=1')
import agent_policy as policy
import file_access as files
from studio import Studio
with tempfile.TemporaryDirectory(prefix='bac-file-live-') as folder:
 root=Path(folder).resolve();host=root/'outside.txt';host.write_text('original host data')
 studio=Studio(root/'data',start_worker=False);account,_=studio.session();owner=account['id']
 studio.onboard(owner,{'name':'Synthetic file test','persona':'guide','skills':['weather'],'protection':'openshell'})
 workspace=studio.workspace(owner);read='file:read:'+str(host);write='file:write:'+str(host)
 def seed():
  with patch.object(studio,'runtime_status',return_value={'ready':True}):job=studio.enqueue(owner,{'prompt':'Read '+str(host)})
  studio.decision(owner,job['id'],'cancel')
 seed()
 try:
  assert read in studio.policy_report(owner)['pendingFiles']
  studio.policy_change(owner,{'permission':read,'allow':True})
  report=studio.policy_report(owner);name=report['sandboxes'][0]['name']
  cfg=policy.shell('sandbox','ssh-config',name);ssh=root/'ssh';ssh.write_text(cfg);ssh.chmod(0o600)
  alias=re.search(r'^Host\s+(\S+)',cfg,re.M).group(1)
  def run(command):
   return subprocess.run(['ssh','-F',str(ssh),'-o','BatchMode=yes',alias,command],capture_output=True,text=True,timeout=40)
  assert run('/bin/cat '+shlex.quote(str(host))).returncode!=0,'Host file must not be directly visible'
  records=files.prepare(workspace,[read]);relative=records[0]['relative'];remote='/sandbox/'+relative
  policy.shell('sandbox','upload',name,str(workspace/'inbox'),'/sandbox',timeout=60)
  got=run('/bin/cat '+shlex.quote(remote));assert got.returncode==0 and got.stdout=='original host data',got.stderr
  print('PASS: host path isolated; approved protected copy readable in OpenShell',flush=True)
  changed=run("printf 'sandbox edit' > "+shlex.quote(remote));assert changed.returncode==0,changed.stderr
  policy.shell('sandbox','download',name,remote,str(workspace/'inbox'),timeout=60)
  files.finish(workspace,records);assert host.read_text()=='original host data'
  print('PASS: changing read-only grant copy cannot write back to host',flush=True)
  studio.policy_change(owner,{'permission':write,'allow':True})
  records=files.prepare(workspace,[write])
  assert run('/bin/rm -f -- '+shlex.quote(remote)).returncode==0
  policy.shell('sandbox','upload',name,str(workspace/relative),'/sandbox/inbox/',timeout=60)
  edited=run("printf 'approved edit' > "+shlex.quote(remote))
  assert edited.returncode==0, edited.stderr + run('id; ls -ld /sandbox/inbox; ls -l /sandbox/inbox').stdout
  policy.shell('sandbox','download',name,remote,str(workspace/'inbox'),timeout=60)
  files.finish(workspace,records);assert host.read_text()=='approved edit'
  print('PASS: exact-file read/write grant saves sandbox edits back to host',flush=True)
  studio.policy_change(owner,{'permission':write,'allow':False});studio.policy_change(owner,{'permission':read,'allow':False})
  files.prepare(workspace,[]);assert not (workspace/relative).exists()
  # Pinned native mirror deletes remote root contents before re-upload on each exec.
  assert run('/bin/rm -f -- '+shlex.quote(remote)).returncode==0
  assert run('/bin/cat '+shlex.quote(remote)).returncode!=0
  assert host.read_text()=='approved edit'
  print('PASS: revoked copy unavailable after mirror refresh; original preserved',flush=True)
 finally:
  studio.delete_agent(owner,{'name':'Synthetic file test'})

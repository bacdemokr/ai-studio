"""Opt-in real protected research; no LLM, no external write requests.

Creates a synthetic Dylan, uses his actual policy and shipped tools in OpenShell,
then deletes his native workspace. Does not change participant policies.
"""
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
if os.environ.get('BAC_LIVE_POLICY_TEST') != '1':
    raise SystemExit('Set BAC_LIVE_POLICY_TEST=1 and BAC_DATA_DIR to your configured runtime.')
import agent_policy as policy
import agent_runtime as runtime
import agent_workflow
import event_planner
from research_http import RESEARCH_APPROVALS
from studio import Studio


with tempfile.TemporaryDirectory(prefix='bac-protected-research-') as directory:
    studio = Studio(directory, start_worker=False)
    owner = studio.session()[0]['id']
    with studio.db() as db:
        member = studio.crew_roster(db, owner, {}, True)[1]
    workspace = studio.workspace(owner, 1)
    try:
        report = studio.prepare_builtin_crew(owner, 1, member)
        assert report['status'] == 'applied'
        assert {row['host'] for row in report['rules']} == {'blogs.nvidia.com'}
        name = report['sandboxes'][0]['name']
        config = policy.shell('sandbox', 'ssh-config', name)
        ssh = Path(directory) / 'ssh-config'
        ssh.write_text(config); ssh.chmod(0o600)
        alias = re.search(r'^Host\s+(\S+)', config, re.M).group(1)

        def remote(command, data=None):
            result = subprocess.run(['ssh','-F',str(ssh),'-o','BatchMode=yes',alias,command],
                                    input=data, capture_output=True, timeout=90)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace')[:600])
            return result.stdout.decode()

        print('PASS: sandbox running with verified pre-approved NVIDIA Blog reads', flush=True)
        for index, queries in enumerate((['agent'], ['Nemotron','inference'], ['robot','OpenClaw','multimodal'])):
            brief, capacity = event_planner.plan({'schema':2,'themeCount':3})
            agent_workflow.prepare(workspace, 'probe-'+str(index), {'brief':brief,'capacity':capacity}, 1)
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode='w') as tar:
                for file in workspace.rglob('*'):
                    if file.is_file(): tar.add(file, arcname=str(file.relative_to(workspace)))
            remote('mkdir -p /sandbox && tar -xf - -C /sandbox', archive.getvalue())
            command = 'cd /sandbox && python3 skills/bac-event-tools/scripts/event_agent_tools.py '
            search = json.loads(remote(command+'search '+shlex.join(queries)))
            assert search['sources'] and not search['failedQueries'], search.get('failedQueries')
            sources = [source['id'] for source in search['sources'][:index+1]]
            read = json.loads(remote(command+'read '+shlex.join(sources)))
            assert all(source.get('article') and not source.get('readError') for source in read['sources'])
            assert studio.prepare_builtin_crew(owner, 1, member)['status'] == 'applied'
            print('PASS: round %d, %d search queries, %d article reads and saved JSON' % (index+1,len(queries),len(sources)), flush=True)

        started = time.time()
        denied = remote('/usr/bin/curl --disable -fsS --max-time 12 https://example.com/ >/dev/null 2>&1; printf "%s" "$?"')
        assert denied != '0', 'Unapproved host unexpectedly accessible'
        for _ in range(10):
            evidence = policy.public_logs(name)
            if any(row['host']=='example.com' and row['action']=='deny' and row.get('time',0)>=started for row in evidence): break
            time.sleep(.5)
        else: raise AssertionError('Missing native policy denial; network errors alone are not evidence')
        document = policy.read_policy(name)
        assert document['loaded'] and policy.same_policy(document['policy'], policy.policy_document(list(RESEARCH_APPROVALS)))
        assert all(rule['access']=='read-only' for rule in policy.network_rows(document['policy']))
        print('PASS: unrelated host denied with native evidence; read-only policy still loaded', flush=True)
    finally:
        runtime.remove(member['id'], workspace)
        assert not policy.runtimes(member['id'], probe=False)
        print('Synthetic Dylan runtime removed', flush=True)

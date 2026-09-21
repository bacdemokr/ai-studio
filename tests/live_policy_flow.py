"""Opt-in real OpenShell network lifecycle; only the model-readiness gate is mocked.
Creates/removes a synthetic agent, never changes participant approvals.
Run with BAC_LIVE_POLICY_TEST=1 and BAC_DATA_DIR pointing at the configured host.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
if os.environ.get('BAC_LIVE_POLICY_TEST') != '1':
    raise SystemExit('Set BAC_LIVE_POLICY_TEST=1 to opt into a real OpenShell test.')
import agent_policy as policy
from studio import Studio

with tempfile.TemporaryDirectory(prefix='bac-policy-live-') as folder:
    studio = Studio(folder, start_worker=False)
    account, _ = studio.session()
    owner = account['id']
    studio.onboard(owner, {'name': 'Synthetic policy test', 'persona': 'guide', 'skills': ['documents'], 'protection': 'openshell'})
    with patch.object(studio, 'runtime_status', return_value={'ready': True}):
        job = studio.enqueue(owner, {'prompt': 'Read https://api.github.com/zen and look up Zurich at https://geocoding-api.open-meteo.com/v1/search?name=Zurich&count=1'})
    studio.decision(owner, job['id'], 'cancel')
    try:
        print('Preparing a synthetic default-deny workspace', flush=True)
        assert studio.policy_change(owner, {'retry': True})['applied']
        report = studio.policy_report(owner)
        assert report['status'] == 'applied' and report['requested'] == []
        name = report['sandboxes'][0]['name']
        cfg = policy.shell('sandbox', 'ssh-config', name)
        ssh = Path(folder) / 'ssh'
        ssh.write_text(cfg)
        ssh.chmod(0o600)
        alias = re.search(r'^Host\s+(\S+)', cfg, re.M).group(1)
        def remote(command):
            return subprocess.run(['ssh', '-F', str(ssh), '-o', 'BatchMode=yes', alias, command], capture_output=True, text=True, timeout=35)
        def fetch(host):
            result = remote('/usr/bin/curl -sS --max-time 20 -o /dev/null -w "HTTP=%{http_code}" ' + shlex.quote('https://' + host + '/'))
            print(host, result.returncode, result.stdout, result.stderr.strip(), flush=True)
            return result
        blocked = fetch('api.github.com')
        assert blocked.returncode != 0, 'Default deny unexpectedly allowed network access'
        print('PASS: unapproved destination cannot be fetched', flush=True)
        assert studio.policy_change(owner, {'permission': 'host:api.github.com', 'allow': True})['applied']
        assert Studio(folder, start_worker=False).policy_report(owner)['status'] == 'applied'
        allowed = fetch('api.github.com')
        if allowed.returncode:
            time.sleep(2)  # Native logs arrive asynchronously.
            logs = policy.shell('logs', name, '--since', '5m', '-n', '100')
            print('Network diagnostics:', '\n'.join(line for line in logs.splitlines() if 'DENIED' in line or 'DNS' in line), flush=True)
            print('Resolver:', remote('/bin/cat /etc/resolv.conf').stdout, flush=True)
        access_ok = allowed.returncode == 0 and allowed.stdout == 'HTTP=200'
        print('PASS: approval survives app reload', flush=True)
        assert access_ok, 'Approved public GET failed; inspect the network diagnostic above'
        print('PASS: approved public GET works', flush=True)

        def fetch_json(url):
            result = remote('/usr/bin/curl -fsS --max-time 20 ' + shlex.quote(url))
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout)

        # The city lookup and forecast are different approvals. Exercise the
        # actual two-step weather flow in a freshly created VM, not just policy
        # activation: a loaded policy alone cannot prove working DNS/HTTPS.
        city_url = 'https://geocoding-api.open-meteo.com/v1/search?' + urlencode({'name': 'Zurich', 'count': 1})
        assert studio.policy_change(owner, {'permission': 'host:geocoding-api.open-meteo.com', 'allow': True})['applied']
        city = fetch_json(city_url)['results'][0]
        assert city['country_code'] == 'CH' and city['name'] == 'Zurich'
        forecast_url = 'https://api.open-meteo.com/v1/forecast?' + urlencode({
            'latitude': city['latitude'], 'longitude': city['longitude'],
            'current': 'temperature_2m,precipitation,weather_code', 'forecast_days': 1, 'timezone': 'auto'})
        denied = remote('/usr/bin/curl -fsS --max-time 20 ' + shlex.quote(forecast_url))
        assert denied.returncode != 0, 'Geocoding approval must not grant forecast access'
        assert studio.policy_change(owner, {'permission': 'weather', 'allow': True})['applied']
        grants = studio.policy_report(owner)['requested']
        assert grants.count('host:geocoding-api.open-meteo.com') == 1
        assert 'weather' not in grants, 'Approved presets must be expanded into individual hosts'
        forecast = fetch_json(forecast_url)
        assert forecast['timezone'] == 'Europe/Zurich'
        assert isinstance(forecast['current']['temperature_2m'], (int, float))
        assert forecast['current']['time'] and forecast['current_units']['temperature_2m']
        print('PASS: Zurich geocoding and live forecast work with explicit weather approval', flush=True)
        assert studio.policy_change(owner, {'permission': 'host:api.open-meteo.com', 'allow': False})['applied']
        assert fetch('api.open-meteo.com').returncode != 0, 'Revoked weather access unexpectedly allowed'
        assert fetch_json(city_url)['results'][0]['country_code'] == 'CH', 'City lookup must survive individual forecast revoke'
        assert 'host:wttr.in' in studio.policy_report(owner)['requested']
        print('PASS: individual forecast revoke preserves city lookup and wttr.in grants', flush=True)
        assert fetch('example.com').returncode != 0, 'Unapproved second host unexpectedly allowed'
        assert studio.policy_change(owner, {'permission': 'host:api.github.com', 'allow': False})['applied']
        assert fetch('api.github.com').returncode != 0, 'Revoked host unexpectedly allowed'
        time.sleep(2)
        denials = {event['host'] for event in policy.public_logs(name) if event['action'] == 'deny' and event.get('reason') == 'policy-denied'}
        assert {'api.github.com', 'example.com'} <= denials, 'Missing explicit native policy-denial evidence'
        print('PASS: unrelated destination stays blocked; revoked host is blocked again', flush=True)
    finally:
        print('Cleaning synthetic agent', flush=True)
        studio.delete_agent(owner, {'name': 'Synthetic policy test'})
        assert not policy.runtimes('bac-' + owner, probe=False)
        print('PASS: synthetic workspace and native registry cleaned', flush=True)

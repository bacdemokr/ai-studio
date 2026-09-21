"""Disposable-container HTTP session and saved-file check across recreation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

if os.environ.get('BAC_CONTAINER_TEST') != '1':
    raise SystemExit('Use BAC_CONTAINER_TEST=1 in a disposable verification stack.')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import ops_common as common

base = 'http://127.0.0.1:'+os.environ.get('PORT', '8080')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
record = common.home()/'.persistence-smoke.json'
certificate = Path('/run/bac-client/tls.crt')
if sys.argv[1] == 'create':
    with opener.open(base+'/api/session', timeout=15) as response:
        cookie = response.headers['Set-Cookie'].split(';')[0]
        session = json.load(response)
    assert session['canConfigure'], 'Local browser was not recognized as operator'
    request = urllib.request.Request(base+'/api/onboard', data=json.dumps({
        'name': 'Image update test', 'persona': 'guide', 'skills': ['documents']}).encode(),
        headers={'Cookie': cookie, 'X-BaC-CSRF': session['csrf'], 'Content-Type': 'application/json'})
    with opener.open(request, timeout=15) as response:
        profile = json.load(response)
    artifact = common.home()/'persistence-artifact.txt'
    artifact.write_text('Saved event file survives image replacement.\n')
    record.write_text(json.dumps({'cookie': cookie, 'profile': profile, 'file': artifact.read_text(),
                                 'certificate': hashlib.sha256(certificate.read_bytes()).hexdigest()}))
    record.chmod(0o600)
    print('PASS: localhost operator access; created synthetic agent and saved file')
else:
    expected = json.loads(record.read_text())
    request = urllib.request.Request(base+'/api/session', headers={'Cookie': expected['cookie']})
    with opener.open(request, timeout=15) as response:
        session = json.load(response)
    assert session['canConfigure']
    assert expected['profile']['id'] in json.dumps(session)
    assert expected['profile']['name'] in json.dumps(session)
    assert (common.home()/'persistence-artifact.txt').read_text() == expected['file']
    assert hashlib.sha256(certificate.read_bytes()).hexdigest() == expected['certificate']
    print('PASS: agent, browser session, saved file and OpenShell certificate survived container recreation')

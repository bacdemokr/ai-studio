"""Per-agent OpenShell policy operations. Attendees choose only curated public reads.

CLI contract: NVIDIA/OpenShell fa0bfa490e42c87a74a70be6ebb40faee7fb8faa,
crates/openshell-cli/src/{main,run}.rs. Native runtime mapping comes from
OpenClaw 2026.9.4 `sandbox list --json`, never a guessed sandbox name.
"""
import hashlib
import json
import re
import shutil
import subprocess
import time

import agent_runtime as runtime
import ops_common as c

CATALOG = {
    'weather': {'title': 'Weather & city lookup', 'description': 'Read live weather and look up a city.',
                'hosts': ['api.open-meteo.com', 'geocoding-api.open-meteo.com']},
    'zurich': {'title': 'Zurich visitor guide', 'description': 'Read public pages for event and travel ideas.',
               'hosts': ['www.zuerich.com']},
    'search': {'title': 'Wikipedia search', 'description': 'Search public Wikipedia articles without an API key.',
               'hosts': ['en.wikipedia.org']},
    'github': {'title': 'Public GitHub API', 'description': 'Read public project information; no account credentials.',
               'hosts': ['api.github.com']},
}


def policy_document(approved=()):
    if not isinstance(approved, (list, tuple)) or any(x not in CATALOG for x in approved):
        raise ValueError('Choose an available public-read permission.')
    return {'version': 1, 'filesystem_policy': {'include_workdir': True,
            'read_only': ['/usr', '/lib', '/lib64', '/bin', '/sbin', '/proc', '/dev/urandom', '/etc', '/var/log'],
            'read_write': ['/sandbox', '/agent', '/tmp', '/dev/null']},
            'landlock': {'compatibility': 'best_effort'},
            'network_policies': {'bac_' + key: {'name': 'bac-' + key,
                'endpoints': [{'host': host, 'port': 443, 'protocol': 'rest', 'enforcement': 'enforce', 'access': 'read-only'} for host in CATALOG[key]['hosts']],
                'binaries': [{'path': '/usr/bin/curl'}]} for key in sorted(set(approved))}}


def default_path():
    return runtime.root() / 'policies/default-deny.json'


def plugin_config():
    return c.read_json(runtime.config_path(), {}).get('plugins', {}).get('entries', {}).get('openshell', {})


def configured():
    try:
        entry = plugin_config()
        config = entry.get('config', {})
        command = config.get('command', 'openshell')
        return bool(entry.get('enabled') and shutil.which(command) and config.get('mode') == 'mirror'
                    and config.get('autoProviders') is False and not config.get('providers')
                    and config.get('policy') == str(default_path())
                    and c.read_json(default_path(), {}) == policy_document())
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def shell(*args, timeout=35):
    config = plugin_config().get('config', {})
    command = [config.get('command', 'openshell')]
    for field, flag in [('gateway', '--gateway'), ('gatewayEndpoint', '--gateway-endpoint'), ('workspace', '--workspace')]:
        if config.get(field):
            command += [flag, config[field]]
    result = subprocess.run(command + list(args), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('OpenShell could not complete this request. Check the gateway and policy on the host.')
    return result.stdout


def runtimes(agent_id):
    if not re.fullmatch(r'bac-[a-f0-9]{24}(?:-r[0-4])?', agent_id):
        raise RuntimeError('Choose a personal BaC agent.')
    report = json.loads(runtime.cli('sandbox', 'list', '--json', timeout=35))
    prefix = 'agent:' + agent_id
    matches = [row for row in report.get('containers', []) if row.get('backendId') == 'openshell'
               and (row.get('sessionKey') == prefix or row.get('sessionKey', '').startswith(prefix + ':'))]
    for row in matches:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,62}', row.get('containerName', '')):
            raise RuntimeError('Invalid sandbox identity from the native runtime.')
    return matches


def network_rows(document):
    rows = []
    for key, rule in document.get('network_policies', {}).items():
        binaries = [b.get('path') for b in rule.get('binaries', [])]
        for ep in rule.get('endpoints', []):
            rows.append({'rule': key, 'host': ep.get('host'), 'port': ep.get('port'),
                         'access': ep.get('access'), 'protocol': ep.get('protocol'),
                         'enforcement': ep.get('enforcement'), 'binaries': binaries})
    return rows


def same_network(actual, expected):
    # Unknown provider/global entries must not silently count as our deny/allow policy.
    return actual.get('network_policies', {}) == expected.get('network_policies', {})


def read_policy(name):
    report = json.loads(shell('policy', 'get', name, '--full', '--output', 'json'))
    if report.get('sandbox') != name or not isinstance(report.get('policy'), dict):
        raise RuntimeError('OpenShell did not return this sandbox’s effective policy.')
    if report.get('policy_source') != 'sandbox':
        report['loaded'] = False
    else:
        revision = json.loads(shell('policy', 'get', name, '--rev', str(report['version']), '--output', 'json'))
        report['loaded'] = (revision.get('status') == 'loaded' and revision.get('version') == report['version']
                            and revision.get('active_version') == report['version'])
    return report


def public_logs(name):
    logs = shell('logs', name, '--since', '10m', '-n', '150')
    events = []
    for line in re.sub(r'\x1b\[[0-9;]*m', '', logs).splitlines():
        action = re.search(r'(?:action[=:]\s*"?(allow|deny)\b|\b(ALLOWED|DENIED)\b)', line, re.I)
        host = re.search(r'(?:host|dst_host|destination)[=:]\s*"?([a-zA-Z0-9.-]+)', line)
        if not action or not host:
            continue
        verdict = (action.group(1) or action.group(2)).lower()
        events.append({'action': 'allow' if verdict in ('allow', 'allowed') else 'deny',
                       'host': host.group(1), 'binary': '/usr/bin/curl' if '/usr/bin/curl' in line else 'other process',
                       'source': 'OpenShell policy log', 'fingerprint': hashlib.sha256(line.encode()).hexdigest()[:16]})
    return events[-30:][::-1]


def inspect(agent_id, protection, approved=()):
    result = {'mode': protection, 'checkedAt': time.time(), 'catalog': CATALOG,
              'requested': list(approved), 'rules': [], 'logs': [], 'sandboxes': [],
              'hostReady': configured(), 'status': 'standard' if protection == 'standard' else 'setup-required'}
    if protection == 'standard' or not result['hostReady']:
        return result
    entry = c.read_json(runtime.config_path(), {}).get('agents', {}).get('entries', {}).get(agent_id, {})
    if entry.get('sandbox', {}).get('mode') != 'all':
        result['status'] = 'awaiting-first-mission'
        return result
    try:
        found = runtimes(agent_id)
        if not found:
            result['status'] = 'awaiting-first-mission'
            return result
        snapshots = []
        for row in found:
            name = row['containerName']
            policy = read_policy(name)
            snapshots.append(policy)
            result['sandboxes'].append({'name': name, 'running': row.get('running'),
                                         'revision': policy.get('version'), 'loaded': policy['loaded'],
                                         'matchesRequest': same_network(policy['policy'], policy_document(list(approved)))})
            result['rules'] += [{**r, 'sandbox': name} for r in network_rows(policy['policy'])]
            try:
                result['logs'] += public_logs(name)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                result['logsUnavailable'] = True
        result['status'] = 'applied' if all(x['loaded'] and x['matchesRequest'] and x['running'] for x in result['sandboxes']) else 'needs-review'
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        result.update(status='unavailable', error='Could not verify the agent’s live sandbox. Check OpenShell on the host, then refresh.')
    return result


def apply(agent_id, approved):
    if not configured():
        raise RuntimeError('Run ./bac openshell enable on the host first.')
    found = runtimes(agent_id)
    if not found:
        raise RuntimeError('Run this protected agent once to create its sandbox, then approve access here.')
    directory = runtime.root() / 'policies'
    directory.mkdir(exist_ok=True, parents=True, mode=0o700)
    path = directory / (agent_id + '.json')
    c.write_json(path, policy_document(approved))  # JSON is also valid YAML; no extra parser dependency.
    for row in found:
        name = row['containerName']
        current = read_policy(name)
        if current.get('policy_source') != 'sandbox':
            raise RuntimeError('A host-wide policy controls this sandbox. Ask the host to review it.')
        shell('policy', 'set', name, '--policy', str(path), '--wait', timeout=75)
        applied = read_policy(name)
        if not applied['loaded'] or not same_network(applied['policy'], policy_document(approved)):
            raise RuntimeError('OpenShell has not confirmed the requested policy. Refresh to inspect what is applied.')
    return inspect(agent_id, 'openshell', approved)

"""Pinned OpenClaw installation, independent of application releases and vLLM."""
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import tarfile
import urllib.request

import agent_runtime as r
import ops_common as c

NODE = '24.16.0'


def install_node():
    system = {'Linux': 'linux', 'Darwin': 'darwin'}.get(platform.system())
    arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'x64'}.get(platform.machine())
    if not system or not arch:
        raise RuntimeError('This installer supports Linux/macOS on ARM64 or x64.')
    target = r.root() / 'node'
    if (target / 'bin/node').exists():
        return
    cache = r.root() / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    name = 'node-v' + NODE + '-' + system + '-' + arch + '.tar.gz'
    base = 'https://nodejs.org/dist/v' + NODE + '/'
    print('Installing private Node.js ' + NODE + ' (system Node is unchanged).', flush=True)
    checksums = urllib.request.urlopen(base + 'SHASUMS256.txt', timeout=60).read().decode()
    expected = next((line.split()[0] for line in checksums.splitlines() if line.split()[-1] == name), None)
    if not expected:
        raise RuntimeError('Official Node checksum not found.')
    archive = cache / name
    urllib.request.urlretrieve(base + name, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Node archive checksum mismatch.')
    with tarfile.open(archive) as tar:
        prefix = name[:-7]
        for member in tar.getmembers():
            parts = member.name.split('/')
            if parts[0] != prefix or '..' in parts or member.isdev() or member.islnk():
                raise RuntimeError('Unexpected Node archive member.')
            if member.issym():
                # Official npm/npx symlinks must remain within the extracted Node directory.
                link = (cache / member.name).parent / member.linkname
                if (cache / prefix).resolve() not in link.resolve().parents:
                    raise RuntimeError('Node archive symlink escapes its directory.')
        tar.extractall(cache)
    os.replace(cache / prefix, target)


def setup():
    c.initialize()
    r.root().mkdir(parents=True, exist_ok=True, mode=0o700)
    install_node()
    package = r.root() / 'package'
    package.mkdir(exist_ok=True)
    manifest = package / 'node_modules/openclaw/package.json'
    if not manifest.exists() or c.read_json(manifest).get('version') != r.VERSION:
        print('Installing OpenClaw ' + r.VERSION + '. This is independent from your LLM.', flush=True)
        c.run([r.root() / 'node/bin/npm', 'install', '--prefix', package, '--omit=dev', '--no-audit', '--no-fund', 'openclaw@' + r.VERSION], env=r.environment())
    with r.config_lock():
        if not r.config_path().exists():
            r.save_config(r.initial_config())
    r.register('bac-host', r.root() / 'host-workspace', {'name': 'BaC host', 'persona': 'guide', 'skills': ['documents']})
    print(r.cli('config', 'validate'))
    print('OpenClaw is installed. Run ./bac runtime start after starting your LLM.')


def start():
    c.require_systemd()
    if not r.config_path().exists():
        raise RuntimeError('Run ./bac runtime setup first.')
    print(r.cli('config', 'validate'))
    c.install_unit('bac-openclaw', [r.root() / 'package/node_modules/.bin/openclaw', 'gateway', 'run'],
                   {k: r.environment()[k] for k in ('PATH', 'OPENCLAW_STATE_DIR', 'OPENCLAW_CONFIG_PATH')})
    c.service('bac-openclaw', 'enable')
    c.service('bac-openclaw', 'restart')
    print('OpenClaw starting on loopback port 18789. ./bac runtime check shows readiness.')


def check():
    print(json.dumps(r.status(), indent=2))
    if r.config_path().exists():
        c.run([r.root() / 'package/node_modules/.bin/openclaw', 'config', 'validate'], env=r.environment())


def configure_telegram():
    from studio import Studio
    from telegram_bridge import telegram
    token = getpass.getpass('Dedicated BaC Telegram bot token (hidden): ').strip()
    if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{25,80}', token):
        raise RuntimeError('That does not look like a Telegram bot token.')
    studio = Studio(start_worker=False)
    path = studio.directory / 'telegram.json'
    previous = path.read_bytes() if path.exists() else None
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump({'token': token}, handle)
    os.chmod(path, 0o600)
    try:
        result = telegram(studio, 'getMe', {})
        webhook = telegram(studio, 'getWebhookInfo', {})
        if webhook.get('url'):
            raise RuntimeError('This bot has an existing webhook. Use a separate BaC bot; no webhook was changed.')
    except Exception:
        if previous is None:
            path.unlink()
        else:
            path.write_bytes(previous)
        raise
    print('Connected @' + result['username'] + '. Each participant pairs explicitly from their web workspace.')
    print('Use a dedicated bot; do not run another getUpdates consumer for it.')


def configure_search():
    key = getpass.getpass('Brave Search API key (hidden): ').strip()
    if not key or len(key) > 500 or '\n' in key:
        raise RuntimeError('Enter a valid API key.')
    with r.config_lock():
        config = c.read_json(r.config_path())
        if not config:
            raise RuntimeError('Run ./bac runtime setup first.')
        previous = json.loads(json.dumps(config))
        config.setdefault('plugins', {}).setdefault('entries', {})['brave'] = {
            'enabled': True, 'config': {'webSearch': {'apiKey': key, 'mode': 'web'}}}
        config['tools'].setdefault('web', {})['search'] = {'provider': 'brave', 'maxResults': 5}
        for agent in config['agents']['entries'].values():
            if 'bac-web' in agent.get('skills', []):
                allow = agent.setdefault('tools', {}).setdefault('allow', [])
                if 'web_search' not in allow:
                    allow.append('web_search')
        r.save_config(config)
        try:
            print(r.cli('config', 'validate'))
        except Exception:
            r.save_config(previous)
            raise
        (r.root() / 'search-enabled').touch(mode=0o600)
    c.service('bac-openclaw', 'restart')
    print('Brave Search is configured for agents with the Web explorer skill. Website reading and weather do not require this key.')


def openshell(action):
    if action == 'prove':
        from security_lab import prove
        return prove()
    if not shutil.which('openshell'):
        raise RuntimeError('Install the official OpenShell CLI and create a gateway first. See docs/live-studio.md. No sandbox was enabled.')
    c.run(['openshell', 'gateway', 'list'])
    if action == 'check':
        print(r.cli('sandbox', 'explain'))
        print(r.cli('sandbox', 'list'))
        return
    print(r.cli('plugins', 'install', '@openclaw/openshell-sandbox@2026.9.4', timeout=240))
    with r.config_lock():
        config = c.read_json(r.config_path())
        previous = json.loads(json.dumps(config))
        config['agents']['defaults']['sandbox'] = {'mode': 'all', 'backend': 'openshell', 'scope': 'session', 'workspaceAccess': 'rw'}
        config.setdefault('plugins', {}).setdefault('entries', {})['openshell'] = {'enabled': True, 'config': {'from': 'openclaw', 'mode': 'mirror'}}
        r.save_config(config)
        try:
            print(r.cli('config', 'validate'))
        except Exception:
            r.save_config(previous)
            raise
    c.service('bac-openclaw', 'restart')
    print('OpenShell backend configured in mirror mode. Run a mission, then ./bac openshell check to inspect the actual sandbox.')

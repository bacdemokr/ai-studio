"""Prime native image caches without a model, attendee identity or workspace upload.

OpenShell 0.1.4 has no cache-only command. A short-lived, default-deny sandbox
exercises its normal preparation path. Only this installation's labeled warmup
resources may be removed; ordinary agent sandboxes never enter this lifecycle.
"""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time


class Cancelled(Exception):
    pass


def invoke(command, env, timeout=20, stop=None):
    # Never expose CLI output in UI/errors: it can contain host configuration.
    with subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        deadline = time.monotonic() + timeout
        while True:
            cancelled = stop is not None and stop.is_set()
            if cancelled or time.monotonic() >= deadline:
                process.terminate()
                try:process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill();process.communicate()
                if cancelled:raise Cancelled()
                raise RuntimeError('OpenShell warmup timed out.')
            try:
                stdout, _ = process.communicate(timeout=.25)
                break
            except subprocess.TimeoutExpired:pass
        if process.returncode:
            raise RuntimeError('OpenShell warmup command failed.')
        return stdout


def settings():
    from agent_policy import configured, plugin_config, default_path
    from openshell_runtime import command, environment, lock
    import ops_common
    if not configured():return None
    config = plugin_config()['config']
    # Use the pinned binary directly for this maintenance resource. The normal
    # owned_openshell wrapper continues to require a real agent for all hires.
    prefix = [command()]
    for field, flag in [('gateway', '--gateway'), ('gatewayEndpoint', '--gateway-endpoint'), ('workspace', '--workspace')]:
        if config.get(field):prefix += [flag, config[field]]
    directory = ops_common.home() / 'openclaw'
    owner = hashlib.sha256(json.dumps([str(directory.resolve()), prefix[1:]], sort_keys=True).encode()).hexdigest()[:24]
    return {'prefix': prefix, 'env': environment(), 'directory': directory,
            'owner': owner, 'image': config.get('from') or lock()['images']['openclaw'], 'policy': str(default_path())}


def prepare(stop, publish):
    config = settings()
    if config is None:return 'not-configured'
    # Native routable sandbox names are limited to 19 characters. The full
    # installation identity stays in the ownership label, not in the name.
    owner = config['owner']; prefix = 'bac-wu-'
    selector = 'bac-warmup-owner=' + owner
    def call(*args, timeout=20, cancellable=True):
        return invoke(config['prefix'] + list(args), config['env'], timeout, stop if cancellable else None)
    def inventory(cancellable=True):
        data = json.loads(call('sandbox', 'list', '--selector', selector, '--output', 'json', cancellable=cancellable))
        if not isinstance(data, dict) or not isinstance(data.get('sandboxes'), list) or data.get('next_page_token') != '':
            raise RuntimeError('OpenShell warmup inventory was not verified.')
        rows = data['sandboxes']
        for row in rows:
            if (not isinstance(row, dict) or row.get('labels', {}).get('bac-warmup-owner') != owner
                    or not re.fullmatch(re.escape(prefix) + '[a-f0-9]{12}', row.get('name', ''))):
                raise RuntimeError('OpenShell warmup ownership was not verified.')
        return rows
    def cleanup():
        rows = inventory(cancellable=False)
        for row in rows:call('sandbox', 'delete', row['name'], cancellable=False)
        if rows:
            for attempt in range(5):
                if not inventory(cancellable=False):return
                time.sleep(1)
            raise RuntimeError('OpenShell warmup cleanup is pending.')

    config['directory'].mkdir(parents=True, exist_ok=True, mode=0o700)
    with (config['directory'] / '.warmup.lock').open('a') as handle:
        try:fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:return 'skipped'
        if stop.is_set():raise Cancelled()
        # Recover a warmup left by an interrupted app, under the same scope and
        # cross-process lock. No remembered PID or unscoped delete is used.
        cleanup()
        if stop.is_set():raise Cancelled()
        name = prefix + secrets.token_hex(6)
        try:
            publish('preparing')
            call('sandbox', 'create', '--name', name, '--from', config['image'],
                 '--policy', config['policy'], '--no-auto-providers', '--label', selector,
                 '--no-keep', '--detach', '--', 'sleep', '60', timeout=240)
            rows = inventory()
            if not any(row['name'] == name and row.get('phase', '').lower() == 'ready' for row in rows):
                raise RuntimeError('OpenShell warmup readiness was not confirmed.')
        finally:
            publish('cleaning')
            cleanup()
    return 'ready'


class StartupWarmup:
    def __init__(self, stop, prepare_fn=None, diagnostics=None):
        self.stop, self.prepare, self.diagnostics = stop, prepare_fn, diagnostics
        self.state = {'state': 'not-configured'}
        self.thread = None
        self.started = None

    def publish(self, state):
        elapsed = round((time.monotonic() - self.started) * 1000) if self.started is not None else 0
        self.state = {'state': state, 'elapsedMs': elapsed}
        if self.diagnostics:
            self.diagnostics.emit('openshell.warmup', status='done' if state in ('ready', 'not-configured', 'skipped') else
                                  'error' if state == 'unavailable' else 'cancelled' if state == 'cancelled' else 'running',
                                  elapsedMs=elapsed)

    def start(self):
        if self.thread is not None or not callable(self.prepare):return
        self.started = time.monotonic();self.publish('checking')
        self.thread = threading.Thread(target=self.run, name='openshell-image-warmup', daemon=True)
        self.thread.start()

    def run(self):
        try:state = self.prepare(self.stop, self.publish)
        except Cancelled:state = 'cancelled'
        except Exception:state = 'unavailable'
        self.publish(state)

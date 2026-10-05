"""Optional host model service. Never starts either application's agent stack."""
import argparse
import contextlib
import fcntl
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import signal
import select
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


class Model:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.directory = self.root / '.local-model'
        self.state_path = self.directory / 'state.json'
        self.unit = 'bac-studio-llm-' + hashlib.sha256(str(self.root).encode()).hexdigest()[:12] + '.service'

    @contextlib.contextmanager
    def locked(self):
        self.directory.mkdir(mode=0o700, exist_ok=True)
        with (self.directory / 'operation.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Another local model operation is running.') from None
            yield

    def configuration(self, name=None):
        path = self.root / 'local-model.json'
        if not path.exists():
            # Explicit model preparation can reuse the adjacent installation.
            # Ordinary Studio startup remains independent of the parent demo.
            parent = self.root.parent
            parent_config = parent / 'config.json'
            if name and parent.name == 'build-a-claw' and parent_config.is_file():
                source = json.loads(parent_config.read_text()).get('models', {}).get(name)
                if isinstance(source, dict):
                    weights = str((parent / source['path']).resolve())
                    data = {'models': {name: {
                        **source, 'model_path': weights,
                        'base_url': source.get('base_url', '').rstrip('/') + '/v1',
                        'argv': [arg.replace('{model_path}', weights).replace('{model_id}', source['model_id'])
                                 for arg in source.get('argv', [])],
                    }}}
                else:
                    raise RuntimeError('Local model is not configured in build-a-claw: ' + str(name))
            elif name:
                raise RuntimeError('No local model setup was found. Create local-model.json beside bac with the vLLM executable and downloaded Qwen weights paths. If using the build-a-claw installation, that directory must be present with runtime/restored/vllm/bin/vllm and models/qwen. You can still run ./bac start without a local model.')
            else:
                return None
        else:
            data = json.loads(path.read_text())
        if not name and not data.get('enabled', False):
            return None
        name = name or data.get('default_model', 'qwen')
        spec = data.get('models', {}).get(name)
        if not isinstance(spec, dict):
            raise RuntimeError('Local model is not configured: ' + str(name))
        url = urllib.parse.urlsplit(spec.get('base_url', ''))
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path != '/v1' or url.query or url.fragment or url.username or url.password:
            raise RuntimeError('Local model base_url must be http://127.0.0.1:PORT/v1.')
        model_id = spec.get('model_id')
        context = spec.get('context_window')
        wait = data.get('wait_seconds', 600)
        if not isinstance(model_id, str) or not model_id or type(context) is not int or not 8192 <= context <= 2000000:
            raise RuntimeError('Configure a model_id and valid context_window.')
        if type(wait) is not int or not 1 <= wait <= 3600:
            raise RuntimeError('wait_seconds must be between 1 and 3600.')
        args = spec.get('argv')
        env = spec.get('env', {})
        if not isinstance(spec.get('model_path'), str) or not Path(spec['model_path']).is_absolute():
            raise RuntimeError('local-model.json needs an absolute model_path pointing to downloaded weights.')
        if not isinstance(args, list) or not args or not all(isinstance(a, str) and a for a in args):
            raise RuntimeError('Configure a nonempty argv list.')
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise RuntimeError('Model env must contain string names and values.')
        return {**spec, 'name': name, 'wait_seconds': wait}

    def require_installation(self, spec):
        executable = Path(spec['argv'][0])
        weights = Path(spec['model_path'])
        missing = []
        if not executable.is_file() or not os.access(executable, os.X_OK):
            missing.append('vLLM executable: ' + str(executable))
        if not weights.is_dir() or not (weights / 'config.json').is_file():
            missing.append('downloaded model weights (including config.json): ' + str(weights))
        if missing:
            message = spec['name'].capitalize() + ' installation is missing or incomplete.\nRequired:\n  ' + '\n  '.join(missing)
            parent = self.root.parent
            if parent.name == 'build-a-claw' and any(parent == p or parent in p.parents for p in (executable, weights)):
                message += '\nThis setup uses the build-a-claw directory: ' + str(parent)
            message += '\nRestore/install these files, or update their paths in local-model.json. Nothing was stopped. Studio can still start with ./bac start.'
            raise RuntimeError(message)

    def state(self):
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def properties(self):
        result = subprocess.run(['systemctl', '--user', 'show', self.unit,
                                 '--property=InvocationID,ActiveState,LoadState'],
                                capture_output=True, text=True, timeout=10)
        return dict(row.split('=', 1) for row in result.stdout.splitlines() if '=' in row)

    def owned(self, state, properties):
        return bool(state.get('invocation_id')) and state.get('unit') == self.unit and state['invocation_id'] == properties.get('InvocationID')

    def request(self, spec, suffix, payload=None, timeout=5):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(spec['base_url'] + suffix,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type': 'application/json'})
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            with exc:
                detail = exc.read(2000).decode(errors='replace')
            raise RuntimeError('Model API HTTP ' + str(exc.code) + ': ' + detail) from None

    def probe(self, spec, inference=False, timeout=5):
        rows = self.request(spec, '/models', timeout=timeout).get('data', [])
        selected = next((row for row in rows if isinstance(row, dict) and row.get('id') == spec['model_id']), None)
        if selected is None:
            raise RuntimeError('The listener does not expose the configured model ' + spec['model_id'])
        limit = selected.get('max_model_len')
        if isinstance(limit, int) and limit < spec['context_window']:
            raise RuntimeError('The server context limit is smaller than the configured context_window.')
        if inference:
            result = self.request(spec, '/chat/completions', {
                'model': spec['model_id'], 'messages': [{'role': 'user', 'content': 'Say OK.'}],
                'max_tokens': 8, 'temperature': 0}, timeout=timeout)
            if not result.get('choices'):
                raise RuntimeError('The model did not return an inference result.')

    def listening(self, spec):
        url = urllib.parse.urlsplit(spec['base_url'])
        try:
            with socket.create_connection((url.hostname, url.port or 80), timeout=1):
                return True
        except OSError:
            return False

    def wait(self, spec, managed=False):
        deadline = time.monotonic() + spec['wait_seconds']
        next_notice = 0
        error = None
        while True:
            if managed:
                props = self.properties()
                if not self.owned(self.state(), props) or props.get('ActiveState') in ('failed', 'inactive'):
                    raise RuntimeError('Local model service exited. Run ./bac vllm --logs for its startup log.')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Local model readiness timed out: ' + str(error))
            try:
                self.probe(spec, inference=True, timeout=min(30, remaining))
                return
            except (OSError, ValueError, RuntimeError) as exc:
                error = exc
            now = time.monotonic()
            if now >= next_notice:
                print('Waiting for ' + spec['name'] + ' inference (' + str(max(0, int(deadline-now))) + 's remaining)…', flush=True)
                next_notice = now + 15
            time.sleep(min(2, max(0, deadline-time.monotonic())))

    def start(self, name=None):
        (self.directory / 'attempt.json').unlink(missing_ok=True)
        spec = self.configuration(name)
        if spec is None:
            (self.directory / 'connection.json').unlink(missing_ok=True)
            print('Using an external model. Connect it in Settings → Model.', flush=True)
            return
        state = self.state()
        props = self.properties()
        managed = self.owned(state, props)
        active = props.get('ActiveState') in ('active', 'activating', 'deactivating')
        if managed and active and state.get('spec') != spec:
            raise RuntimeError('A different model configuration is running. Run ./bac vllm --stop before switching.')
        newly_started = False
        if managed and active:
            print('Reusing the Studio-owned model service.', flush=True)
        elif active:
            # A missing/stale receipt does not prevent read-only reuse. Do not
            # adopt the invocation or acquire permission to stop it by probing.
            try:
                self.probe(spec)
            except (OSError, ValueError, RuntimeError) as exc:
                raise RuntimeError(
                    'An existing model service has no matching local launch record, and the configured model API is not ready or does not match. '
                    'Nothing was stopped. Run ./bac vllm --status and ./bac vllm --logs; '
                    'if the model is still loading, retry ./bac vllm after it is ready.\n' + str(exc)) from None
            print('Reusing the verified model API without taking ownership of the existing service; it will be left running.', flush=True)
        elif self.listening(spec):
            # An external listener must already identify itself; never adopt or stop it.
            self.probe(spec)
            print('Reusing an external ' + spec['name'] + ' server; Studio will leave it running.', flush=True)
            managed = False
        else:
            self.require_installation(spec)
            if subprocess.run(['systemctl', '--user', 'show-environment'], capture_output=True, timeout=10).returncode:
                raise RuntimeError('A systemd user session is required to launch local vLLM.')
            subprocess.run(['systemctl', '--user', 'reset-failed', self.unit], capture_output=True, timeout=10)
            command = ['systemd-run', '--user', '--unit=' + self.unit,
                       '--property=Type=exec', '--property=KillMode=control-group',
                       '--property=TimeoutStopSec=60', '--property=Restart=no',
                       '--property=WorkingDirectory=' + str(self.root)]
            for key, value in spec.get('env', {}).items():
                command.append('--setenv=' + key + '=' + value)
            command.extend(['--', *spec['argv']])
            print('Starting ' + spec['name'] + ' on this PC…', flush=True)
            subprocess.run(command, check=True, timeout=30)
            props = self.properties()
            if not props.get('InvocationID'):
                raise RuntimeError('Could not record the model service identity. Run ./bac vllm --logs.')
            write(self.state_path, {'unit': self.unit, 'invocation_id': props['InvocationID'], 'spec': spec})
            write(self.directory / 'attempt.json', self.state())
            newly_started = managed = True
        try:
            self.wait(spec, managed)
            write(self.directory / 'connection.json', {
                'provider': 'local', 'baseUrl': spec['base_url'], 'model': spec['model_id'],
                'contextWindow': spec['context_window'], 'apiKey': '', 'requiresKey': False})
        except BaseException:
            if newly_started:
                try:
                    result = subprocess.run(['journalctl', '--user', '-u', self.unit, '-n', '12', '--no-pager'],
                        capture_output=True, text=True, timeout=5)
                    if isinstance(result.stdout, str) and result.stdout.strip():
                        print('Last vLLM startup messages:\n' + result.stdout[-5000:], file=sys.stderr)
                except (OSError, subprocess.SubprocessError):
                    pass
                self.stop()
            raise
        print('Local model ready: ' + spec['base_url'] + ' · ' + spec['model_id'], flush=True)

    def stop(self):
        state = self.state()
        if state and self.owned(state, self.properties()):
            subprocess.run(['systemctl', '--user', 'stop', self.unit], check=True, timeout=75)
            print('Studio-owned local model stopped.', flush=True)
        else:
            print('No Studio-owned model to stop; external model servers are left running.', flush=True)
        self.state_path.unlink(missing_ok=True)
        (self.directory / 'attempt.json').unlink(missing_ok=True)

    def process_matches(self, pid, spec):
        """Match the complete configured command, allowing a Python shebang prefix."""
        try:
            path = Path('/proc') / str(pid)
            if path.stat().st_uid != os.getuid():
                return False
            args = [part.decode() for part in (path / 'cmdline').read_bytes().split(b'\0') if part]
            wanted = spec['argv']
            return len(args) >= len(wanted) and args[-len(wanted):] == wanted
        except (OSError, UnicodeError):
            return False

    def stop_configured_process(self, spec):
        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            raise RuntimeError('Safe external-server restart requires Linux pidfd support.')
        matches = [int(path.name) for path in Path('/proc').iterdir()
                   if path.name.isdigit() and self.process_matches(int(path.name), spec)]
        if not matches:
            if self.listening(spec):
                raise RuntimeError('The model port is occupied by a process whose command does not match local-model.json. Nothing was killed.')
            return
        if len(matches) != 1:
            raise RuntimeError('More than one process matches the model command. Nothing was killed.')
        pid = matches[0]
        handles = []
        try:
            fd = os.pidfd_open(pid)
            handles.append(fd)
            if not self.process_matches(pid, spec):
                raise RuntimeError('Model process changed before restart. Nothing was killed.')
            # Capture descendant identities before signalling the parent. pidfds
            # remain bound to those processes even if numeric PIDs are reused.
            parents = {}
            for path in Path('/proc').iterdir():
                if not path.name.isdigit():
                    continue
                try:
                    fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
                    parents[int(path.name)] = int(fields[1])
                except (OSError, ValueError, IndexError):
                    pass
            family = {pid}
            while True:
                children = {child for child, parent in parents.items() if parent in family} - family
                if not children:
                    break
                family.update(children)
            for child in family - {pid}:
                child_fd = None
                try:
                    child_fd = os.pidfd_open(child)
                    fields = (Path('/proc') / str(child) / 'stat').read_text().rsplit(')', 1)[1].split()
                    if int(fields[1]) != parents[child]:
                        os.close(child_fd)
                        continue
                    handles.append(child_fd)
                except (OSError, ValueError, IndexError):
                    if child_fd is not None and child_fd not in handles:
                        try: os.close(child_fd)
                        except OSError: pass
            print('Stopping the configured model server and its workers…', flush=True)
            for descriptor in handles:
                try: signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                except ProcessLookupError: pass
            poller = select.poll()
            for descriptor in handles:
                poller.register(descriptor, select.POLLIN)
            pending = set(handles)
            deadline = time.monotonic() + 15
            while pending and time.monotonic() < deadline:
                pending.difference_update(fd for fd, _ in poller.poll(200))
            for descriptor in pending:
                try: signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                except ProcessLookupError: pass
            deadline = time.monotonic() + 10
            while pending and time.monotonic() < deadline:
                pending.difference_update(fd for fd, _ in poller.poll(200))
            if pending:
                raise RuntimeError('Model processes did not exit; replacement was not started.')
        finally:
            for descriptor in handles:
                os.close(descriptor)

    def restart(self, name='qwen'):
        spec = self.configuration(name)
        self.require_installation(spec)
        if subprocess.run(['systemctl', '--user', 'show-environment'], capture_output=True, timeout=10).returncode:
            raise RuntimeError('A systemd user session is required to restart vLLM. Nothing was stopped.')
        state = self.state()
        props = self.properties()
        if self.owned(state, props):
            self.stop()
        elif props.get('ActiveState') in ('active', 'activating', 'deactivating'):
            # Killing a matching process cannot establish ownership of its
            # systemd unit and may race its replacement or remaining workers.
            raise RuntimeError(
                'An existing model service has no matching local launch record. '
                'Restart was cancelled before stopping anything. Run ./bac vllm to reuse the model '
                'after it is ready, or inspect ./bac vllm --status and ./bac vllm --logs.')
        else:
            self.stop_configured_process(spec)
        deadline = time.monotonic() + 15
        while self.listening(spec):
            if time.monotonic() >= deadline:
                raise RuntimeError('Model port did not become free; replacement was not started.')
            time.sleep(.2)
        self.start(name)
        self.commit()

    def commit(self):
        (self.directory / 'attempt.json').unlink(missing_ok=True)

    def rollback(self):
        attempt = self.directory / 'attempt.json'
        if attempt.exists() and self.owned(json.loads(attempt.read_text()), self.properties()):
            self.stop()
        attempt.unlink(missing_ok=True)

    def status(self):
        state = self.state()
        if state and self.owned(state, self.properties()):
            print('Local model: Studio-owned · ' + self.properties().get('ActiveState', 'unknown'))
        else:
            spec = self.configuration()
            if not spec:
                print('Local model: not managed (external connection)')
                return
            try:
                self.probe(spec)
                print('Local model: external server ready at ' + spec['base_url'])
            except (OSError, ValueError, RuntimeError):
                print('Local model: stopped or unavailable')

    def logs(self):
        subprocess.run(['journalctl', '--user', '-u', self.unit, '-n', '80', '--no-pager'], check=True, timeout=15)

    def connect(self, studio_url):
        if not studio_url:
            result = subprocess.run(['docker', 'compose', '-f', 'compose.yaml', 'config', '--format', 'json'],
                cwd=self.root, check=True, capture_output=True, text=True, timeout=15)
            port = int(json.loads(result.stdout)['services']['studio']['environment']['PORT'])
            if not 1024 <= port <= 65535:
                raise RuntimeError('Invalid Studio port.')
            studio_url = 'http://127.0.0.1:' + str(port)
        url = urllib.parse.urlsplit(studio_url)
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path not in ('', '/') or url.username or url.password or url.query or url.fragment:
            raise RuntimeError('Studio URL must be http://127.0.0.1:PORT.')
        connection = json.loads((self.directory / 'connection.json').read_text())
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
        base = studio_url.rstrip('/')
        headers = {'Content-Type': 'application/json', 'Origin': base, 'X-BaC-Key-Session': 'local-launcher'}

        def request(path, payload=None):
            req = urllib.request.Request(base + '/api/' + path,
                data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            try:
                with opener.open(req, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                with exc:
                    detail = exc.read(2000).decode(errors='replace')
                raise RuntimeError('Studio API HTTP ' + str(exc.code) + ': ' + detail) from None

        session = request('session')
        if not session.get('canConfigure'):
            raise RuntimeError('The Studio endpoint did not grant local operator access.')
        headers['X-BaC-CSRF'] = session['csrf']
        print('Connecting the local model for Stages 1 and 2…', flush=True)
        request('settings', {**connection, 'section': 'model', 'verifyConnection': True})
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if request('runtime').get('ready'):
                print('Studio and local model connected.', flush=True)
                return
            time.sleep(2)
        raise RuntimeError('Model settings were saved, but the agent runtime did not become ready. Run ./bac vllm --logs.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'restart', 'stop', 'status', 'logs', 'rollback', 'commit', 'connect'])
    parser.add_argument('--model')
    parser.add_argument('--studio-url')
    args = parser.parse_args()
    model = Model()
    if args.action in ('status', 'logs'):
        getattr(model, args.action)()
        return
    with model.locked():
        if args.action == 'start':
            model.start(args.model)
        elif args.action == 'restart':
            model.restart(args.model or 'qwen')
        elif args.action == 'connect':
            model.connect(args.studio_url)
        else:
            getattr(model, args.action)()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('vLLM could not complete the requested operation:\n' + str(exc), file=sys.stderr)
        print('Studio is unchanged. You can run ./bac start without local vLLM.', file=sys.stderr)
        sys.exit(1)

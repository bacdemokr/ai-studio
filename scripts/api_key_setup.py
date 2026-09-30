"""Validate the install-local Stage 3 key before starting services."""
import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

from team_models import BASE_URL, MODELS, LABELS, valid_model, save_connection, credential_path


class InvalidKey(Exception):
    pass


class ServiceUnavailable(Exception):
    pass


def request(key, path, payload=None):
    req = urllib.request.Request(BASE_URL + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        if status in (401, 403):
            raise InvalidKey('The inference API rejected this key.') from None
        raise ServiceUnavailable(f'Inference API returned HTTP {status}. Try ./bac start again later; the key was not changed.') from None
    except (OSError, ValueError, urllib.error.URLError):
        raise ServiceUnavailable('Could not validate the key with the inference API. Check the connection and try ./bac start again; the key was not changed.') from None


def validate(key):
    if not key or any(c.isspace() for c in key) or not key.isascii():
        raise InvalidKey('api.cfg needs one API key on a single line.')
    catalog = request(key, '/models')
    ids = {m['id'] for m in catalog.get('data', []) if isinstance(m, dict) and valid_model(m.get('id'))}
    if not set(MODELS).issubset(ids):
        raise InvalidKey('This key does not provide the configured team models.')
    result = request(key, '/chat/completions', {'model': MODELS[0], 'messages': [
        {'role': 'user', 'content': 'Reply OK.'}], 'max_tokens': 16, 'stream': False})
    if not result.get('choices'):
        raise ServiceUnavailable('Inference returned no completion. Try ./bac start again; the key was not changed.')
    return [{'id': model, 'label': dict(zip(MODELS, LABELS)).get(model, model)} for model in sorted(ids)]


def setup(path, interactive=None):
    key = path.read_text().strip()
    interactive = sys.stdin.isatty() if interactive is None else interactive
    while True:
        try:
            models = validate(key)
            break
        except InvalidKey as error:
            print(str(error), flush=True)
            if not interactive:
                raise InvalidKey('Put a valid inference API key in api.cfg, then run ./bac start in a terminal.') from None
            try:
                key = getpass.getpass('Inference API key (hidden; saved in api.cfg): ').strip()
            except (EOFError, KeyboardInterrupt):
                raise InvalidKey('Key setup cancelled. Services were not restarted.') from None
    # Keep the original file inode: api.cfg is a single-file bind mount.
    with path.open('w') as stream:
        os.chmod(path, 0o600)
        stream.write(key + '\n')
    save_connection(key, models)
    # The setup helper runs as root; the studio runs as uid 10001.
    if os.geteuid() == 0:
        saved = credential_path()
        os.chown(saved.parent, 10001, 10001)
        os.chown(saved, 10001, 10001)
    print('Inference API key verified. Stage 3 is configured.', flush=True)


if __name__ == '__main__':
    try:
        setup(Path(sys.argv[1]))
    except (InvalidKey, ServiceUnavailable, OSError):
        error = sys.exc_info()[1]
        print(str(error) if isinstance(error, (InvalidKey, ServiceUnavailable)) else
              'Could not read or save api.cfg. Check its file permissions.', file=sys.stderr)
        sys.exit(1)

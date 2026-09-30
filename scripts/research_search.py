"""Pinned, keyless search for standard research agents; no sandbox policy changes."""
from pathlib import Path

VERSION = '2026.7.1'
PACKAGE = '@openclaw/parallel-plugin'


def configure(config, runtime_root):
    plugin = Path(runtime_root)/'package/node_modules'/PACKAGE
    import json
    if json.loads((plugin/'package.json').read_text()).get('version') != VERSION:
        raise RuntimeError('Parallel search plugin version mismatch. Rebuild the runtime image.')
    plugins = config.setdefault('plugins', {})
    paths = plugins.setdefault('load', {}).setdefault('paths', [])
    if str(plugin) not in paths:paths.append(str(plugin))
    plugins.setdefault('entries', {})['parallel'] = {'enabled': True}
    if 'allow' in plugins and 'parallel' not in plugins['allow']:plugins['allow'].append('parallel')
    config.setdefault('tools', {}).setdefault('web', {})['search'] = {
        'enabled': True, 'provider': 'parallel-free', 'maxResults': 3, 'timeoutSeconds': 20}
    return config

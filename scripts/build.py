#!/usr/bin/env python3
"""Build the editable UI fragment into a standalone page with a bundled 3D renderer."""
from pathlib import Path
import base64
import json
import os
import re
import argparse
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true", help="Validate an app patch without writing to the source checkout")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
# Reject accidental JavaScript/file overwrites before publishing the generated page.
for stylesheet in (ROOT / 'src').glob('*.css'):
    css = re.sub(r'/\*.*?\*/', '', stylesheet.read_text(encoding='utf-8'), flags=re.S)
    if re.search(r'^\s*(?://|(?:const|let|var|function|async function|import|export)\s)', css, re.M):
        raise ValueError(f'JavaScript found in stylesheet: {stylesheet.name}')
    if not css.strip() or css.count('{') != css.count('}'):
        raise ValueError(f'Empty or unbalanced stylesheet: {stylesheet.name}')
fragment = (ROOT / 'src/bac-planner.html').read_text(encoding='utf-8')
crew_catalog = json.loads((ROOT / 'src/crew-catalog.json').read_text(encoding='utf-8'))
fragment = fragment.replace('/* CREW_CATALOG */', json.dumps(crew_catalog).replace('</', '<\\/'))
campus = (ROOT / 'src/campus.html').read_text(encoding='utf-8')
studio = (ROOT / 'src/studio.html').read_text(encoding='utf-8').replace('/* STUDIO_CSS */', (ROOT / 'src/studio.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-rooms.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-sound.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-artifacts.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-controls.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-events.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-scenarios.css').read_text(encoding='utf-8'))
campus = campus.replace('<div class="campus-layout">', studio + '\n<div class="campus-layout">')
campus = campus.replace('/* CAMPUS_CSS */', (ROOT / 'src/campus.css').read_text(encoding='utf-8'))
fragment = fragment.replace('<!-- AGENT_CAMPUS -->', campus)
vendor = (ROOT / 'src/vendor/three-r180.cjs').read_text(encoding='utf-8')
workshop_art = 'data:image/png;base64,' + base64.b64encode((ROOT / 'src/assets/build-a-claw-workshop.png').read_bytes()).decode('ascii')
world_scene = (ROOT / 'src/world-scene.js').read_text(encoding='utf-8').replace('__WORKSHOP_ART_DATA_URL__', workshop_art)
world_scene = world_scene.replace('/* AGENT_CHARACTER */', (ROOT / 'src/agent-character.js').read_text(encoding='utf-8')).replace('/* WORLD_ROOMS */', (ROOT / 'src/world-rooms.js').read_text(encoding='utf-8').replace('/* LOUNGE_LIFE */', (ROOT / 'src/world-lounge.js').read_text(encoding='utf-8'))).replace('/* WORLD_NAVIGATION */', (ROOT / 'src/world-navigation.js').read_text(encoding='utf-8'))
world_scene = world_scene.replace('/* WORLD_CREW_EXCHANGE */', (ROOT / 'src/world-crew-exchange.js').read_text(encoding='utf-8'))
world_scene = world_scene.replace('/* WORLD_PROTECTION */', (ROOT / 'src/world-protection.js').read_text(encoding='utf-8'))
world_scene = world_scene.replace('/* WORLD_ROUNDTABLE */', (ROOT / 'src/world-roundtable.js').read_text(encoding='utf-8'))
campus_js = '(function(){const exports={};\n' + vendor + '\nconst THREE=exports;\n' + (ROOT / 'src/campus.js').read_text(encoding='utf-8').replace('/* STUDIO_SOUND */', (ROOT / 'src/studio-sound.js').read_text(encoding='utf-8')).replace('/* WORLD_SCENE */', world_scene) + '\n})();'
fragment = fragment.replace('<!-- CAMPUS_SCRIPT -->', '<script>' + campus_js.replace('</script', '<\\/script') + '</script>')
studio_js = (ROOT / 'src/studio.js').read_text(encoding='utf-8')
# Keep assembly explicit and fail on missing/duplicate include markers.
for module in ('json', 'compare', 'settings', 'crew', 'telemetry',
               'events', 'event-team', 'scenarios', 'world', 'surfaces', 'chat', 'rooms', 'identity', 'safety', 'policies'):
    marker = '/* STUDIO_' + module.upper() + ' */'
    if studio_js.count(marker) != 1:
        raise ValueError('Expected one include marker: ' + marker)
    studio_js = studio_js.replace(marker, (ROOT / ('src/studio-' + module + '.js')).read_text(encoding='utf-8'))

fragment = fragment.replace('<!-- STUDIO_SCRIPT -->', '<script>' + studio_js.replace('</script', '<\\/script') + '</script>')
fragment = fragment.replace('<!-- NVIDIA_THEME -->', '<style>\n' + (ROOT / 'src/nvidia-theme.css').read_text(encoding='utf-8') + '\n</style>')
version = os.environ.get('BAC_DEMO_VERSION', 'local-preview')
page = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Build your agent, explore skills, and collaborate with a team of specialists.">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; frame-src 'self' blob:; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>NVIDIA Build-a-Claw — Agent Studio</title>
<style>
:root{color-scheme:dark;background:#0c0c0c;--browser-viewport-height:100vh}
@supports(height:100dvh){:root{--browser-viewport-height:100dvh}}
body{margin:0;padding:0;width:100%;max-width:none}
</style>
</head><body>
'''+fragment+'''
<noscript>Enable JavaScript to use the interactive planner.</noscript>
</body></html>
'''
if args.check:
    required = ['scripts/serve.py', 'scripts/studio.py', 'scripts/container_runtime.py',
                'scripts/agent_runtime.py', 'skills/bac-event-page/SKILL.md',
                'runtime/research-guard/index.mjs', 'runtime/research-guard/openclaw.plugin.json']
    runtime_source = (ROOT / 'scripts/agent_runtime.py').read_text()
    required += ['skills/bac-' + name + '/SKILL.md'
                 for name in re.findall(r"project_skill\('([^']+)'\)", runtime_source)]
    for member in crew_catalog[:4]:
        required += ['crew/' + member['id'] + '/' + name
                     for name in ('SOUL.md', 'IDENTITY.md', 'AGENTS.md')]
    for name in required:
        if not (ROOT / name).is_file():
            raise ValueError('Incomplete app bundle: missing ' + name)
    # Validate the same assembled page we will serve; source modules contain
    # include markers and cannot all be checked as independent scripts.
    for source in (ROOT / 'scripts').glob('*.py'):
        compile(source.read_bytes(), str(source), 'exec')
    with tempfile.TemporaryDirectory(prefix='bac-app-check-') as folder:
        for index, script in enumerate(re.findall(r'<script\b[^>]*>(.*?)</script>', page, re.S | re.I)):
            target = Path(folder) / f'inline-{index}.js'
            target.write_text(script, encoding='utf-8')
            subprocess.run(['node', '--check', str(target)], check=True)
        for source in (ROOT / 'scripts').glob('*.mjs'):
            subprocess.run(['node', '--check', str(source)], check=True)
    print('App files, Python and bundled JavaScript validated.')
else:
    (ROOT / 'app').mkdir(exist_ok=True)
    (ROOT / 'app/index.html').write_text(page, encoding='utf-8')
    (ROOT / 'app/version.json').write_text(json.dumps({'version': version}) + '\n', encoding='utf-8')
    print('Built app/index.html (bundled Three.js; no runtime downloads).')

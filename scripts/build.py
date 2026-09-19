#!/usr/bin/env python3
"""Build the editable UI fragment into a standalone page with a bundled 3D renderer."""
from pathlib import Path
from html import escape
import base64
import json
import os

ROOT = Path(__file__).resolve().parents[1]
fragment = (ROOT / 'src/bac-planner.html').read_text(encoding='utf-8')
playground = (ROOT / 'src/playground.html').read_text(encoding='utf-8')
playground = playground.replace('/* PLAYGROUND_CSS */', (ROOT / 'src/playground.css').read_text(encoding='utf-8'))
playground = playground.replace('/* SKILL_TOOLS_JS */', (ROOT / 'src/skill-tools.js').read_text(encoding='utf-8'))
playground = playground.replace('/* PLAYGROUND_JS */', (ROOT / 'src/playground.js').read_text(encoding='utf-8'))
fragment = fragment.replace('<!-- SKILL_PLAYGROUND -->', playground)
campus = (ROOT / 'src/campus.html').read_text(encoding='utf-8')
studio = (ROOT / 'src/studio.html').read_text(encoding='utf-8').replace('/* STUDIO_CSS */', (ROOT / 'src/studio.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-rooms.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-sound.css').read_text(encoding='utf-8') + '\n' + (ROOT / 'src/studio-events.css').read_text(encoding='utf-8'))
campus = campus.replace('<div class="campus-layout">', studio + '\n<div class="campus-layout">')
campus = campus.replace('/* CAMPUS_CSS */', (ROOT / 'src/campus.css').read_text(encoding='utf-8'))
fragment = fragment.replace('<!-- AGENT_CAMPUS -->', campus)
vendor = (ROOT / 'src/vendor/three-r180.cjs').read_text(encoding='utf-8')
workshop_art = 'data:image/png;base64,' + base64.b64encode((ROOT / 'src/assets/build-a-claw-workshop.png').read_bytes()).decode('ascii')
world_scene = (ROOT / 'src/world-scene.js').read_text(encoding='utf-8').replace('__WORKSHOP_ART_DATA_URL__', workshop_art)
world_scene = world_scene.replace('/* AGENT_CHARACTER */', (ROOT / 'src/agent-character.js').read_text(encoding='utf-8')).replace('/* WORLD_ROOMS */', (ROOT / 'src/world-rooms.js').read_text(encoding='utf-8').replace('/* LOUNGE_LIFE */', (ROOT / 'src/world-lounge.js').read_text(encoding='utf-8'))).replace('/* WORLD_NAVIGATION */', (ROOT / 'src/world-navigation.js').read_text(encoding='utf-8'))
campus_js = '(function(){const exports={};\n' + vendor + '\nconst THREE=exports;\n' + (ROOT / 'src/campus.js').read_text(encoding='utf-8').replace('/* STUDIO_SOUND */', (ROOT / 'src/studio-sound.js').read_text(encoding='utf-8')).replace('/* WORLD_SCENE */', world_scene) + '\n})();'
fragment = fragment.replace('<!-- CAMPUS_SCRIPT -->', '<script>' + campus_js.replace('</script', '<\\/script') + '</script>')
studio_js = (ROOT / 'src/studio.js').read_text(encoding='utf-8').replace('/* STUDIO_EVENTS */', (ROOT / 'src/studio-events.js').read_text(encoding='utf-8')).replace('/* STUDIO_CREW */', (ROOT / 'src/studio-crew.js').read_text(encoding='utf-8')).replace('/* STUDIO_WORLD */', (ROOT / 'src/studio-world.js').read_text(encoding='utf-8')).replace('/* STUDIO_ROOMS */', (ROOT / 'src/studio-rooms.js').read_text(encoding='utf-8')).replace('/* STUDIO_SAFETY */', (ROOT / 'src/studio-safety.js').read_text(encoding='utf-8')).replace('/* STUDIO_POLICIES */', (ROOT / 'src/studio-policies.js').read_text(encoding='utf-8'))
fragment = fragment.replace('<!-- STUDIO_SCRIPT -->', '<script>' + studio_js.replace('</script', '<\\/script') + '</script>')
fragment = fragment.replace('<!-- NVIDIA_THEME -->', '<style>\n' + (ROOT / 'src/nvidia-theme.css').read_text(encoding='utf-8') + '\n</style>')
version = os.environ.get('BAC_DEMO_VERSION', 'local-preview')
label = version if version == 'local-preview' else version[:12]
fragment = fragment.replace('<!-- BUILD_VERSION -->', '<span class="demo-label" title="Application build">Build ' + escape(label) + '</span>')
page = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Build your agent, explore skills, and plan a BaC event with a crew.">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; frame-src 'self' blob:; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>NVIDIA Build a Claw — Agent Studio</title>
<style>
:root{color-scheme:dark;background:#0c0c0c}
body{margin:0;padding:0;max-width:1600px;margin-inline:auto}
</style>
</head><body>
'''+fragment+'''
<noscript>Enable JavaScript to use the interactive planner.</noscript>
</body></html>
'''
(ROOT / 'app').mkdir(exist_ok=True)
(ROOT / 'app/index.html').write_text(page, encoding='utf-8')
(ROOT / 'app/version.json').write_text(json.dumps({'version': version}) + '\n', encoding='utf-8')
print('Built app/index.html (bundled Three.js; no runtime downloads).')

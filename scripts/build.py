#!/usr/bin/env python3
"""Build the editable UI fragment into a dependency-free standalone page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fragment = (ROOT / 'src/bac-planner.html').read_text(encoding='utf-8')
playground = (ROOT / 'src/playground.html').read_text(encoding='utf-8')
playground = playground.replace('/* PLAYGROUND_CSS */', (ROOT / 'src/playground.css').read_text(encoding='utf-8'))
playground = playground.replace('/* PLAYGROUND_JS */', (ROOT / 'src/playground.js').read_text(encoding='utf-8'))
fragment = fragment.replace('<!-- SKILL_PLAYGROUND -->', playground)
fragment = fragment.replace('<!-- NVIDIA_THEME -->', '<style>\n' + (ROOT / 'src/nvidia-theme.css').read_text(encoding='utf-8') + '\n</style>')
page = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Build your agent, explore skills, and plan a BaC event with a crew.">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>BaC Crew — Agent Playground</title>
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
print('Built app/index.html (no third-party runtime dependencies).')

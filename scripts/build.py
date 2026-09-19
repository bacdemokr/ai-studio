#!/usr/bin/env python3
"""Build the editable UI fragment into a dependency-free standalone page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fragment = (ROOT / 'src/bac-planner.html').read_text(encoding='utf-8')
# The inline preview host supplies this decorative icon. Keep the export offline.
fragment = fragment.replace('<i data-lucide="sprout" aria-hidden="true"></i>', '<span aria-hidden="true">B</span>')
page = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Interactive BaC event planning prototype with agent personas, skills and handoffs.">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>BaC Crew — Virtual Event Planner</title>
<style>
:root{color-scheme:light dark;background:light-dark(#edf1eb,#111816)}
body{margin:0;padding:24px;max-width:1440px;margin-inline:auto}
@media(max-width:600px){body{padding:8px}}
</style>
</head><body>
'''+fragment+'''
<noscript>Enable JavaScript to use the interactive planner.</noscript>
</body></html>
'''
(ROOT / 'app').mkdir(exist_ok=True)
(ROOT / 'app/index.html').write_text(page, encoding='utf-8')
print('Built app/index.html (no third-party runtime dependencies).')

"""Attach verified HTML outputs to the chat that produced them."""
import hashlib
import os
import re
from pathlib import Path

DEMO_CODING_INSTRUCTIONS = (
    '\nDEMO CODING PACE: applies when this assignment requires implementation. '
    'Prioritize a usable desktop demo quickly. Implement the requested core behavior with simple readable code, '
    'one clear layout and native browser controls. No mobile layouts, mobile breakpoints, touch controls or mobile testing. '
    'Do not add optional features, elaborate animations, themes, settings, persistence, frameworks or multiple files '
    'unless the current user explicitly requires them. A useful small result is preferable to an unfinished polished one. '
    'Read only the assigned inputs and relevant existing source. For a new page, aim to write the complete compact '
    'implementation once, including the essential behavior; do not deliberately save a skeleton that needs many edits. '
    'If the model output budget requires smaller writes, keep a usable saved file and add only missing requirements. '
    'Do one focused static check of the core flow, controls, initialization and obvious errors while composing. '
    'After a successful save, return immediately unless a specific requirement is missing or a concrete defect was found. '
    'Do not reread solely to confirm a save, generate alternate versions, refactor working code or run cosmetic polish loops. '
    'Fix identified functional defects with targeted edits; do not rewrite the whole page for a small change. '
    'A successful write confirms delivery, not browser execution. Never claim unperformed testing. '
    'Keep the final handoff under 80 words with the file path and material limitations; code and deliverable content '
    'are NOT subject to this summary limit. Never drop explicit requirements to fit a word or character target.\n'
)

PAGE_INSTRUCTIONS = (
    '\nIf the user asks you to create a webpage, produce a complete self-contained HTML '
    'file in artifacts/ with inline CSS and JavaScript, rather than only describing it. '
    'The preview has no network access: use inline SVG or data images and no CDN dependencies. '
    'It runs in an iframe with sandbox="allow-scripts allow-forms" and an opaque origin. Local form handlers may call preventDefault; actual submissions are blocked by form-action none. localStorage, sessionStorage '
    'and other persistence APIs may throw SecurityError: guard reads and writes with try/catch and '
    'keep an in-memory fallback so optional persistence never prevents startup. Do not require parent-page access. '
    'For interactive apps, inspect initialization, input-to-state mapping, timing, pause/resume, terminal states '
    'and restart. A requested Restart control must work during play as well as after game over; reset timers without '
    'duplicating loops. Keep displayed scores and totals synchronized after every state change, including keyboard actions. '
    'For numeric controls, trim the raw text and reject empty or whitespace-only values before converting '
    'with Number; require Number.isFinite for both inputs and computed results so arithmetic overflow cannot display Infinity. '
    'Preserve the requested valid range, including zero when allowed; do not silently add stricter requirements. '
    'For indivisible counts such as people, require Number.isInteger(value) and value >= 1. Do not use parseInt or '
    'rounding to silently accept fractional counts. Enforce these rules in JavaScript even if the form uses novalidate. '
    'When adding controls to an existing page, bind actions to specific IDs or data-action attributes so shared styling '
    'classes do not accidentally attach unrelated handlers. '
    'Keep the generated UI truthful: without an implemented backend, a local form confirmation must not say an email '
    'will be sent, a booking was made, or data was saved remotely. Clearly describe only the local demo result. '
    'A successful write or read verifies file delivery only, not playability or browser execution. '
    'In the handoff state whether checks were static or actually executed; do not claim runtime verification '
    'without observed test evidence. '
    'If file writing is unavailable, return the complete document in a fenced html block. '
    'Do not create a webpage unless requested.\n')


def html_files(workspace):
    from studio import safe_file, Problem
    folder = workspace / 'artifacts'
    if folder.is_symlink() or not folder.is_dir():
        return {}
    found = {}
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
        for name in sorted(files):
            if not name.lower().endswith('.html'):
                continue
            relative = str((Path(root) / name).relative_to(workspace))
            try:
                path = safe_file(workspace, relative, True)
                raw = path.read_bytes()
                raw.decode('utf-8')
                found[relative] = (hashlib.sha256(raw).hexdigest(), path.stat().st_mtime_ns)
            except (Problem, OSError, UnicodeError):
                continue
    return found


def collect_pages(studio, owner, job_id, role, before, answer, source_map=None):
    """Export changed pages into job-specific immutable, account-owned paths.

    Never trust paths mentioned in a model reply. Only actual artifact files or
    complete HTML documents returned by the model can become previews.
    """
    from studio import safe_file, Problem
    workspace = studio.workspace(owner, role)
    sources = []
    source_names = {}
    for relative, signature in html_files(workspace).items():
        if before.get(relative) == signature:
            continue
        try:
            raw = safe_file(workspace, relative, True).read_bytes()
            # Do not attach a file that changed during collection.
            content = raw.decode('utf-8')
            if (hashlib.sha256(raw).hexdigest() == signature[0]
                    and re.search(r'<html\b', content, re.I) and re.search(r'</html\s*>', content, re.I)):
                sources.append(raw)
                source_names[hashlib.sha256(raw.strip()).hexdigest()] = relative
        except (Problem, OSError, UnicodeError):
            continue
    # A model without file tools can still supply a complete HTML deliverable.
    for match in re.finditer(r'^```html\s*\n([\s\S]*?)^```\s*$', str(answer), re.I | re.M):
        content = match.group(1).strip()
        if re.search(r'<html\b', content, re.I) and re.search(r'</html\s*>', content, re.I):
            raw = content.encode('utf-8')
            if len(raw) <= 10 * 1024 * 1024:
                sources.append(raw)
    paths, seen = [], set()
    label = 'personal' if role is None else 'r' + str(role)
    for raw in sources:
        digest = hashlib.sha256(raw.strip()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        relative = 'artifacts/page-' + job_id + '-' + label + '-' + digest[:12] + '.html'
        safe_file(studio.workspace(owner), relative).write_bytes(raw)
        if source_map is not None and digest in source_names:
            source_map[relative] = source_names[digest]
        paths.append(relative)
    return paths

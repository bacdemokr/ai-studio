"""Named, bounded page edits. Standalone so it can run in an agent workspace."""
import argparse
import fcntl
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

TEXT = {'headline': 'MORGAN_HEADLINE', 'intro': 'MORGAN_INTRO',
        'cta': 'MORGAN_CTA', 'program-title': 'MORGAN_PROGRAM_TITLE',
        'promotion-title': 'MORGAN_PROMOTION_TITLE'}
PROGRAM_SLOT = '<!-- Author the demo cards here from Dylan’s themes. -->'


def local(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Use a relative file in this workspace.')
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Page files must stay inside this workspace without symbolic links.')
    return path


def atomic(path, text):
    fd, name = tempfile.mkstemp(prefix='.page-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Card(HTMLParser):
    TAGS = {'article', 'div', 'section', 'small', 'h3', 'p', 'b', 'strong', 'em', 'span',
            'a', 'details', 'summary', 'ul', 'ol', 'li', 'br'}
    ATTRS = {'class', 'href', 'title', 'aria-label', 'aria-hidden', 'role'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.titles = []
        self.links = []
        self.roots = 0
        self.html = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            raise ValueError('Card contains an unsupported element: ' + tag)
        if not self.stack:
            self.roots += 1
            if tag != 'article' or 'theme-card' not in dict(attrs).get('class', '').split():
                raise ValueError('Use one article.theme-card as the card root.')
        clean = []
        for key, value in attrs:
            # These presentation-only fields do not contribute authored text.
            # In HTML even open="false" opens <details>; the design needs it closed.
            if (key == 'id' or key.startswith('data-')
                    or tag == 'details' and key == 'open'
                    or tag == 'a' and key in ('target', 'rel')):
                continue
            if key not in self.ATTRS:
                raise ValueError('Card contains an unsupported attribute: ' + key)
            if key == 'aria-hidden' and value not in ('true', 'false'):
                raise ValueError('aria-hidden must be true or false.')
            if key == 'href':
                parsed = urlsplit(value or '')
                if tag != 'a' or parsed.scheme != 'https' or not parsed.hostname:
                    raise ValueError('Card links must use HTTPS.')
                self.links.append(value)
            clean.append(' ' + key + '="' + escape(value or '', quote=True) + '"')
        self.html.append('<' + tag + ''.join(clean) + '>')
        if tag == 'h3':
            self.titles.append('')
        if tag != 'br':
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError('Close the card HTML elements in order.')
        self.stack.pop()
        self.html.append('</' + tag + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != 'br':
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.stack and data.strip():
            raise ValueError('Keep all card text inside its article.')
        if 'h3' in self.stack:
            self.titles[-1] += data
        self.html.append(escape(data, quote=False))

    def handle_comment(self, data):
        raise ValueError('Do not include page markers or comments in a card.')

    def handle_decl(self, decl):
        raise ValueError('Supply only a card fragment, not a complete document.')


def checked(section, value, contract):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(section + ': supply nonempty text.')
    if 'MORGAN_' in value or '<!-- BAC:' in value:
        raise ValueError(section + ': remove template placeholders and page markers.')
    if section in TEXT:
        limit = 1000 if section == 'intro' else 100
        if len(value) > limit or (section == 'headline' and len(value.split()) > 16):
            raise ValueError(section + ': shorten to ' + str(limit) + ' characters (headline: at most 16 words).')
        return value
    match = re.fullmatch(r'card-([1-9][0-9]*)', section)
    if not match or int(match[1]) > len(contract['themes']):
        raise ValueError('Unknown page section: ' + section)
    if len(value) > 6000:
        raise ValueError(section + ': keep one card under 6000 characters; do not include CSS or the whole page.')
    parser = Card()
    parser.feed(value)
    parser.close()
    if parser.stack or parser.roots != 1:
        raise ValueError(section + ': supply one complete article.theme-card.')
    theme = contract['themes'][int(match[1]) - 1]
    normalize = lambda text: ' '.join(text.split())
    if [normalize(t) for t in parser.titles] != [normalize(theme['demo'])]:
        raise ValueError(section + ': keep exactly one h3 with this demo title: ' + theme['demo'])
    if theme.get('source') and theme['source'] not in parser.links:
        raise ValueError(section + ': include the supplied source link: ' + theme['source'])
    return ''.join(parser.html)


def draft_files(html_path, count):
    """Distinct job-scoped sources avoid overwriting an unapplied shared patch."""
    stem = html_path.removesuffix('.html')
    return {'copy': stem + '-copy.json',
            **{'card-' + str(i): stem + '-card-' + str(i) + '.html' for i in range(1, count + 1)}}


def collect(workspace):
    """Apply agent-authored files after its turn; retain valid sections on errors."""
    root = Path(workspace).resolve()
    contract = json.loads(local(root, 'inbox/morgan-page.json').read_text())
    if contract.get('sectionEditor') != 2:
        raise ValueError('Automatic collection requires sectionEditor 2.')
    output = local(root, contract['files']['html'])
    files = draft_files(contract['files']['html'], len(contract['themes']))
    state = local(root, contract['files']['html'] + '.sections.json')
    lock = local(root, contract['files']['html'] + '.sections.lock')
    errors = {}
    required = list(TEXT) + [key for key in files if key != 'copy']

    def read(relative, limit):
        path = local(root, relative)
        with path.open(encoding='utf-8') as stream:
            text = stream.read(limit + 1)
        if len(text) > limit:
            raise ValueError('File exceeds ' + str(limit) + ' characters.')
        return text

    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        sections = json.loads(state.read_text()) if state.exists() else {}
        sections = {key: checked(key, value, contract) for key, value in sections.items()}
        try:
            copy = json.loads(read(files['copy'], 8000))
            if not isinstance(copy, dict):
                raise ValueError('Write an object with headline, intro, cta, program-title and promotion-title.')
            if set(copy) - set(TEXT):
                raise ValueError('Unknown text fields: ' + ', '.join(sorted(set(copy) - set(TEXT))))
            for key, value in copy.items():
                try:
                    sections[key] = checked(key, value, contract)
                except ValueError as error:
                    errors[key] = str(error)
        except (ValueError, OSError) as error:
            errors['copy'] = str(error)
        for key, relative in files.items():
            if key == 'copy':
                continue
            try:
                sections[key] = checked(key, read(relative, 6000), contract)
            except (ValueError, OSError) as error:
                errors[key] = str(error)
        template = local(root, 'inbox/morgan-page-starter.html').read_text()
        html = render(template, contract, sections)
        atomic(state, json.dumps(sections, ensure_ascii=False, indent=2))
        atomic(output, html)
    missing = [key for key in required if key not in sections]
    return {'status': 'incomplete' if missing or errors else 'complete',
            'saved': list(sections), 'missing': missing, 'errors': errors,
            'files': files}


def render(template, contract, sections):
    for key, token in TEXT.items():
        if template.count(token) != 1:
            raise ValueError('Invalid starter placeholder: ' + token)
        template = template.replace(token, escape(sections[key]) if key in sections else token)
    if template.count(PROGRAM_SLOT) != 1:
        raise ValueError('Invalid starter program mount.')
    cards = ''.join(sections.get('card-' + str(i), '') for i in range(1, len(contract['themes']) + 1))
    return template.replace(PROGRAM_SLOT, '<div class="cards">' + cards + '</div>')


def run(workspace, action='status', patch_file=None):
    root = Path(workspace).resolve()
    contract = json.loads(local(root, 'inbox/morgan-page.json').read_text())
    if contract.get('sectionEditor') != 1:
        raise ValueError('This task uses the legacy file-editing contract.')
    output = local(root, contract['files']['html'])
    state = local(root, contract['files']['html'] + '.sections.json')
    lock = local(root, contract['files']['html'] + '.sections.lock')
    template = local(root, 'inbox/morgan-page-starter.html').read_text()
    required = list(TEXT) + ['card-' + str(i) for i in range(1, len(contract['themes']) + 1)]
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        sections = json.loads(state.read_text()) if state.exists() else {}
        for key, value in sections.items():
            checked(key, value, contract)
        if action == 'apply':
            patch = json.loads(local(root, patch_file).read_text())
            if not isinstance(patch, dict) or set(patch) != {'section', 'content'} or not isinstance(patch['section'], str):
                raise ValueError('Supply one JSON object with section and content fields.')
            section = patch['section']
            sections[section] = checked(section, patch['content'], contract)
        elif action != 'status':
            raise ValueError('Unknown page action.')
        html = render(template, contract, sections)
        if action == 'apply':
            # Save accepted sections first; status can recover an interrupted HTML write.
            atomic(state, json.dumps(sections, ensure_ascii=False, indent=2))
        if sections:
            atomic(output, html)
        missing = [s for s in required if s not in sections]
        return {'status': 'incomplete' if missing else 'complete', 'saved': list(sections),
                'missing': missing, 'file': contract['files']['html'],
                'message': 'Only missing or invalid sections need another edit. Saved sections and the social post are preserved.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'status'])
    parser.add_argument('patch_file', nargs='?')
    args = parser.parse_args()
    try:
        print(json.dumps(run(Path.cwd(), args.action, args.patch_file), ensure_ascii=False))
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'invalid', 'error': str(error),
                          'message': 'Correct this section only and apply again; previously accepted sections remain saved.'}))
        raise SystemExit(1)

"""Reject invented public citation URLs; this is not semantic fact checking."""
import re
from urllib.parse import urlsplit, urlunsplit


def urls(text):
    found = set()
    for value in re.findall(r'https?://[^\s<>"\x27`]+', str(text)):
        value = value.rstrip('.,;:!?')
        while value and value[-1] in ')]}':
            close = value[-1]
            if value.count(close) <= value.count({')': '(', ']': '[', '}': '{'}[close]):
                break
            value = value[:-1]
        found.add(value)
    return found


def identity(url):
    try:
        p = urlsplit(url)
        path = p.path.rstrip('/')
        # arXiv serves one paper in several representations. Preserve explicit
        # versions: v1, v2 and the unversioned latest URL are not interchangeable.
        if p.netloc.lower() == 'arxiv.org':
            paper = re.fullmatch(r'/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v[1-9]\d*)?)(?:\.pdf)?', path)
            if paper:
                path = '/abs/' + paper.group(1)
        # A fragment and the HTTP-to-HTTPS upgrade do not identify another page.
        return urlunsplit(('https', p.netloc.lower(), path, p.query, ''))
    except ValueError:
        return url


def unsupported_citations(answer, sources):
    allowed = set()
    for source in sources:
        allowed.add(identity(source['url']))
        allowed.update(identity(url) for url in urls(source['text']))
    return sorted(url for url in urls(answer) if identity(url) not in allowed)

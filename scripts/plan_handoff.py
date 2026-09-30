"""Required saved handoffs, checked independently of model completion claims."""
import re
from pathlib import PurePosixPath
from plan_artifacts import TEXT_TYPES


def required_files(task):
    explicit = task.get('requiredFiles', [])
    if not isinstance(explicit, list) or len(explicit) > 12:
        raise RuntimeError('Invalid required handoff files in the plan.')
    for path in explicit:
        if (not isinstance(path, str) or len(path) > 300 or not path.startswith('artifacts/')
                or any(part in ('', '.', '..') for part in path.split('/')) or '\\' in path
                or PurePosixPath(path).suffix.lower() not in TEXT_TYPES | {'.html'}):
            raise RuntimeError('Required handoff files must be supported files inside artifacts/.')
    # Older plans can name the required output in their assignment instead.
    prose = task.get('task', '') + '\n' + task.get('expected', '')
    inferred = re.findall(r'(?:\bsave(?:d)?\b|\bwrite\b|\bwritten\b|\bcreate(?:d)?\b|\bproduce\b|\boutput\b|\bupdate\b|저장)'
                          r'[^\n]{0,100}?\b(artifacts/[\w./-]+\.(?:md|txt|csv|json|py|js|css|html))\b', prose, re.I)
    return list(dict.fromkeys(explicit + [p for p in inferred if '..' not in p.split('/')]))


def missing_files(task, sources, files):
    required = required_files(task)
    # The existing webpage collector can save a complete returned HTML document
    # under its own verified preview filename when native writing is unavailable.
    html_fallback = (sum(path.endswith('.html') for path in required) == 1
                     and any(path.endswith('.html') for path in files))
    return [path for path in required if not files or (path not in sources
            and not (path.endswith('.html') and html_fallback))]

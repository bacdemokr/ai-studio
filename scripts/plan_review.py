"""Preserve an explicitly requested review through selection and early completion."""
import re


def requested_review(task):
    # A conservative fallback for clear English requests if the planner omits
    # reviewRequired. Quoted source text and product reviews are not directives.
    text = re.sub(r'```.*?```', '', task, flags=re.S)
    text = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
    positive = re.compile(
        r'\b(?:add|include|need|require|want|request)(?:\s+\w+){0,5}\s+(?:review|reviewer)\b'
        r'|\b(?:independent(?:ly)?|peer)[ -]+review\b'
        r'|\b(?:ask|call|use|involve|invite)\s+(?:vera|(?:a|the)\s+reviewer)\b'
        r'|\b(?:review|double[- ]check)\s+(?:my|our|the|these|your)\s+'
        r'(?:analysis|calculations|numbers|results|work|code|data|answer|output)\b', re.I)
    negative = re.compile(
        r"\b(?:no|not|without|skip|omit|don['’]?t|do\s+not|unnecessary|optional)\b"
        r"|\b(?:isn['’]?t|is\s+not)\s+(?:needed|required)\b", re.I)
    return any(positive.search(clause) and not negative.search(clause)
               for clause in re.split(r'[\n.!?;]|\bbut\b', text, flags=re.I))


def include_required_review(plan):
    """Assemble the reviewer before any specialist starts, within the team cap."""
    if not plan.get('reviewRequired'):
        return
    tasks = plan['tasks']
    if not tasks and plan.get('outcome') in ('partial', 'unavailable'):
        return
    reviewers = [task for task in tasks if task['role'] == 4]
    if not reviewers and len(tasks) >= 3:
        raise ValueError('Reserve one of the three specialist slots for the requested Vera review.')
    originals = list(dict.fromkeys(key for task in tasks for key in task.get('inputs', [])))
    review = reviewers[0] if reviewers else {
        'role': 4,
        'task': 'Independently review the preceding analysis or deliverable against the original user request and supplied data. '
                'Recalculate material figures from the original operands, check units and periods, and flag discrepancies '
                'between supplied percentages and computed values. Do not merely confirm that a file exists. '
                'Report concrete findings, corrections and any unverified assumptions without inventing external validation.',
        'expected': 'An independent review with specific checks, findings or corrections, and honest verification limits.',
        'inputs': originals, 'requiredFiles': [],
    }
    review['inputs'] = list(dict.fromkeys(review.get('inputs', []) + originals))
    if any(task.get('useImages') for task in tasks):
        review['useImages'] = True
    plan['tasks'] = [task for task in tasks if task['role'] != 4] + [review]
    if not reviewers:
        plan['summary'] += ' Vera will independently review the result, as requested.'
    if plan.get('answer'):
        plan['captainDraft'] = plan.pop('answer')


def review_finished(plan):
    output = plan.get('outputs', {}).get('4', {})
    return bool(4 in plan.get('calledRoles', []) and output.get('answer')
                and not output.get('incomplete') and output.get('handoffStatus') != 'missing')

"""Bind Open Task assignments to real hired agents, with built-in specialists as backup.

Adapted from Paul Roeseler's personal_collaboration capture/validation approach.
Keep the current dispatcher so cancellation, verified handoffs and recovery are shared.
"""
import json
import re

ROLE_SKILLS = {4: {'documents'}, 5: {'builder'}, 6: {'documents'}, 7: {'builder'}, 8: {'web', 'weather'}}
ROLE_WORDS = [(5, r'(?<![A-Za-z0-9_])(?:cod(?:e|ing)|programming|developer|implement|build)(?![A-Za-z0-9_])|코딩|개발|구현'),
              (4, r'(?<![A-Za-z0-9_])(?:review|reviewer|check)(?![A-Za-z0-9_])|검토|검증|리뷰'),
              (8, r'(?<![A-Za-z0-9_])(?:research|researcher|search)(?![A-Za-z0-9_])|조사|검색|리서치'),
              (7, r'(?<![A-Za-z0-9_])(?:design|designer|UX)(?![A-Za-z0-9_])|디자인|설계'),
              (6, r'(?<![A-Za-z0-9_])(?:analysis|analyst|analy[sz]e)(?![A-Za-z0-9_])|분석')]


def mentions(text, name):
    return re.search(r'(?<![\w])' + re.escape(name) + r'(?![A-Za-z0-9_])', text, re.I)


def direct_request(task):
    text = re.sub(r'```.*?```', '', task, flags=re.S)
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))


def excluded(text, match):
    return bool(re.search(r"(?:do not|don't|never|without|except|exclude|skip|not)\s+(?:(?:use|ask|let|include|involve)\s+)?$",
                          text[max(0, match.start()-40):match.start()], re.I)
                or re.match(r"(?:은|는|을|를|도)?\s*(?:빼|제외|말고|참여시키지|쓰지|사용하지)|\s+(?:should|must)\s+not\b", text[match.end():], re.I))


def requirements(task, members):
    """Conservative direct-name backstop, using only the visitor's request, never files."""
    text = direct_request(task)
    found = []
    for member in members:
        match = mentions(text, member['name'])
        if not match:
            continue
        clause = re.split(r'[\n.!?;]', text[:match.start()])[-1] + text[match.start():].split('\n')[0]
        if excluded(text, match):
            continue
        if not re.search(r'\b(?:use|ask|let|have|include|involve|assign|instead|replace|must)\b|참여|대신|맡|해줘|해주세요|시켜|써줘|사용', clause, re.I):
            continue
        tail = text[match.end():]
        next_names = [m.start() for other in members if other['key'] != member['key']
                      for m in [mentions(tail, other['name'])] if m]
        span = tail[:min(next_names)] if next_names else re.split(r'[\n.!?;]', tail)[0]
        role = next((role for role, pattern in ROLE_WORDS if re.search(pattern, span, re.I)), None)
        found.append({'key': member['key'], 'name': member['name'], 'role': role})
    return found


def capture(studio, db, owner, task):
    from studio import Problem
    rows = db.execute("SELECT id,profile FROM agents WHERE kind='personal' AND participant="
                      "(SELECT participant FROM agents WHERE id=?) AND profile IS NOT NULL AND deleting=0 "
                      "ORDER BY created,id", (owner,)).fetchall()
    all_members = [{**json.loads(row['profile']), 'key': row['id'], 'role': 'Hired specialist'} for row in rows]
    required = requirements(task, all_members)
    connection_ready = not all_members or studio.runtime_status().get('ready')
    request = direct_request(task)
    members, unavailable = [], []
    for member in all_members:
        match = mentions(request, member['name'])
        if match and excluded(request, match):
            unavailable.append({'name': member['name'], 'reason': 'Excluded by the visitor.'})
            continue
        if not connection_ready:
            if any(item['key'] == member['key'] for item in required):
                raise Problem(member['name'] + ' needs its Hiring & Lounge model connection. Reconnect it in Settings.', 409)
            unavailable.append({'name': member['name'], 'reason': 'Hiring & Lounge model is not connected.'})
            continue
        try:
            studio.require_available(db, member['key'])
            studio.require_idle(db, member['key'])
        except Problem:
            if any(item['key'] == member['key'] for item in required):
                raise Problem(member['name'] + ' is busy or unavailable. Finish its current work before including it.', 409)
            unavailable.append({'name': member['name'], 'reason': 'Busy or unavailable.'})
        else:
            members.append(member)
    if len(required) > 3:
        raise Problem('This demo can assign three specialists per task. Split this request so every named agent can participate.', 409)
    return members, required, unavailable


def instructions(members, required):
    if not members:
        return ''
    from agent_runtime import collaboration_capabilities
    choices = [{**{key: m.get(key) for key in ('key', 'name', 'purpose', 'skills')},
                **collaboration_capabilities(m)} for m in members]
    return ('\nVISITOR TEAM SELECTION - overrides generic recommendations to pick Scout/Cody/Vera by name. '
            'Role numbers describe the assignment (4 review, 5 coding, 6 analysis, 7 design, 8 research), '
            'not who must do it. Prefer suitable hired agents below; use the built-in expert only when no suitable '
            'hired agent is available. Add agent:"exact key" to each hired assignment; agent:"builtin" selects '
            'the backup for that role. Each agent and role can appear only once. '
            'If the visitor names an agent, it MUST actually contribute, even outside its usual skills or expertise. '
            'If they say Pixel should code instead, give Pixel role 5; do not leave coding to Cody and give Pixel '
            'a token reaction. User role assignments override saved interests, but never expand tool permissions. '
            'Keep the agent\'s identity and voice. Missing tools must be reported honestly. '
            'Do not substitute someone else merely because the nominated agent may produce a worse result. '
            'An independent reviewer must be a different agent. Keep assignments small and concrete: enough '
            'evidence for the requested result, a saved handoff, then stop. For research the shared ceiling is '
            '150 seconds, two searches or five direct fetches; stop earlier once the required facts are supported. '
            'No optional polish or repeated verification.\nHired agents:\n' + json.dumps(choices, ensure_ascii=False) +
            '\nRequired participants detected from the direct request:\n' + json.dumps(required, ensure_ascii=False) + '\n')


def bind(plan, roster, members, required, task):
    """Enforce named assignments before dispatch, without changing saved profiles."""
    available = {m['key']: m for m in members}
    tasks = plan['tasks']
    for assignment in tasks:
        key = assignment.get('agent', 'builtin')
        if key != 'builtin' and key not in available:
            raise RuntimeError('Casey selected an agent outside the available hired team. No specialist was started.')
    for item in required:
        assigned = next((t for t in tasks if t.get('agent') == item['key']), None)
        target = item['role']
        if assigned and (target is None or assigned['role'] == target):
            continue
        if assigned:
            tasks.remove(assigned)
        existing = next((t for t in tasks if t['role'] == target), None) if target else None
        if existing:
            if existing.get('agent') in {r['key'] for r in required if r['key'] != item['key']}:
                raise RuntimeError('Two named agents were assigned the same demo role. Split their assignments into separate tasks.')
            existing['agent'] = item['key']
        else:
            unused = [r for r in (5, 8, 6, 7, 4) if not any(t['role'] == r for t in tasks)]
            if not unused or len(tasks) >= 3:
                raise RuntimeError('Casey must leave a specialist slot for ' + item['name'] + '. No specialist was started.')
            role = target or next((r for r in unused if ROLE_SKILLS[r].intersection(available[item['key']].get('skills', []))), unused[0])
            tasks.append({'role': role, 'agent': item['key'], 'task': 'The visitor explicitly assigns you this work. '
                          'Perform your contribution yourself within the requested role; preserve your voice. Request: ' + task[:1600],
                          'expected': 'Your actual contribution and honest limitations, not a reaction or a substitute agent.',
                          'inputs': [], 'requiredFiles': []})
    used = {t['agent'] for t in tasks if t.get('agent') not in (None, 'builtin')}
    for assignment in tasks:
        role = assignment['role']
        if 'agent' not in assignment and not mentions(task, roster[role]['name']):
            candidate = next((m for m in members if m['key'] not in used and 'radar' not in m.get('skills', [])
                              and ROLE_SKILLS[role].intersection(m.get('skills', []))), None)
            if candidate:
                assignment['agent'] = candidate['key']
                used.add(candidate['key'])
    bindings, seen = {}, set()
    for assignment in tasks:
        key = assignment.get('agent', 'builtin')
        if key == 'builtin':
            continue
        if key in seen:
            raise RuntimeError('An agent cannot both produce and independently review the same work. Choose distinct agents.')
        seen.add(key)
        member = available[key]
        bindings[str(assignment['role'])] = member
        roster[assignment['role']] = member
        assignment['name'] = member['name']
    plan['visitorBindings'] = bindings
    plan['requiredAgents'] = required
    # Keep the UI's explanation consistent when the deterministic backstop corrected the planner.
    if bindings:
        plan['summary'] += ' Hired team: ' + ', '.join(m['name'] for m in bindings.values()) + '.'


def validate(studio, owner, member):
    from studio import Problem
    with studio.db() as db:
        row = db.execute("SELECT profile FROM agents WHERE id=? AND kind='personal' AND participant="
                         "(SELECT participant FROM agents WHERE id=?)", (member['key'], owner)).fetchone()
        if not row or not row['profile']:
            raise Problem('The selected agent is no longer in this studio.', 409)
        studio.require_available(db, member['key'])
    current = json.loads(row['profile'])
    if any(current.get(key) != member.get(key) for key in ('id', 'name', 'purpose', 'tonePrompt', 'skills', 'protection', 'model', 'avatar')):
        raise Problem('The selected agent changed after the task was submitted. Start a new task.', 409)
    return current

"""Bind Open Task assignments to real hired agents, with built-in specialists as backup.

Adapted from Paul Roeseler's personal_collaboration capture/validation approach.
Keep the current dispatcher so cancellation, verified handoffs and recovery are shared.
"""
import json
import re


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
        # Detect explicit participants only. Role semantics belong to Casey;
        # neighboring words may describe a different agent or an input file.
        found.append({'key': member['key'], 'name': member['name'], 'role': None})
    return found


def hired_members(db, owner):
    rows = db.execute("SELECT id,profile FROM agents WHERE kind='personal' AND participant="
                      "(SELECT participant FROM agents WHERE id=?) AND profile IS NOT NULL AND deleting=0 "
                      "ORDER BY created,id", (owner,)).fetchall()
    return [{**json.loads(row['profile']), 'key': row['id'], 'role': 'Hired specialist'} for row in rows]


def require_opt_in(db, owner, task):
    """Do not silently replace an explicitly requested person when participation is off."""
    from studio import Problem
    required = requirements(task, hired_members(db, owner))
    if required:
        raise Problem('Turn on Include hired agents to assign ' + ', '.join(m['name'] for m in required) + '.', 409)


def capture(studio, db, owner, task):
    from studio import Problem
    all_members = hired_members(db, owner)
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
            'hired agent is available. Every task MUST include agent:"exact key" for a hired assignment; agent:"builtin" selects '
            'the backup for that role. Each agent and role can appear only once. '
            'Interpret the visitor\'s natural-language assignments, including informal requests and references to earlier sentences. '
            'Explicitly named built-in specialists must be kept when requested. '
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


class TeamSelectionError(RuntimeError):
    """A planner response needs explicit identities before any work may start."""


def validate_selection(plan, members, required):
    available = {m['key']: m for m in members}
    seen = set()
    for assignment in plan['tasks']:
        key = assignment.get('agent')
        if key is None:
            if members:
                raise TeamSelectionError('Identify who performs every task using agent: an exact hired key or "builtin". '
                                         'Role numbers identify the job, not the agent. Read the original request to assign each person.')
            continue
        if key == 'builtin':
            continue
        if key not in available:
            raise RuntimeError('Casey selected an agent outside the available hired team. No specialist was started.')
        if key in seen:
            raise TeamSelectionError('Each hired agent can perform only one specialist assignment. '
                                     'An independent reviewer must be a different agent.')
        seen.add(key)
    missing = [m['name'] for m in required if m['key'] not in seen]
    if missing:
        raise TeamSelectionError('The visitor explicitly requested ' + ', '.join(missing) +
                                 '. Assign their actual requested work, not a reaction or a replacement.')


def bind(plan, roster, members, required, task):
    """Apply Casey's explicit choices. Never infer or rewrite roles from prose."""
    validate_selection(plan, members, required)
    available = {m['key']: m for m in members}
    bindings = {}
    for assignment in plan['tasks']:
        key = assignment.get('agent', 'builtin')
        if key != 'builtin':
            member = available[key]
            bindings[str(assignment['role'])] = member
            roster[assignment['role']] = member
        assignment['name'] = roster[assignment['role']]['name']
    plan['visitorBindings'] = bindings
    plan['requiredAgents'] = required


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

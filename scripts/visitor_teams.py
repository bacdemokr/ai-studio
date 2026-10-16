"""Bind Open Task assignments to real hired agents, with built-in specialists as backup.

Adapted from Paul Roeseler's personal_collaboration capture/validation approach.
Keep the current dispatcher so cancellation, verified handoffs and recovery are shared.
"""
import json
from role_boundaries import TEAM_ROLE_BOUNDARY, skill_scope, implementation_scope
import re

ROLE_SKILLS = {
    4: ('builder',),
    5: ('builder',),
    6: ('data-analysis',),
    7: ('interface-design',),
    8: ('web',),
}
BUILTIN_NAMES = {4: 'Vera', 5: 'Cody', 6: 'Ada', 7: 'Iris', 8: 'Scout'}


def team_mode(data):
    """Old clients retain their boolean opt-in; new clients name the team explicitly."""
    from studio import Problem
    if 'teamMode' in data:
        mode = data['teamMode']
        if not isinstance(mode, str) or mode not in ('builtin', 'mixed', 'hired'):
            raise Problem('Choose Hired only or Hired + Standby.')
        return mode
    include = data.get('includeHiredAgents', bool(data.get('roster')))
    if type(include) is not bool:
        raise Problem('Include hired agents must be on or off.')
    return 'mixed' if include else 'builtin'


def mentions(text, name):
    return re.search(r'(?<![\w])' + re.escape(name) + r'(?![A-Za-z0-9_])', text, re.I)


def direct_request(task):
    text = re.sub(r'```.*?```', '', task, flags=re.S)
    return '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))


def excluded(text, match):
    return bool(re.search(r"(?:do not|don't|never|without|except|exclude|skip|not)\s+(?:(?:use|ask|let|include|involve)\s+)?$",
                          text[max(0, match.start()-40):match.start()], re.I)
                or re.match(r"(?:은|는|을|를|도)?\s*(?:빼|제외|말고|참여시키지|쓰지|사용하지)|\s+(?:should|must)\s+not\b", text[match.end():], re.I))


def explicit_builtin(task, role):
    """An explicitly named standby remains eligible even when a hire has its skill."""
    name = BUILTIN_NAMES.get(role)
    text = direct_request(task or '')
    match = mentions(text, name) if name else None
    return bool(match and not excluded(text, match))


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
        raise Problem('Choose Hired only or Hired + Standby to assign ' + ', '.join(m['name'] for m in required) + '.', 409)


def capture(studio, db, owner, task):
    from studio import Problem
    all_members = hired_members(db, owner)
    required = requirements(task, all_members)
    import personal_models
    runtime = studio.runtime_status() if all_members else {}
    request = direct_request(task)
    members, unavailable = [], []
    for member in all_members:
        match = mentions(request, member['name'])
        if match and excluded(request, match):
            unavailable.append({'name': member['name'], 'reason': 'Excluded by the visitor.'})
            continue
        if not personal_models.ready(member, runtime):
            if any(item['key'] == member['key'] for item in required):
                raise Problem(member['name'] + ': ' + personal_models.unavailable(member), 409)
            unavailable.append({'name': member['name'], 'reason': personal_models.unavailable(member)})
            continue
        try:
            studio.require_available(db, member['key'])
            studio.require_idle(db, member['key'])
        except Problem:
            preparing = db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind='prepare-agent' "
                                   "AND status='running'", (member['key'],)).fetchone()
            reason = ('is still preparing. Try again when preparation finishes.' if preparing else
                      'is busy or unavailable. Finish its current work before including it.')
            if any(item['key'] == member['key'] for item in required):
                raise Problem(member['name'] + ' ' + reason, 409)
            unavailable.append({'name': member['name'], 'reason': 'Preparing.' if preparing else 'Busy or unavailable.'})
        else:
            members.append(member)
    if len(required) > 3:
        raise Problem('This demo can assign three specialists per task. Split this request so every named agent can participate.', 409)
    return members, required, unavailable


def instructions(members, required, mode='mixed'):
    if not members and mode != 'hired':
        return ''
    from agent_runtime import collaboration_capabilities
    choices = [{**{key: m.get(key) for key in ('key', 'name', 'purpose', 'skills')},
                'skillScope': skill_scope(m), 'implementationScope': implementation_scope(m),
                **collaboration_capabilities(m)} for m in members]
    policy = ('HIRED AGENTS ONLY: Casey coordinates but cannot do specialist work. Assign every specialist task '
              'to an exact hired key below. Never use agent:"builtin" or invoke Scout, Cody, Vera, Ada or Iris. '
              'Their role numbers are assignment types only, not available people. If no useful requested portion '
              'is possible with the listed tools, return outcome:"unavailable" and explain the missing capability. Do not silently '
              'switch teams. One hire may deliver a combined small implementation, but may not independently review itself. '
              if mode == 'hired' else
              'MIXED TEAM PRIORITY: assign a suitable hired agent below before any built-in specialist with the same needed skill. '
              'This is mandatory, not a suggestion. Use agent:"builtin" only when no unassigned suitable hire is available, '
              'or when the visitor explicitly names that built-in specialist. '
              'If a hire covers one requested part and standby covers another, split those tasks within the three-slot limit. '
              'Explicitly named built-in specialists must be kept when requested. ')
    return ('\nVISITOR TEAM SELECTION - overrides generic recommendations to pick Scout/Cody/Vera by name. ' + policy +
            'Role numbers describe the assignment (4 review, 5 coding, 6 analysis, 7 design, 8 research), '
            'not who must do it. Every task MUST include agent:"exact key" for a hired assignment. '
            'Each agent and role can appear only once. '
            + TEAM_ROLE_BOUNDARY + ' '
            'Every hired assignment must include roleFit, one short sentence naming the equipped skill that covers this actual work. '
            'Do not invent a skill or use purpose text to justify missing skills. '
            'implementationScope:"missing-coding" means Coding is not equipped. Do not assign coding or an HTML deliverable, '
            'even to a Programmer or custom developer, and even if write is available. '
            'For a named agent you cannot suitably assign, include declinedAgents:[{"agent":"exact hired key",'
            '"reason":"role mismatch and the suitable role needed"}]. Do not list a declined agent in tasks. '
            'Explain each declined request in summary and the final answer, not only in JSON metadata. '
            'An independent reviewer must be a different agent. Keep assignments small and concrete: enough '
            'evidence for the requested result, a saved handoff, then stop. For research the shared ceiling is '
            '150 seconds, two searches or five direct fetches; stop earlier once the required facts are supported. '
            'No optional polish or repeated verification.\nHired agents:\n' + json.dumps(choices, ensure_ascii=False) +
            '\nRequired participants detected from the direct request:\n' + json.dumps(required, ensure_ascii=False) + '\n')


class TeamSelectionError(RuntimeError):
    """A planner response needs explicit identities before any work may start."""


def validate_selection(plan, members, required, mode='mixed', task=''):
    available = {m['key']: m for m in members}
    formats = plan.get('requestedFormats', [])
    declared = [path for task in plan['tasks'] for path in task.get('requiredFiles', [])]
    # A coding assignment may use the existing verified HTML collector without
    # an exact planner-selected filename. Final completion still needs a saved page.
    implicit_html = any(task['role'] == 5 for task in plan['tasks'])
    missing = [kind for kind in formats if not (kind == 'html' and implicit_html)
               and not any(path.lower().endswith('.' + kind) for path in declared)]
    if plan['tasks'] and missing and not plan.get('unassignedRequirements'):
        raise TeamSelectionError('The original request requires saved ' + ', '.join(missing).upper() +
                                 ' output, but no assignment produces it. Include the appropriate available specialist '
                                 'and requiredFiles, or record why the team cannot produce it in unassignedRequirements. '
                                 'Do not omit the implementation after selecting an analyst or researcher; Casey cannot fill it in.')
    selected_hires = {assignment.get('agent') for assignment in plan['tasks']
                      if assignment.get('agent') not in (None, 'builtin')}
    if mode == 'mixed':
        for assignment in plan['tasks']:
            if assignment.get('agent') not in (None, 'builtin') or explicit_builtin(task, assignment.get('role')):
                continue
            skills = ROLE_SKILLS.get(assignment.get('role'), ())
            candidates = [member for member in members if member['key'] not in selected_hires
                          and any(skill in member.get('skills', []) for skill in skills)]
            if candidates:
                names = ', '.join(member.get('name', member['key']) for member in candidates)
                raise TeamSelectionError('Hired + Standby must use a suitable hired agent before the built-in '
                                         + BUILTIN_NAMES[assignment['role']] + '. Assign ' + names +
                                         ' to this ' + '/'.join(skills) + ' work, or use the standby specialist only '
                                         'after every matching hire is already assigned or unavailable.')
    seen = set()
    for assignment in plan['tasks']:
        key = assignment.get('agent')
        if mode == 'hired' and key in (None, 'builtin'):
            raise TeamSelectionError('Hired agents only is selected. Assign every specialist task to an available hired key; '
                                     'built-in specialists cannot participate. If the team cannot do the work, explain the missing capability.')
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
        if not skill_scope(available[key]):
            raise TeamSelectionError(available[key].get('name', 'This agent') + ' has no equipped specialist skill. '
                                     'Equip the skill required for this task or choose a suitably equipped agent.')
        if not isinstance(assignment.get('roleFit'), str) or not assignment['roleFit'].strip():
            raise TeamSelectionError('Explain how each hired assignment fits an equipped skill in roleFit. '
                                     'If it does not fit, decline it rather than reassigning its identity.')
        implements = assignment.get('role') == 5 or any(
            str(file).lower().endswith(('.html', '.htm')) for file in assignment.get('requiredFiles', []))
        if implements and implementation_scope(available[key]) != 'allowed':
            raise TeamSelectionError(available[key]['name'] + ' does not have Coding equipped. '
                                     'File tools do not grant Coding. Remove this coding/HTML assignment; '
                                     'use a suitable available agent or explain the missing expertise. '
                                     'Do not relabel implementation as research or analysis.')
        seen.add(key)
    declined = plan.get('declinedAgents', [])
    declined_keys = {m['agent'] for m in declined}
    if len(declined_keys) != len(declined) or declined_keys - available.keys() or declined_keys & seen:
        raise TeamSelectionError('Declined agents must be available hired agents, listed once and not assigned work.')
    missing = [m['name'] for m in required if m['key'] not in seen | declined_keys]
    if missing:
        raise TeamSelectionError('The visitor explicitly requested ' + ', '.join(missing) +
                                 '. Assign suitable requested work or explain the role mismatch in declinedAgents. Do not substitute a reaction or replacement.')


def bind(plan, roster, members, required, task, mode='mixed'):
    """Apply Casey's explicit choices. Never infer or rewrite roles from prose."""
    validate_selection(plan, members, required, mode, task)
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
    declined = {m['agent'] for m in plan.get('declinedAgents', [])}
    plan['requiredAgents'] = [m for m in required if m['key'] not in declined]


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

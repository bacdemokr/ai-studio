"""Bind Open Task assignments to real hired agents, with built-in specialists as backup.

Adapted from Paul Roeseler's personal_collaboration capture/validation approach.
Keep the current dispatcher so cancellation, verified handoffs and recovery are shared.
"""
import json
from role_boundaries import TEAM_ROLE_BOUNDARY, skill_scope, implementation_scope

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


def hired_members(db, owner):
    rows = db.execute("SELECT id,profile FROM agents WHERE kind='personal' AND participant="
                      "(SELECT participant FROM agents WHERE id=?) AND profile IS NOT NULL AND deleting=0 "
                      "ORDER BY created,id", (owner,)).fetchall()
    return [{**json.loads(row['profile']), 'key': row['id'], 'role': 'Hired specialist'} for row in rows]


def capture(studio, db, owner):
    """Capture actual availability. Participation intent belongs to Casey's plan."""
    from studio import Problem
    all_members = hired_members(db, owner)
    import personal_models
    runtime = studio.runtime_status() if all_members else {}
    members, unavailable = [], []
    for member in all_members:
        identity = {'key': member['key'], 'name': member['name']}
        if not personal_models.ready(member, runtime):
            unavailable.append({**identity, 'reason': personal_models.unavailable(member)})
            continue
        try:
            studio.require_available(db, member['key'])
            studio.require_idle(db, member['key'])
        except Problem:
            preparing = db.execute("SELECT 1 FROM jobs WHERE owner=? AND kind='prepare-agent' "
                                   "AND status='running'", (member['key'],)).fetchone()
            unavailable.append({**identity, 'reason': 'Preparing.' if preparing else 'Busy or unavailable.'})
        else:
            members.append(member)
    return members, unavailable


def instructions(members, unavailable=(), mode='mixed'):
    from agent_runtime import collaboration_capabilities
    choices = [{**{key: m.get(key) for key in ('key', 'name', 'purpose', 'skills')},
                'skillScope': skill_scope(m), 'implementationScope': implementation_scope(m),
                **collaboration_capabilities(m)} for m in members]
    policy = ('HIRED AGENTS ONLY: Casey coordinates but cannot do specialist work. Assign every specialist task '
              'to an exact hired key below. Never use agent:"builtin" or invoke Scout, Cody, Vera, Ada or Iris. '
              'Their role numbers are assignment types only, not available people. If the core requested result '
              'is known to be impossible with this team, return tasks:[], outcome:"unavailable" and explain the missing capability, '
              'unless the user explicitly permits reduced scope. Do not silently '
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
            'Interpret participation from the whole current user request, including negation and corrections. '
            'Return requestedAgents and excludedAgents as arrays of identities: exact hired keys or the standby names '
            'Vera, Cody, Ada, Iris, Scout. requestedAgents contains only people the user asks to participate; '
            'excludedAgents contains only people the user asks to leave out. An incidental mention, filename, quoted '
            'example or optional suggestion does not make someone required. Use [] when there is no such instruction. '
            'Never assign an excluded or unavailable agent. A requested standby overrides hired priority only in mixed mode. '
            'For a requested agent you cannot assign because of skills, availability, team mode or the three-slot limit, '
            'include declinedAgents:[{"agent":"same identity","reason":"specific limitation and next step"}]. '
            'Do not list a declined agent in tasks. Do not silently replace a requested unavailable person. '
            'Explain each declined request in summary and the final answer, not only in JSON metadata. '
            'An independent reviewer must be a different agent. Keep assignments small and concrete: enough '
            'evidence for the requested result, a saved handoff, then stop. For research the shared ceiling is '
            'two searches or five direct fetches within the whole-task time budget; leave time for implementation. '
            'No optional polish or repeated verification.\nHired agents:\n' + json.dumps(choices, ensure_ascii=False) +
            '\nUnavailable hired agents (context only, cannot be assigned):\n' + json.dumps(unavailable, ensure_ascii=False) + '\n')


class TeamSelectionError(RuntimeError):
    """A planner response needs explicit identities before any work may start."""


def validate_selection(plan, members, unavailable=(), mode='mixed'):
    available = {m['key']: m for m in members}
    known = {**{m['key']: m['name'] for m in unavailable if m.get('key')},
             **{m['key']: m.get('name', m['key']) for m in members},
             **{name: name for name in BUILTIN_NAMES.values()}}
    requested = set(plan.get('requestedAgents', []))
    excluded = set(plan.get('excludedAgents', []))
    if (requested | excluded) - known.keys() or requested & excluded:
        raise TeamSelectionError('Participation requests must identify known agents and cannot both request and exclude the same agent.')
    selected = {assignment_identity(t) for t in plan['tasks']}
    if selected & excluded:
        raise TeamSelectionError('The plan assigns an agent it also excludes. Re-read the request and correct the participation decision.')
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
            if assignment.get('agent') not in (None, 'builtin') or assignment_identity(assignment) in requested:
                continue
            skills = ROLE_SKILLS.get(assignment.get('role'), ())
            candidates = [member for member in members if member['key'] not in selected_hires | excluded
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
    if len(declined_keys) != len(declined) or declined_keys - known.keys() or declined_keys & selected:
        raise TeamSelectionError('Declined agents must be known agents, listed once and not assigned work.')
    missing = [known[key] for key in sorted(requested - selected - declined_keys)]
    if missing:
        raise TeamSelectionError('The plan identifies a participation request for ' + ', '.join(missing) +
                                 '. Assign suitable requested work or explain the limitation in declinedAgents. Do not substitute a reaction or replacement.')


def assignment_identity(assignment):
    key = assignment.get('agent', 'builtin')
    return BUILTIN_NAMES.get(assignment['role']) if key == 'builtin' else key


def bind(plan, roster, members, unavailable=(), mode='mixed'):
    """Apply Casey's explicit choices. Never infer or rewrite roles from prose."""
    validate_selection(plan, members, unavailable, mode)
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
    plan['requiredAgents'] = [m for m in members if m['key'] in plan.get('requestedAgents', []) and m['key'] not in declined]


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

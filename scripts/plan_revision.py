"""One evidence-backed repair, restricted to specialists already in this plan."""
PLAN_TIME_BUDGET_SECONDS = 600


class PlanBudgetExceeded(RuntimeError):
    pass


def read_revision(value, plan):
    if not isinstance(value, dict) or plan.get('revision'):
        raise RuntimeError('Only one revision is allowed for this collaboration.')
    role, evidence_role = value.get('role'), value.get('evidenceRole')
    called = plan.get('calledRoles', [])
    if (type(role) is not int or role not in called or role == 0 or str(role) not in plan.get('outputs', {})
            or type(evidence_role) is not int or str(evidence_role) not in plan.get('outputs', {})):
        raise RuntimeError('A revision must use a participating specialist and a saved contribution as evidence.')
    if value.get('severity') != 'blocking':
        raise RuntimeError('A revision is reserved for a concrete unmet requirement, not optional polish.')
    result = {'role': role, 'evidenceRole': evidence_role, 'severity': 'blocking'}
    for key, limit in (('issue', 1500), ('task', 2000), ('expected', 1500)):
        text = value.get(key)
        if not isinstance(text, str) or not 0 < len(text.strip()) <= limit:
            raise RuntimeError('A revision needs a specific issue, scoped assignment and acceptance criteria.')
        result[key] = text.strip()
    return result


def effective_outputs(plan):
    outputs = dict(plan.get('outputs', {}))
    revision = plan.get('revision', {})
    if revision.get('status') == 'delivered' and revision.get('output'):
        outputs[str(revision['role'])] = revision['output']
    return outputs


REVISION_INSTRUCTIONS = (
    '\nYou may request ONE targeted revision from a specialist who already participated, '
    'only when a saved contribution or review identifies a concrete defect that prevents an original requirement '
    'from being met. Optional polish, personal taste and unavailable tools are not reasons to repeat work. '
    'A generic request to read the file again, confirm it was saved, or verify every requirement is NOT a blocking defect. '
    'Successful saved-file evidence already establishes delivery, not browser execution. If no concrete failure '
    'has been observed, finish with any unperformed execution checks stated as limitations. '
    'Perform a necessary narrow source check yourself using the supplied readPath; do not send the author back '
    'just to confirm its implementation. Preserve any independent review explicitly requested by the user. '
    'Choose the appropriate participating expert for this problem, not a fixed researcher/programmer pair. '
    'Preserve their role scope. Do not add an agent, broaden the user request or repeat the whole workflow. '
    'No automatic second review or second revision will follow. If one scoped repair cannot produce a useful '
    'improvement, return the current result as partial with its limitations. '
    'For a justified revision return ONLY JSON {"done":false,"reason":"why this repair is essential",'
    '"revision":{"role":5,"evidenceRole":4,"severity":"blocking","issue":"specific observed unmet requirement",'
    '"task":"one bounded repair within this specialist expertise","expected":"how Casey can verify it"}}. '
    'The role numbers are schema examples only; choose from the actual participants. Otherwise finish normally. '
)


def revision_instructions(plan):
    """Do not suggest an absent reviewer/programmer in the control JSON example."""
    called = [role for role in plan.get('calledRoles', [])
              if str(role) in plan.get('outputs', {})]
    if not called:
        return ''
    return REVISION_INSTRUCTIONS.replace('"role":5,"evidenceRole":4',
        '"role":' + str(called[0]) + ',"evidenceRole":' + str(called[-1])) + (
        '\nAllowed revision roles and evidenceRole values for this request: ' + str(called) + '. '
        'Reading an existing brief to compose your final reply is your own work, not a specialist revision. '
        'Use the supplied readPath if a specific verification is needed; otherwise finish from the contribution.\n')

"""Stage 3 scenario identifiers shared by ownership and HTTP routing."""
SCENARIOS = ('plan', 'event-brief')


def validate(value):
    from studio import Problem
    if value not in SCENARIOS:
        raise Problem('Choose an available Stage 3 scenario.')
    return value


def crew_member(member, scenario):
    """Resolve a scenario's identity without changing catalog role/tool identifiers."""
    return {**member, **member.get('event', {})} if scenario == 'event-brief' else dict(member)

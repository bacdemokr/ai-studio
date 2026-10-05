"""Stage 3 scenario identifiers shared by ownership and HTTP routing."""
SCENARIOS = ('plan', 'event-brief')


def validate(value):
    from studio import Problem
    if value not in SCENARIOS:
        raise Problem('Choose an available Stage 3 scenario.')
    return value

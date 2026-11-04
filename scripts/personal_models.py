"""Per-agent choices from prepared connections, adapted from Paul Roeseler's experiment.

Profiles store only a source/model reference. Credentials remain in the existing
connection inventory. Open Task prefers the API default without overwriting saved Lounge choices.
"""
import model_connections as connections
import runtime_settings as settings
import team_models

DEFAULT = 'local'
LEGACY = 'shared'


def selection(profile):
    return profile.get('model', LEGACY)


def split_ref(value):
    if not isinstance(value, str):
        return None
    parts = value.split('/', 2)
    if len(parts) == 3 and parts[0] == 'api' and parts[1] in ('nvidia', 'openai', 'anthropic') and team_models.valid_model(parts[2]):
        return parts[1], parts[2]
    return None


def validate(value=DEFAULT, *, previous=None):
    from studio import Problem
    if value in (DEFAULT, LEGACY):
        return value
    if split_ref(value) and (value == previous or any(row['id'] == value for row in public()['models'])):
        return value
    raise Problem('Choose an available model for this agent.')


def public(state=None):
    state = state or connections.public()
    local, api = (state['connections'][key] for key in ('local', 'api'))
    choices = [{'id': DEFAULT, 'label': 'Local' + (' - ' + local['model'] if local.get('model') else ''),
                'source': 'local', 'connected': bool(local['ready'])}]
    rows = {row['id']: row for row in api.get('models', [])}
    if api.get('model'):
        rows.setdefault(api['model'], {'id': api['model'], 'label': api['model']})
    for model, row in rows.items():
        if not team_models.valid_model(model):
            continue
        choices.append({'id': 'api/' + api['provider'] + '/' + model,
                        'label': row.get('label', model), 'source': 'api',
                        'connected': bool(api['ready'])})
    choices.append({'id': LEGACY, 'label': 'Shared default', 'source': 'shared',
                    'connected': bool(state['loungeSource'])})
    return {'default': DEFAULT, 'models': choices}


def effective_selection(profile, runtime, stage='lounge'):
    """Resolve per call, not from the current room, so navigation cannot reroute work."""
    chosen = selection(profile)
    if stage == 'team':
        if profile.get('taskModel'):
            return profile['taskModel']
        if split_ref(chosen):
            return chosen
    state = runtime.get('modelConnections')
    if not state:
        return chosen
    states = state['connections']
    if stage == 'team':
        source = connections.choose('auto', 'team', states)
    elif chosen == DEFAULT:
        source = connections.choose('auto', 'lounge', states)
    else:
        return chosen  # Preserve explicitly selected Lounge API models.
    if source == 'local':
        return DEFAULT
    if source == 'api':
        api = states['api']
        return 'api/' + api['provider'] + '/' + api['model']
    return chosen


def ready(profile, runtime, stage='lounge'):
    value = effective_selection(profile, runtime, stage)
    if value == LEGACY:
        return bool(runtime.get('ready'))
    if not runtime.get('gateway'):
        return False
    state = runtime.get('modelConnections')
    if not state:
        # Compatibility with pre-inventory local installations.
        return value == DEFAULT and settings.read()['provider'] == 'local' and bool(runtime.get('model'))
    return any(row['id'] == value and row['connected'] for row in public(state)['models'])


def unavailable(profile, stage='lounge'):
    if stage == 'team' and (profile.get('taskModel') or split_ref(selection(profile))):
        return 'This agent’s selected Open Task model is unavailable. Check its connection or choose Automatic in the model picker.'
    if stage == 'team':
        return 'Open Task needs a connected External Endpoint or Local model in Settings.'
    return ('No model connection is available. Connect Local or an External Endpoint in Settings.'
            if selection(profile) == DEFAULT else
            'This agent\'s model is unavailable. Check its connection in Settings or choose another model in Edit agent.')


def prepare(studio, member, stage='lounge'):
    from studio import Problem
    # Legacy/local-only workspace preparation does not need a model-health probe.
    # Preserve this path before consulting runtime status for stage routing.
    chosen = member.get('taskModel', selection(member)) if stage == 'team' else selection(member)
    if not connections.enabled() and (chosen == LEGACY or chosen == DEFAULT and settings.read()['provider'] == 'local'):
        return
    runtime = studio.runtime_status()
    chosen = effective_selection(member, runtime, stage)
    if chosen == LEGACY:
        if connections.enabled():
            connections.prepare(studio, member, connections.read().get('lounge', 'auto'), 'lounge')
        return
    if not ready(member, runtime, stage):
        raise Problem(unavailable(member, stage), 503)
    source = 'local' if chosen == DEFAULT else 'api'
    value = connections.profile(source)
    if source == 'api':
        provider, model = split_ref(chosen)
        if value['_provider'] != provider:
            raise Problem(unavailable(member, stage), 503)
        value['model'] = model
    connections.bind(studio, member, value, 'lounge')

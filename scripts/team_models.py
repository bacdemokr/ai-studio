"""Dedicated NVIDIA models with a host-persisted Stage 3 credential."""
import copy
import json
import os
import re
import tempfile

BASE_URL = 'https://inference-api.nvidia.com/v1'
MODELS = ('nvidia/nvidia/nemotron-3-ultra-nvfp4', 'nvidia/nvidia/nemotron-3.5-lightning')
LABELS = ('Nemotron 3 Ultra', 'Nemotron 3.5 Lightning')
_catalog = [{'id':m,'label':label} for m,label in zip(MODELS,LABELS)]


def credential_path():
    import ops_common as c
    return c.home() / 'credentials' / 'stage3.json'


def saved_connection():
    try:
        value = json.loads(credential_path().read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def credentials():
    import runtime_settings as settings
    import session_secrets as secrets
    key = saved_connection().get('apiKey')
    if isinstance(key, str) and key:
        return {'baseUrl': BASE_URL, 'apiKey': key, 'model': MODELS[0]}
    return secrets.get(settings.secret_key('team'))


def save_connection(key, models):
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.stage3-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'apiKey': key, 'models': models}, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

def valid_model(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}',value))


def role_for(agent):
    match = re.fullmatch(r'bac-[0-9a-f]{24}-r([0-8])', agent)
    return int(match[1]) if match else None


def default_model(role):
    # Captain, programmer and UX designer use Ultra; other specialists use Lightning.
    return MODELS[0 if role in (0, 5, 7) else 1]


def local_provider(agent):
    return 'bac-team-local-' + agent.split('-')[1] if role_for(agent) is not None else None


def model_for(agent, selected=None):
    role = role_for(agent)
    if role is None:return None
    prefix = local_provider(agent) + '/'
    if isinstance(selected, str) and selected.startswith(prefix) and valid_model(selected[len(prefix):]):
        return selected
    if isinstance(selected,str) and selected.startswith('bac-team/'):
        selected=selected[len('bac-team/'):]
        if valid_model(selected):return 'bac-team/'+selected
    if valid_model(selected) and selected in {m['id'] for m in _catalog}:return 'bac-team/'+selected
    return 'bac-team/'+default_model(role)


def public():
    models = saved_connection().get('models', _catalog)
    models = [{'id': m['id'], 'label': m.get('label', m['id'])} for m in models
              if isinstance(m, dict) and valid_model(m.get('id'))] if isinstance(models, list) else list(_catalog)
    return {'connected':bool(credentials().get('apiKey')), 'models':models}


def apply(config, selected=None, local=None, agent_id=None):
    import runtime_settings as settings
    import session_secrets as secrets
    ids=set(MODELS)
    if valid_model(selected) and not selected.startswith('bac-team-local-'):ids.add(selected.removeprefix('bac-team/'))
    for agent,entry in config.get('agents',{}).get('entries',{}).items():
        model=model_for(agent,entry.get('model'))
        if model and model.startswith('bac-team/'):ids.add(model.removeprefix('bac-team/'))
    config.setdefault('models',{}).setdefault('providers',{})['bac-team']={
        'baseUrl':secrets.proxy_url('team',BASE_URL),'apiKey':'session-only','api':'openai-completions',
        'models':[{'id':m,'name':m,'input':['text'],'reasoning':False,'contextWindow':32768,
                   'contextTokens':32768,'maxTokens':settings.MAX_OUTPUT_TOKENS,
                   'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}} for m in sorted(ids)]}
    if local is not None and local_provider(agent_id):
        context = local['contextWindow']
        config['models']['providers'][local_provider(agent_id)] = {
            'baseUrl': local['baseUrl'], 'apiKey': 'local-only', 'api': 'openai-completions',
            'models': [{'id': local['model'], 'name': local['model'], 'input': ['text'], 'reasoning': False,
                        'contextWindow': context, 'contextTokens': context, 'maxTokens': min(settings.MAX_OUTPUT_TOKENS, context // 4),
                        'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}}]}
    for agent,entry in config.get('agents',{}).get('entries',{}).items():
        model=model_for(agent,entry.get('model'))
        if model:entry.update(model=model,modelPolicy={'allow':[model]})
    return config


def configure(studio,data):
    global _catalog
    import agent_runtime as runtime
    import runtime_settings as settings
    import session_secrets as secrets
    import ops_common as c
    from studio import Problem
    provider,profile=settings.validate({'provider':'nvidia','baseUrl':BASE_URL,'model':MODELS[0],
                                       'apiKey':data.get('apiKey',''),'_credentialSession':data.get('_credentialSession')})
    if not data.get('apiKey'):raise Problem('Enter the dedicated Multi-Agent Demo API key.')
    available=settings.request(provider,profile,'/models',timeout=25)
    ids={row.get('id') for row in available.get('data',[]) if isinstance(row,dict) and valid_model(row.get('id'))}
    if not set(MODELS).issubset(ids):raise Problem('The dedicated API key must provide both configured Nemotron models.',502)
    with studio.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','waiting','stopping') LIMIT 1").fetchone():
            raise Problem('Finish or cancel pending missions before changing team models.',409)
        _catalog=[{'id':m,'label':dict(zip(MODELS,LABELS)).get(m,m)} for m in sorted(ids) if valid_model(m)]
        with runtime.config_lock():
            config=copy.deepcopy(c.read_json(runtime.config_path(),None) or runtime.initial_config())
            runtime.save_config(apply(config))
        save_connection(profile['apiKey'], _catalog)
        secrets.remove(settings.secret_key('team'))
        studio.provisioned.clear();studio.status_cache=(0,{})
    return public()


def selections(studio, owner):
    with studio.db() as db:
        saved={r['role']:r['model'] for r in db.execute('SELECT role,model FROM crew_resources WHERE owner=?',(owner,))}
    return [{'id':saved.get(role) if valid_model(saved.get(role)) else default_model(role),
             'role':role} for role in range(9)]


def select(studio, owner, data):
    from studio import Problem, CREW_CATALOG
    role,model=data.get('role'),data.get('model')
    eligible = set(range(4)) if studio.crew_scenario(owner)=='event-brief' else {i for i,m in enumerate(CREW_CATALOG) if m.get('planEligible',True)}
    if type(role) is not int or role not in eligible or model not in {m['id'] for m in public()['models']}:
        raise Problem('Choose a team member and an available model.')
    with studio.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM agents WHERE id=? AND kind='crew' AND deleting=0",(owner,)).fetchone():
            raise Problem('Team not found.',404)
        studio.require_bac_not_resetting(db,owner)
        studio.require_team_idle(db,owner)
        if db.execute("SELECT 1 FROM jobs WHERE owner=? AND status IN ('queued','running','waiting','stopping')",(owner,)).fetchone():
            raise Problem('Wait for the current team task to finish before changing models.',409)
        resource=db.execute('SELECT native_id FROM crew_resources WHERE owner=? AND role=?',(owner,role)).fetchone()
        if not resource:raise Problem('Team member not found.',404)
        db.execute('UPDATE crew_resources SET model=? WHERE owner=? AND role=?',(model,owner,role))
        # Provisioning applies the preference before the next request; no idle
        # native agent, container or credential is created by a model selection.
        studio.provisioned.discard(resource['native_id'])
    return {'teamSelections':selections(studio,owner)}

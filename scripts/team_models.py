"""Dedicated, session-only NVIDIA models for the built-in BaC team."""
import copy
import re

BASE_URL = 'https://inference-api.nvidia.com/v1'
MODELS = ('nvidia/nvidia/nemotron-3-ultra-nvfp4', 'nvidia/nvidia/nemotron-3.5-lightning')
LABELS = ('Nemotron 3 Ultra', 'Nemotron 3.5 Lightning')


def role_for(agent):
    match = re.fullmatch(r'bac-[0-9a-f]{24}-r([0-8])', agent)
    return int(match[1]) if match else None


def model_for(agent, selected=None):
    role = role_for(agent)
    if role is None:return None
    if selected in MODELS:return 'bac-team/'+selected
    if selected in ['bac-team/'+m for m in MODELS]:return selected
    return 'bac-team/'+MODELS[0 if role == 0 else 1]


def public():
    import runtime_settings as settings
    import session_secrets as secrets
    return {'connected':bool(secrets.get(settings.secret_key('team')).get('apiKey')),
            'models':[{'id':m,'label':label} for m,label in zip(MODELS,LABELS)]}


def apply(config):
    import runtime_settings as settings
    import session_secrets as secrets
    config.setdefault('models',{}).setdefault('providers',{})['bac-team']={
        'baseUrl':secrets.proxy_url('team',BASE_URL),'apiKey':'session-only','api':'openai-completions',
        'models':[{'id':m,'name':m,'input':['text'],'reasoning':False,'contextWindow':32768,
                   'contextTokens':32768,'maxTokens':settings.MAX_OUTPUT_TOKENS,
                   'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}} for m in MODELS]}
    for agent,entry in config.get('agents',{}).get('entries',{}).items():
        model=model_for(agent,entry.get('model'))
        if model:entry.update(model=model,modelPolicy={'allow':[model]})
    return config


def configure(studio,data):
    import agent_runtime as runtime
    import runtime_settings as settings
    import session_secrets as secrets
    import ops_common as c
    from studio import Problem
    provider,profile=settings.validate({'provider':'nvidia','baseUrl':BASE_URL,'model':MODELS[0],
                                       'apiKey':data.get('apiKey',''),'_credentialSession':data.get('_credentialSession')})
    if not data.get('apiKey'):raise Problem('Enter the dedicated Multi-Agent Demo API key.')
    available=settings.request(provider,profile,'/models',timeout=25)
    ids={row.get('id') for row in available.get('data',[]) if isinstance(row,dict)}
    if not set(MODELS).issubset(ids):raise Problem('The dedicated API key must provide both configured Nemotron models.',502)
    with studio.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','waiting','stopping') LIMIT 1").fetchone():
            raise Problem('Finish or cancel pending missions before changing team models.',409)
        with runtime.config_lock():
            config=copy.deepcopy(c.read_json(runtime.config_path(),None) or runtime.initial_config())
            runtime.save_config(apply(config))
        secrets.put(settings.secret_key('team'),profile,data.get('_credentialSession','direct'))
        studio.provisioned.clear();studio.status_cache=(0,{})
    return public()


def selections(studio, owner):
    with studio.db() as db:
        saved={r['role']:r['model'] for r in db.execute('SELECT role,model FROM crew_resources WHERE owner=?',(owner,))}
    return [{'id':saved.get(role) if saved.get(role) in MODELS else MODELS[0 if role==0 else 1],
             'role':role} for role in range(9)]


def select(studio, owner, data):
    from studio import Problem
    role,model=data.get('role'),data.get('model')
    if type(role) is not int or role not in (0,2,3,4,5,6,7,8) or model not in MODELS:
        raise Problem('Choose a team member and an available model.')
    with studio.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM agents WHERE id=? AND kind='crew' AND deleting=0",(owner,)).fetchone():
            raise Problem('Team not found.',404)
        studio.require_bac_not_resetting(db,owner)
        studio.require_event_crew_idle(db,owner)
        if db.execute("SELECT 1 FROM jobs WHERE owner=? AND status IN ('queued','running','waiting','stopping')",(owner,)).fetchone():
            raise Problem('Wait for the current team task to finish before changing models.',409)
        resource=db.execute('SELECT native_id FROM crew_resources WHERE owner=? AND role=?',(owner,role)).fetchone()
        if not resource:raise Problem('Team member not found.',404)
        db.execute('UPDATE crew_resources SET model=? WHERE owner=? AND role=?',(model,owner,role))
        # Provisioning applies the preference before the next request; no idle
        # native agent, container or credential is created by a model selection.
        studio.provisioned.discard(resource['native_id'])
    return {'teamSelections':selections(studio,owner)}

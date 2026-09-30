"""Dedicated, session-only NVIDIA models for the built-in BaC team."""
import copy
import re

BASE_URL = 'https://inference-api.nvidia.com/v1'
MODELS = ('nvidia/nvidia/nemotron-3-ultra-nvfp4', 'nvidia/nvidia/nemotron-3.5-lightning')
LABELS = ('Nemotron 3 Ultra', 'Nemotron 3.5 Lightning')


def role_for(agent):
    match = re.fullmatch(r'bac-[0-9a-f]{24}-r([0-8])', agent)
    return int(match[1]) if match else None


def model_for(agent):
    role = role_for(agent)
    return 'bac-team/' + MODELS[0 if role == 0 else 1] if role is not None else None


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
        model=model_for(agent)
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

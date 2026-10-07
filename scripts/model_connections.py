"""Shared connection inventory and stage preferences. No credentials on disk."""
import copy
import json
import threading
import time
import hashlib
import ops_common as c
import runtime_settings as settings
import session_secrets as secrets

_lock = threading.RLock()
_checks = {}
_pending = set()


def path():return c.home() / 'model-connections.json'
def enabled():return path().exists()
def read():return c.read_json(path(), {'apiProvider':'nvidia','lounge':'auto','disabled':[]})


def persist(value):
    path().parent.mkdir(parents=True,exist_ok=True)
    temp=path().with_suffix('.new')
    temp.write_text(json.dumps(value));temp.chmod(0o600);temp.replace(path())


def profile(source):
    import team_models
    saved=read();provider='local' if source=='local' else saved.get('apiProvider','nvidia')
    value=copy.deepcopy(settings.read().get('profiles',{}).get(provider,{}))
    value.update(secrets.get(settings.secret_key(provider)))
    if provider=='nvidia' and not value.get('apiKey'):
        fallback=team_models.credentials()
        if fallback.get('apiKey'):
            for field in ('apiKey','baseUrl'):value[field]=fallback[field]
            value.setdefault('model',fallback['model'])
            value['_credentialProvider']='team'
    value.setdefault('baseUrl',settings.PROVIDERS[provider]['baseUrl'])
    value.setdefault('contextWindow',32768)
    value['_provider']=provider
    value.setdefault('apiKey','')
    return value


def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def probe(source,value):
    key=signature(value)
    try:
        provider=value['_provider']
        result=settings.request(provider,value,'/v1/models?limit=1000' if provider=='anthropic' else '/models',timeout=8)
        rows=result.get('data',[]) if isinstance(result,dict) else []
        ready=any(isinstance(row,dict) and row.get('id')==value.get('model') for row in rows)
        state={'ready':ready,'message':'Ready' if ready else 'Selected model is not available.','checkedAt':time.time()}
    except Exception as error:
        from studio import Problem
        state={'ready':False,'message':str(error) if isinstance(error,Problem) else 'Connection check failed.','checkedAt':time.time()}
    with _lock:
        _checks[key]=(time.monotonic(),state);_pending.discard(key)
    return state


def status(source,refresh=False):
    value=profile(source);key=signature(value)
    basic={'provider':value['_provider'],'model':value.get('model',''),'baseUrl':value['baseUrl'],'contextWindow':value['contextWindow'],'enabled':source not in read().get('disabled',[])}
    if source in read().get('disabled',[]):return {**basic,'ready':False,'message':'Disabled'}
    if not value.get('model') or (source=='api' and not value.get('apiKey')):
        return {**basic,'ready':False,'message':'Not configured'}
    with _lock:
        cached=_checks.get(key)
        if refresh or not cached or time.monotonic()-cached[0]>30:
            if key not in _pending:
                _pending.add(key)
                threading.Thread(target=probe,args=(source,value),daemon=True,name='model-connection-check').start()
        state=cached[1] if cached and time.monotonic()-cached[0]<90 else {'ready':False,'message':'Checking…'}
    return {**basic,**state}


def choose(preference,stage,states):
    preferred=('local' if stage=='lounge' else 'api') if preference=='auto' else preference
    other='api' if preferred=='local' else 'local'
    return preferred if states[preferred]['ready'] else other if states[other]['ready'] else None


def public(refresh=False):
    states={s:status(s,refresh) for s in ('local','api')}
    return {'connections':states,'loungePreference':read().get('lounge','auto'),
            'loungeSource':choose(read().get('lounge','auto'),'lounge',states),'enabled':enabled()}


def resolve(preference='auto',stage='team'):
    state=public();source=choose(preference,stage,state['connections'])
    return source,profile(source) if source else None


def idle(studio,db):
    from studio import Problem
    if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','waiting','stopping') LIMIT 1").fetchone():
        raise Problem('Finish or stop active work before changing model connections.',409)


def configure(studio,data):
    from studio import Problem
    source=data.get('source')
    if source not in ('local','api'):raise Problem('Choose Local model or API.')
    with studio.db() as db:idle(studio,db)
    provider=data.get('provider') if source=='api' else 'local'
    if provider not in ('nvidia','openai','anthropic') and source=='api':raise Problem('Choose an API provider.')
    request={**data,'provider':provider}
    # api.cfg can supply NVIDIA without entering its key again.
    if provider=='nvidia' and not request.get('apiKey'):
        import team_models
        request['apiKey']=team_models.credentials().get('apiKey','')
    provider,value=settings.validate(request)
    settings.verify_connection(provider,value)
    with _lock,studio.db() as db:
        db.execute('BEGIN IMMEDIATE');idle(studio,db)
        saved=settings.read();saved.setdefault('profiles',{})[provider]=value;settings.persist(saved)
        secrets.put(settings.secret_key(provider),value,data.get('_credentialSession','direct'))
        config=read();config['disabled']=[s for s in config.get('disabled',[]) if s!=source]
        if source=='api':config['apiProvider']=provider
        persist(config)
        checked=profile(source)
        _checks[signature(checked)]=(time.monotonic(),{'ready':True,'message':'Ready','checkedAt':time.time()})
        studio.provisioned.clear();studio.status_cache=(0,{})
    return public()


def preferences(studio,data,owner=None):
    from studio import Problem
    preference=data.get('lounge','auto')
    if preference not in ('auto','local','api'):raise Problem('Choose Auto, Local model or API.')
    team=data.get('team')
    if team is not None and team not in ('auto','local','api'):raise Problem('Choose Auto, Local model or API.')
    with _lock,studio.db() as db:
        db.execute('BEGIN IMMEDIATE');idle(studio,db)
        saved=read();saved['lounge']=preference
        if 'disable' in data:
            source=data['disable']
            if source not in ('local','api'):raise Problem('Choose a connection.')
            saved['disabled']=list(set(saved.get('disabled',[]))|{source})
        if 'enable' in data:
            source=data['enable']
            if source not in ('local','api'):raise Problem('Choose a connection.')
            saved['disabled']=[s for s in saved.get('disabled',[]) if s!=source]
        if team is not None and owner:
            db.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)',('scenario-model:'+owner,json.dumps({'provider':team})))
        persist(saved);studio.provisioned.clear();studio.status_cache=(0,{})
    result=public()
    if owner:
        from scenario_models import connection
        result['teamConnection']=connection(studio,owner)
    return result


def native(value):
    provider=value['_provider'];credential=value.get('_credentialProvider',provider)
    return {'baseUrl':secrets.proxy_url(credential,value['baseUrl']) if value.get('apiKey') else value['baseUrl'],
            'apiKey':'session-only' if value.get('apiKey') else 'local-only','api':settings.PROVIDERS[provider]['api'],
            'models':[{'id':value['model'],'name':value['model'],'input':['text'],'reasoning':False,
                       'contextWindow':value['contextWindow'],'contextTokens':value['contextWindow'],
                       'maxTokens':min(settings.MAX_OUTPUT_TOKENS,value['contextWindow']//4),
                       'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}}]}


def prepare(studio,member,preference='auto',stage='team'):
    from studio import Problem
    source,value=resolve(preference,stage)
    if not value:raise Problem('Model not connected. Configure a Local model or API in Settings.',503)
    # Copy only the sanitized runtime provider, never a credential, into agent instructions.
    if source=='api' and value['_provider']=='nvidia' and stage=='team':
        import team_models
        selected=member.get('_teamModel')
        if selected in {m['id'] for m in team_models.public()['models']}:value['model']=selected
    provider=native(value)
    if stage=='lounge':provider['models'][0]['input']=['text','image']
    member['_connectionConfig']=provider
    stamp=signature(provider)
    routes=studio.__dict__.setdefault('_connection_routes',{})
    if routes.get(member['id'])!=stamp:studio.provisioned.discard(member['id']);routes[member['id']]=stamp
    return source,value


def provider_id(agent):
    return 'bac-connection-'+hashlib.sha256(agent.encode()).hexdigest()[:24]


def models(data):
    if data.get('provider')=='nvidia' and not data.get('apiKey'):
        import team_models
        data={**data,'apiKey':team_models.credentials().get('apiKey','')}
    return settings.models(data)

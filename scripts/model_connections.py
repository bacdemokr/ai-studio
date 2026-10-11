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
_discovered = {}


def path():return c.home() / 'model-connections.json'
def enabled():return path().exists()
def read():return c.read_json(path(), {'apiProvider':'nvidia','lounge':'auto','disabled':[]})


def persist(value):
    path().parent.mkdir(parents=True,exist_ok=True)
    temp=path().with_suffix('.new')
    temp.write_text(json.dumps(value));temp.chmod(0o600);temp.replace(path())


def initialize():
    """Migrate the selected host provider once, without copying credentials."""
    with _lock:
        if enabled():return
        value=read();previous=settings.read();provider=previous.get('provider')
        if provider in settings.PROVIDERS and previous.get('profiles',{}).get(provider):
            value['lounge']='local' if provider=='local' else 'api'
            if provider!='local':value['apiProvider']=provider
        persist(value)


def profile(source, discovery=True):
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
    if value.get('apiKey'):
        stored=team_models.saved_connection() if provider=='nvidia' else {}
        value['_keySource']=stored.get('source','host') if stored.get('apiKey')==value['apiKey'] else 'session'
    if source == 'local' and discovery and not value.get('model'):
        with _lock:
            detected = _discovered.get((str(path()), signature(value)))
        if detected:
            value.update(detected, _autoDetected=True)
    return value


def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def catalog(rows):
    import team_models
    return [{'id':row['id'],'label':row.get('display_name') or dict(zip(team_models.MODELS,team_models.LABELS)).get(row['id'],row['id'])} for row in (rows or []) if isinstance(row,dict) and team_models.valid_model(row.get('id'))]


def probe(source,value):
    key=signature(value)
    automatic = source == 'local' and (not value.get('model') or value.get('_autoDetected'))
    with _lock:
        # A queued probe may start after Settings changed. Never associate an old
        # endpoint's catalogue with the new endpoint's discovery baseline.
        if automatic and signature(profile(source)) != key:
            _pending.discard(key)
            return {'ready':False, 'message':'Connection settings changed. Checking again.', 'checkedAt':time.time()}
        baseline = profile(source, discovery=False) if automatic else None
        discovery_key = (str(path()), signature(baseline)) if automatic else None
    detected = None
    try:
        provider=value['_provider']
        result=settings.request(provider,value,'/v1/models?limit=1000' if provider=='anthropic' else '/models',timeout=8)
        rows=result.get('data',[]) if isinstance(result,dict) else []
        message = None
        if automatic:
            valid_ids = {model['id'] for model in catalog(rows)}
            candidates = {row['id']:row for row in rows if isinstance(row, dict) and row.get('id') in valid_ids}
            if len(candidates) == 1:
                model, row = next(iter(candidates.items()))
                limit = row.get('max_model_len')
                context = baseline['contextWindow']
                if type(limit) is int:
                    context = min(context, limit)
                if context >= 8192:
                    detected = {'model':model, 'contextWindow':context}
                    value = {**baseline, **detected, '_autoDetected':True}
                else:
                    message = 'Local model context is below the supported 8,192-token minimum.'
            else:
                message = ('Multiple local models found. Choose one in Settings.' if candidates else
                           'No local model is available yet.')
        ready=not message and any(isinstance(row,dict) and row.get('id')==value.get('model') for row in rows)
        state={'ready':ready,'message':message or ('Ready' if ready else 'Selected model is not available.'),'checkedAt':time.time(),'models':catalog(rows)}
    except Exception as error:
        from studio import Problem
        state={'ready':False,'message':str(error) if isinstance(error,Problem) else 'Connection check failed.','checkedAt':time.time()}
    with _lock:
        if automatic and signature(profile(source, discovery=False)) == discovery_key[1]:
            # Discovery is runtime-only; explicit settings and routing stay intact.
            if detected:
                _discovered[discovery_key] = detected
            elif 'models' in state:
                _discovered.pop(discovery_key, None)
            _checks[discovery_key[1]] = (time.monotonic(), state)
            _checks[signature(value)] = (time.monotonic(), state)
        _checks[key]=(time.monotonic(),state);_pending.discard(key)
    return state


def status(source,refresh=False):
    value=profile(source);key=signature(value)
    basic={'provider':value['_provider'],'model':value.get('model',''),'baseUrl':value['baseUrl'],'contextWindow':value['contextWindow'],'keySource':value.get('_keySource'),'enabled':source not in read().get('disabled',[])}
    if source in read().get('disabled',[]):return {**basic,'ready':False,'message':'Disabled'}
    if (source=='api' and (not value.get('model') or not value.get('apiKey'))) or (source=='local' and not value.get('model') and not enabled()):
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
    request=with_nvidia_key(request)
    provider,value=settings.validate(request)
    rows=settings.verify_connection(provider,value)
    with _lock,studio.db() as db:
        db.execute('BEGIN IMMEDIATE');idle(studio,db)
        saved=settings.read();saved.setdefault('profiles',{})[provider]=value;settings.persist(saved)
        secrets.put(settings.secret_key(provider),value,data.get('_credentialSession','direct'))
        config=read();config['disabled']=[s for s in config.get('disabled',[]) if s!=source]
        if source=='api':config['apiProvider']=provider
        persist(config)
        checked=profile(source)
        _checks[signature(checked)]=(time.monotonic(),{'ready':True,'message':'Ready','checkedAt':time.time(),'models':catalog(rows)})
        studio.provisioned.clear();studio.status_cache=(0,{})
    return public()


def preferences(studio,data,owner=None,participant=None):
    from studio import Problem
    preference=data.get('lounge','auto')
    if preference not in ('auto','local','api'):raise Problem('Choose Auto, Local model or API.')
    team=data.get('team')
    if team is not None and team not in ('auto','local','api'):raise Problem('Choose Auto, Local model or API.')
    scenarios=data.get('scenarios',{})
    if not isinstance(scenarios,dict) or any(k not in ('event-brief','plan') or v not in ('auto','local','api') for k,v in scenarios.items()):raise Problem('Choose a valid connection for each scenario.')
    if scenarios and not participant:raise Problem('Open your Settings before changing scenarios.')
    owners={key:studio.crew_owner(participant,key) for key in scenarios}
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
        for key,scenario_owner in owners.items():
            db.execute('INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)',('scenario-model:'+scenario_owner,json.dumps({'provider':scenarios[key]})))
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
                       'maxTokens':settings.output_token_limit(value['contextWindow']),
                       'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}}]}


def prepare(studio,member,preference='auto',stage='team'):
    from studio import Problem
    source,value=resolve(preference,stage)
    if not value:raise Problem('Model not connected. Configure a Local model or API in Settings.',503)
    # Copy only the sanitized runtime provider, never a credential, into agent instructions.
    if source=='api' and value['_provider']=='nvidia' and stage=='team' and member.get('_scenario')!='event-brief':
        import team_models
        selected=member.get('_teamModel')
        if selected:
            if selected not in {m['id'] for m in team_models.available_models()}:
                raise Problem('This agent’s selected model is unavailable on the current API connection. Choose another model for this agent.',503)
            value['model']=selected
    bind(studio,member,value,stage)
    return source,value


def bind(studio,member,value,stage='team'):
    provider=native(value)
    if stage=='lounge':provider['models'][0]['input']=['text','image']
    member['_connectionConfig']=provider
    stamp=signature(provider)
    routes=studio.__dict__.setdefault('_connection_routes',{})
    if routes.get(member['id'])!=stamp:studio.provisioned.discard(member['id']);routes[member['id']]=stamp


def provider_id(agent):
    return 'bac-connection-'+hashlib.sha256(agent.encode()).hexdigest()[:24]


def with_nvidia_key(data):
    # Explicit key, then this tab's current connection, then the host fallback.
    # Only forward saved credentials to the destination they belong to.
    if data.get('provider')!='nvidia' or data.get('apiKey'):
        return data
    saved=settings.read().get('profiles',{}).get('nvidia',{})
    base=data.get('baseUrl',saved.get('baseUrl',settings.PROVIDERS['nvidia']['baseUrl']))
    session=secrets.get(settings.secret_key('nvidia'),data.get('_credentialSession','direct'))
    if session.get('apiKey') and isinstance(base,str) and base.rstrip('/')==saved.get('baseUrl'):
        return {**data,'apiKey':session['apiKey']}
    import team_models
    fallback=team_models.credentials()
    if isinstance(base,str) and base.rstrip('/')==fallback.get('baseUrl'):
        return {**data,'apiKey':fallback.get('apiKey','')}
    return data


def models(data):
    return settings.models(with_nvidia_key(data))



def scenario_preferences(studio,participant):
    result={}
    for key in ('event-brief','plan'):
        owner=studio.existing_crew_owner(participant,key)
        with studio.db() as db:
            row=db.execute('SELECT value FROM metadata WHERE key=?',('scenario-model:'+owner,)).fetchone() if owner else None
        result[key]=json.loads(row['value']).get('provider','auto') if row else 'auto'
    return result


def public_for(studio,participant):
    return {**public(),'scenarioPreferences':scenario_preferences(studio,participant)}

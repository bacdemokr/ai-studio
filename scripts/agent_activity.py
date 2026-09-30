"""Read observed tool calls from OpenClaw's native transcript, excluding hidden reasoning and file contents."""
import json
from pathlib import Path
import shlex
import re
import sqlite3
import posixpath
from contextlib import closing


def custom_skill_paths(config, agent, catalog):
    """Only this agent's equipped project skills, at its real workspace paths."""
    if not isinstance(config,dict):return {}
    entry=config.get('agents',{}).get('entries',{}).get(agent,{})
    workspace=entry.get('workspace')
    if not workspace:return {}
    roots=[workspace]
    sandbox=entry.get('sandbox',{})
    if sandbox.get('mode')!='off' and sandbox.get('backend')=='openshell':
        remote=config.get('plugins',{}).get('entries',{}).get('openshell',{}).get('config',{}).get('remoteWorkspaceDir','/sandbox')
        roots.append(remote)
    paths={}
    for name in entry.get('skills',[]):
        if name not in catalog:continue
        relative='skills/'+name+'/SKILL.md'
        skill={'id':name,'label':catalog[name]}
        for path in [relative]+[str(Path(root)/relative) for root in roots]:
            paths[posixpath.normpath(path)]=skill
    return paths


def collect(state, agent, session, started=0, skill_paths=None):
    path=Path(state)/'agents'/agent/'agent/openclaw-agent.sqlite'
    if not path.is_file():return {'source':'OpenClaw transcript','available':False,'calls':[]}
    try:
        with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=2) as db:
            rows=db.execute('''SELECT t.event_json FROM transcript_events t JOIN session_windows s USING(session_id)
                WHERE s.session_key=? AND t.created_at>=? ORDER BY t.seq LIMIT 2000''',
                ('agent:'+agent+':openai-user:'+session,int(started*1000))).fetchall()
        calls={}
        for row in rows:
            event=json.loads(row[0]);message=event.get('message',{})
            if message.get('role')=='assistant':
                for item in message.get('content',[]) if isinstance(message.get('content'),list) else []:
                    if item.get('type')!='toolCall':continue
                    name=item.get('name','');args=item.get('arguments',{})
                    if not isinstance(args,dict):continue
                    target=str(args.get('path') or args.get('file_path') or args.get('url') or args.get('query') or '')[:500]
                    command=str(args.get('command',''))
                    action='';actions=[]
                    if name=='exec':
                        try:
                            lexer=shlex.shlex(command,posix=True,punctuation_chars=';&|<>');lexer.whitespace_split=True
                            parts=list(lexer)
                            indexes=[i for i,x in enumerate(parts) if x.endswith('/event_agent_tools.py') and i>0 and re.fullmatch(r'python(?:3(?:\.\d+)?)?',Path(parts[i-1]).name) and i+1<len(parts) and parts[i+1] in ('search','read','draft-schedule','schedule')]
                            if indexes:
                                action=parts[indexes[0]+1];target=' '.join(parts[indexes[0]:])[:500]
                                # Only a single command or an && chain proves every action
                                # succeeded. A later command after ; can mask a failed tool.
                                if not any(p in (';','||','|','&','>','>>','<','<<','>&') for p in parts):
                                    actions=[parts[i+1] for i in indexes]
                            else:target='Shell command'
                        except ValueError:target='Shell command'
                    calls[item['id']]={'id':item['id'],'tool':name,'target':target,'action':action,'actions':actions,'time':event.get('timestamp'),'status':'started'}
            elif message.get('role')=='toolResult' and message.get('toolCallId') in calls:
                call=calls[message['toolCallId']];details=message.get('details') or {}
                failed=message.get('isError') or details.get('exitCode',0) not in (0,None) or details.get('status') in ('error','failed')
                call['status']='failed' if failed else 'running' if details.get('status')=='running' else 'completed'
        for call in calls.values():
            # Reading a skill is observable; mentioning or equipping one is not use.
            if call['tool']=='read' and call['status']=='completed':
                skill=(skill_paths or {}).get(posixpath.normpath(call['target']))
                if skill:call['customSkill']=dict(skill)
        return {'source':'OpenClaw transcript','available':True,'calls':list(calls.values())}
    except (OSError,ValueError,TypeError,sqlite3.Error):return {'source':'OpenClaw transcript','available':False,'calls':[]}


def require_action(activity, action):
    if not any(c.get('tool')=='exec' and action in c.get('actions',[c.get('action')]) and c.get('status')=='completed' for c in activity.get('calls',[])):
        raise ValueError('No completed '+action+' tool call was observed in the native agent transcript.')


def heartbeat_failure(state, agent, started):
    """Return only a fixed operational diagnosis, never raw transcript contents."""
    path=Path(state)/'agents'/agent/'agent/openclaw-agent.sqlite'
    if not path.is_file():return None
    try:
        with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=2) as db:
            rows=db.execute("""SELECT t.event_json,t.created_at FROM transcript_events t
                JOIN session_windows s USING(session_id) WHERE s.session_key=? AND t.created_at>=?
                ORDER BY t.created_at DESC,t.seq DESC LIMIT 100""",
                ('agent:'+agent+':heartbeat-radar:heartbeat',int(started*1000))).fetchall()
        for raw,stamp in rows:
            message=json.loads(raw).get('message',{})
            if message.get('role')!='toolResult' or message.get('toolName')!='exec':continue
            content=message.get('content',[])
            text=' '.join(str(item.get('text','')) for item in content if isinstance(item,dict)) if isinstance(content,list) else ''
            if 'ENOENT' in text and 'launch' in text:
                return {'time':stamp/1000,'code':'execution-failed','message':'Heartbeat could not launch its command. Check the agent runtime; no website-policy denial was confirmed.'}
            # A later successful exec supersedes an earlier launch failure.
            return None
    except (OSError,ValueError,TypeError,sqlite3.Error):pass
    return None


def model_failure(state, agent, session, started, output_limit):
    """Diagnose only this invocation; never expose model text, arguments or keys."""
    path = Path(state) / 'agents' / agent / 'agent/openclaw-agent.sqlite'
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.2)) as db:
            rows = db.execute('''SELECT t.event_json FROM transcript_events t
                JOIN session_windows s USING(session_id)
                WHERE s.session_key=? AND t.created_at>=?
                ORDER BY t.created_at DESC,t.seq DESC LIMIT 20''',
                ('agent:' + agent + ':openai-user:' + session, int(started * 1000))).fetchall()
        for raw, in rows:
            message = json.loads(raw).get('message', {})
            if message.get('role') != 'assistant':
                continue
            # OpenClaw can convert an empty length-stopped native response into
            # HTTP 500, losing finish_reason in its compatibility response.
            # Usage may report only one output token, so do not require 8192.
            if message.get('stopReason') == 'length':
                return {'code': 'output-limit', 'message':
                    'The model stopped at a generation length limit before finishing. '
                    'Accumulated context may leave too little room for the answer. '
                    'Saved work is preserved; the request was not automatically repeated.'}
            error = str(message.get('errorMessage', ''))
            malformed = error in {
                'Provider returned an incomplete or malformed tool call',
                'Provider completed tool call with malformed JSON arguments',
                'Provider completed stream with an incomplete tool call',
            }
            if malformed:
                output = (message.get('usage') or {}).get('output')
                capped = type(output) is int and output >= output_limit
                return {'code': 'tool-call-output-limit' if capped else 'malformed-tool-call',
                    'message': 'The model returned an incomplete or invalid tool call.' +
                    (f' Its output reached the configured {output_limit:,}-token limit, which may have cut the call short.' if capped else '') +
                    ' Saved work is preserved. The request was not automatically repeated.'}
            if error:
                lowered = error.lower()
                # Some providers wrap their database saturation in HTTP 401.
                # Do not misdiagnose that explicit infrastructure error as a bad key.
                if any(text in lowered for text in ('remaining connection slots are reserved',
                                                     'too many connections', 'too many clients already')):
                    return {'code': 'provider-capacity', 'message':
                        'The model service could not accept the request because its connection capacity was exhausted. '
                        'Saved work is preserved; try again after the service recovers. The request was not automatically repeated.'}
                if re.search(r'(?:http\s*|status(?:\s+code)?[\s:=]*)(?:502|503|504)\b', lowered):
                    return {'code': 'provider-unavailable', 'message':
                        'The model service is temporarily unavailable. Saved work is preserved; the request was not automatically repeated.'}
                if re.search(r'(?:http\s*|status(?:\s+code)?[\s:=]*)429\b', lowered):
                    return {'code': 'provider-rate-limit', 'message':
                        'The model service rate limit was reached. Saved work is preserved; wait before trying again. The request was not automatically repeated.'}
            # Do not diagnose an older error after a later successful response.
            return None
    except (OSError, ValueError, TypeError, AttributeError, sqlite3.Error):
        return None

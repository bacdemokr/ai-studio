"""Tools invoked by crew agents; the application validates and binds completed outputs."""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
from html import escape
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from research_http import fetch
from urllib.parse import urlsplit


def compile_schedule(brief, capacity, spec):
    """Expand Alex's explicit slot/rotation choices; never choose a schedule for him."""
    from event_staffing import presenter_limit, presenter_duty, rest_slots, work_slots
    c = copy.deepcopy(capacity)
    issues = []
    session = spec.get('sessionMinutes')
    if type(session) is not int or not 5 <= session <= brief['session']:
        raise ValueError('Choose sessionMinutes between 5 and the requested session length.')
    reasons = spec.get('criteria', [])
    if not isinstance(reasons, list) or not reasons or any(not isinstance(x, str) or not 1 <= len(x) <= 400 for x in reasons):
        raise ValueError('Explain the scheduling criteria and tradeoffs.')
    limit = spec.get('maxConsecutiveSessions')
    if type(limit) is not int or not 1 <= limit <= max(4,work_slots(session)):
        raise ValueError('Choose a positive maxConsecutiveSessions compatible with 45-minute work blocks and 15-minute breaks.')
    plans = spec.get('booths', [])
    if not isinstance(plans, list) or len(plans) != len(c['topics']):
        raise ValueError('Supply exactly one booth plan per topic slot.')
    topics = {t['id']: t for t in c['topics']}
    seen, people, occupied, rows, booths = set(), {}, set(), [], []
    start = int(brief['startTime'][:2])*60+int(brief['startTime'][3:])
    clock = lambda n: '%02d:%02d' % divmod(n, 60)
    for plan in plans:
        if not isinstance(plan,dict):raise ValueError('Each booth plan must be a JSON object.')
        key = plan.get('topicId')
        if key not in topics or key in seen: raise ValueError('Use each supplied topic ID exactly once.')
        seen.add(key); topic = topics[key]; names = plan.get('presenters', [])
        if not isinstance(names, list) or not 1 <= len(names) <= 3 or any(not isinstance(n,str) for n in names) or len(set(names)) != len(names):
            raise ValueError('Assign 1–3 distinct presenter slots per booth.')
        allowed=presenter_limit(brief,session,topic['groups'])
        if len(names)>allowed:
            raise ValueError(f'{key} needs at most {allowed} topic presenter(s) for its visit load with hourly breaks. Remove unnecessary relief slots.')
        for name in names:
            if not isinstance(name, str) or not re.fullmatch(r'Presenter \d{2} \(unassigned\)', name):
                raise ValueError('Use named slots such as Presenter 01 (unassigned); do not invent confirmed staff.')
            if name in people and people[name] != key: raise ValueError('A presenter must keep one topic; do not assume cross-training.')
            people[name] = key
        booth = dict(booth='Booth-'+str(list(topics).index(key)+1), topicId=key, topic=topic['topic'], demo=topic['demo'],
                     presenter=' / '.join(names), harnesses='OpenClaw')
        booths.append(booth); remaining = topic['attendees']; count = 0; chosen_slots = []
        days = plan.get('days', [])
        if not isinstance(days, list) or len(days) > brief['days']: raise ValueError('Use only the event days.')
        day_seen = set()
        for day_plan in days:
            if not isinstance(day_plan,dict):raise ValueError('Each day plan must be a JSON object.')
            day = day_plan.get('day'); slots = day_plan.get('slots', []); rotation = day_plan.get('rotation', [])
            if type(day) is not int or not 1 <= day <= brief['days'] or day in day_seen: raise ValueError('Use distinct valid event days.')
            day_seen.add(day)
            if not isinstance(slots, list) or any(type(s) is not int or not 0 <= s < brief['duration']//session for s in slots) or slots != sorted(set(slots)):
                raise ValueError('Slots must be increasing, unique, zero-based and inside event hours.')
            if not isinstance(rotation, list) or not rotation or any(type(p) is not int or not 0 <= p < len(names) for p in rotation):
                raise ValueError('Choose a repeating rotation of indexes into your presenter list.')
            for i, slot in enumerate(slots):
                if remaining <= 0: raise ValueError('Do not schedule extra visits beyond the supplied attendee allocation.')
                person = names[rotation[i % len(rotation)]]
                if (day, slot, person) in occupied: raise ValueError('Presenter double booking.')
                occupied.add((day, slot, person)); count += 1
                chosen_slots.append((day-1)*(brief['duration']//session)+slot)
                seats = min(remaining, brief['groupSize']); remaining -= seats
                rows.append({**booth, 'day':day, 'start':clock(start+slot*session), 'end':clock(start+(slot+1)*session),
                             'presenter':person, 'attendees':seats, 'presenterExpertise':topic.get('presenterExpertise', 'Dedicated specialist for '+key)})
        if remaining or count != topic['groups']: raise ValueError('Cover all '+str(topic['groups'])+' visits for '+key+'.')
        # Allow staggered near-even plans rather than prescribing each visit.
        # Bound the longest unserved interval, including opening/closing edges.
        total_slots = (brief['duration']//session)*brief['days']
        ordered = sorted(chosen_slots)
        if count > 1:
            max_idle = (total_slots+count-1)//count + rest_slots(session) - 1
            gaps = [ordered[0]] + [right-left-1 for left,right in zip(ordered,ordered[1:])] + [total_slots-1-ordered[-1]]
            if max(gaps) > max_idle:
                issues.append(f'Spread {key} visits across the full event: longest empty interval '
                              f'is {max(gaps)} slots; allow at most {max_idle} ({max_idle*session} minutes). '
                              f'Keep all {count} visits; adjust only this booth slots, including opening/closing coverage.')
        topic.update(presenters=len(names), stations=1)
    duty, rest_issues = presenter_duty(brief,session,people,rows,limit)
    issues.extend(rest_issues)
    if issues:
        raise ValueError('Schedule checks failed; fix all listed issues in one edit:\n'+'\n'.join(issues))
    c.update(booths=sorted(booths,key=lambda b:b['booth']), schedule=sorted(rows,key=lambda r:(r['day'],r['start'],r['booth'])),
             presenterDuty=duty,presenterCount=len(people),reliefPresenters=max(0,len(people)-len(booths)),
             session=session,slots=(brief['duration']//session)*brief['days'],adjusted=session!=brief['session'],staff=len(people)+c['floorHosts']+1,
             staffingPolicy='tool-calculated' if spec.get('scheduleSource')=='deterministic-tool' else 'agent-authored',
             scheduleAuthor='Scheduling tool' if spec.get('scheduleSource')=='deterministic-tool' else 'Alex',
             scheduleCriteria=reasons,maxConsecutiveSessions=limit,
             assumptions='One visit per attendee. Presenter slots are unassigned. Dedicated topic specialists; session time includes handover. '+ ' '.join(reasons))
    return c


def draft_schedule(brief, capacity):
    """Calculate a candidate using the same scheduler as the form preview."""
    from event_staffing import schedule_spec
    spec = schedule_spec(brief, capacity)
    compile_schedule(brief, capacity, spec)
    return spec


class ArticleText(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer'): self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer'): self.skip=max(0,self.skip-1)
    def handle_data(self,text):
        if not self.skip:self.parts.append(text)


def read_article(url):
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname!='blogs.nvidia.com': raise ValueError('Use a retrieved NVIDIA Blog source URL.')
    raw=fetch(url)
    if len(raw)>2_000_000: raise ValueError('Article exceeds the read limit.')
    parser=ArticleText();parser.feed(raw.decode('utf-8',errors='replace'))
    return re.sub(r'\s+',' ',' '.join(parser.parts)).strip()[:16000]


def schedule_html(brief,calc):
    from event_timetable import tables
    criteria=escape(' '.join(calc['scheduleCriteria']))
    return '<section class="section" id="schedule"><h2>Presenter timetable</h2><p>Alex · '+criteria+'</p>'+tables(brief,calc)+'</section>'


def source_view(source, research_file, article_budget=None):
    """Small, explicitly extractive tool reply; saved evidence is unchanged."""
    view={k:source[k] for k in ('id','title','url','published','readAt','readError') if k in source}
    view['excerpt']=source.get('excerpt','')[:240]
    if article_budget is not None and source.get('article'):
        article=source['article']
        view.update(article=article[:article_budget], articleTruncated=len(article)>article_budget,
                    fullArticleChars=len(article), fullArticleFile=research_file)
    return view


def run(workspace, action, values):
    workspace=Path(workspace).resolve()
    contract=json.loads((workspace/'inbox/agent-task.json').read_text())
    out=workspace/'artifacts';out.mkdir(exist_ok=True)
    files=contract['files'];stamp=datetime.now(timezone.utc).isoformat()
    saved=workspace/files['research']
    previous=json.loads(saved.read_text()) if saved.exists() else {}
    if action in ('search','read','validate-themes') and previous.get('networkFailures',0)>=2:
        return {'status':'stopped','retryAllowed':False,'host':'blogs.nvidia.com',
                'message':'Research access failed twice. Stop this turn now. Check OpenShell Policy or the connection, then run the demo again. Do not try other commands or create placeholder themes.'}
    if action=='search':
        from nvidia_research import search_one
        if not 1<=len(values)<=4 or any(not 1<=len(q)<=100 for q in values): raise ValueError('Supply 1–4 concise search queries.')
        queries=list(dict.fromkeys(previous.get('queries',[])+values))
        if len(queries)>4:raise ValueError('Use at most four distinct queries per mission.')
        sources={row['url']:row for row in previous.get('sources',[])};failures=list(previous.get('failedQueries',[]));found={}
        def search(query):
            try:return query, search_one(query), None
            except Exception as error:return query, [], str(error)[:400] or type(error).__name__
        batch_failed=False
        with ThreadPoolExecutor(max_workers=min(3, len(values))) as pool:
            for query, matches, error in pool.map(search, values):
                for row in matches:found[row['url']]=row
                if error:
                    batch_failed=True
                    failures.append({'query':query,'error':error})
        for row in sorted(found.values(),key=lambda r:(r['published'],r['url']),reverse=True):
            if row['url'] in sources:
                sources[row['url']].update({k:v for k,v in row.items() if k!='id'})
            elif len(sources)<24:
                sources[row['url']]={**row,'id':'S'+str(len(sources)+1)}
        rows=list(sources.values())
        research={'retrieved':stamp,'queries':queries,'sources':rows,'failedQueries':failures,'status':'available' if rows else 'unavailable','method':'Agent-selected NVIDIA Blog search queries'}
        research['networkFailures']=previous.get('networkFailures',0)+int(batch_failed)
        saved.write_text(json.dumps(research,ensure_ascii=False,indent=2))
        result={**research,'sources':[source_view(s,files['research']) for s in rows]}
    elif action=='read':
        research=json.loads((workspace/files['research']).read_text());selected=set(values)
        if not 1<=len(selected)<=6 or not selected.issubset({s['id'] for s in research['sources']}):raise ValueError('Read 1–6 retrieved source IDs.')
        chosen = [source for source in research['sources'] if source['id'] in selected]
        def read(source):
            if source.get('article') and source.get('readAt') and not source.get('readError'):
                return source['article'], None
            try:return read_article(source['url']), None
            except Exception as error:return None, str(error)[:400] or type(error).__name__
        batch_failed=False
        with ThreadPoolExecutor(max_workers=min(3, len(chosen))) as pool:
            for source, (article, error) in zip(chosen, pool.map(read, chosen)):
                if error:
                    batch_failed=True
                    source['readError']=error
                else:source.update(article=article,readAt=source.get('readAt') if source.get('article') and not source.get('readError') else stamp);source.pop('readError',None)
        research['networkFailures']=research.get('networkFailures',0)+int(batch_failed)
        (workspace/files['research']).write_text(json.dumps(research,ensure_ascii=False,indent=2))
        # Keep each selected source visible within the native tool output limit.
        # Full retrieved text stays in the saved research file; excerpts are explicit.
        budget = min(1800, 7200 // len(chosen))
        result={'sources':[source_view(source,files['research'],budget) for source in chosen],
                'note':'Article fields are leading excerpts, not full articles. Use these for supported claims; inspect only a specific saved passage if needed. Do not copy article text into your themes file.'}
    elif action=='validate-themes':
        from event_theme_content import validate_saved_themes
        research=json.loads((workspace/files['research']).read_text())
        output=json.loads((workspace/files['demos']).read_text())
        validate_saved_themes(contract['brief'],output,research)
        result={'status':'validated','themes':len(output['demos']),'file':files['demos']}
    elif action=='draft-schedule':
        spec=draft_schedule(contract['brief'],contract['capacity'])
        plan_path=workspace/files['plan'];plan_path.parent.mkdir(parents=True,exist_ok=True)
        plan_path.write_text(json.dumps(spec,ensure_ascii=False,indent=2))
        result={'status':'drafted','plan':files['plan'],
                'topics':[{'topicId':p['topicId'],'visits':sum(len(d['slots']) for d in p['days']),
                           'presenters':len(p['presenters'])} for p in spec['booths']],
                'note':'The draft passed schedule validation. Run the schedule action once to export it.'}
    elif action=='schedule':
        from event_planner import workbook
        spec=json.loads((workspace/files['plan']).read_text());calc=compile_schedule(contract['brief'],contract['capacity'],spec)
        (workspace/files['schedule']).write_text(json.dumps({'brief':contract['brief'],'capacity':calc,'plan':spec},ensure_ascii=False,indent=2))
        (workspace/files['xlsx']).write_bytes(workbook(contract['brief'],calc))
        (workspace/files['scheduleHtml']).write_text(schedule_html(contract['brief'],calc))
        result={'status':'validated','visits':len(calc['schedule']),'presenters':calc['presenterCount'],'files':[files['schedule'],files['xlsx']]}
    else:raise ValueError('Unknown event tool action.')
    if action in ('search','read') and batch_failed:
        stopped=research['networkFailures']>=2
        result.update(status='stopped' if stopped else 'access-failed',retryAllowed=not stopped,
                      host='blogs.nvidia.com',message=(
                          'Research access failed twice. Stop this turn now. Check OpenShell Policy or the connection, then run the demo again. Do not create placeholder themes.' if stopped else
                          'Research access failed. Retry this same command once only. If it fails again, stop and report the error; do not switch queries, transports or fabricate results.'))
    with (out/'agent-tool-log.jsonl').open('a') as log:
        log.write(json.dumps({'time':stamp,'action':action,'arguments':values,'job':contract['job']})+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['search','read','validate-themes','draft-schedule','schedule']);parser.add_argument('values',nargs='*')
    args=parser.parse_args()
    try:print(json.dumps(run(Path.cwd(),args.action,args.values),ensure_ascii=False))
    except Exception as error:parser.exit(1,str(error)+'\n')

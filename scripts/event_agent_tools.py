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
import urllib.request
from urllib.parse import urlsplit


def compile_schedule(brief, capacity, spec):
    """Expand Alex's explicit slot/rotation choices; never choose a schedule for him."""
    c = copy.deepcopy(capacity)
    session = spec.get('sessionMinutes')
    if type(session) is not int or not 5 <= session <= brief['session']:
        raise ValueError('Choose sessionMinutes between 5 and the requested session length.')
    reasons = spec.get('criteria', [])
    if not isinstance(reasons, list) or not reasons or any(not isinstance(x, str) or not 1 <= len(x) <= 400 for x in reasons):
        raise ValueError('Explain the scheduling criteria and tradeoffs.')
    limit = spec.get('maxConsecutiveSessions')
    if type(limit) is not int or not 1 <= limit <= 4:
        raise ValueError('Choose maxConsecutiveSessions from 1 to 4, with breaks between work blocks.')
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
        for name in names:
            if not isinstance(name, str) or not re.fullmatch(r'Presenter \d{2} \(unassigned\)', name):
                raise ValueError('Use named slots such as Presenter 01 (unassigned); do not invent confirmed staff.')
            if name in people and people[name] != key: raise ValueError('A presenter must keep one topic; do not assume cross-training.')
            people[name] = key
        booth = dict(booth='Booth-'+str(list(topics).index(key)+1), topicId=key, topic=topic['topic'], demo=topic['demo'],
                     presenter=' / '.join(names), harnesses='OpenClaw')
        booths.append(booth); remaining = topic['attendees']; count = 0
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
                seats = min(remaining, brief['groupSize']); remaining -= seats
                rows.append({**booth, 'day':day, 'start':clock(start+slot*session), 'end':clock(start+(slot+1)*session),
                             'presenter':person, 'attendees':seats, 'presenterExpertise':topic.get('presenterExpertise', 'Dedicated specialist for '+key)})
        if remaining or count != topic['groups']: raise ValueError('Cover all '+str(topic['groups'])+' visits for '+key+'.')
        topic.update(presenters=len(names), stations=1)
    duty = []
    lookup = {(r['day'], r['start'], r['presenter']):r for r in rows}
    for day in range(1, brief['days']+1):
        runs = dict.fromkeys(people, 0)
        for slot in range(brief['duration']//session):
            time = clock(start+slot*session)
            for person in people:
                visit = lookup.get((day,time,person)); runs[person] = runs[person]+1 if visit else 0
                if runs[person] > limit: raise ValueError(person+' exceeds the chosen consecutive-session limit.')
                duty.append(dict(day=day,start=time,end=clock(start+(slot+1)*session),presenter=person,booth=visit['booth'] if visit else '',
                                 status='Presenting' if visit else 'Break',topic=visit['topic'] if visit else '',topicId=visit['topicId'] if visit else ''))
    c.update(booths=sorted(booths,key=lambda b:b['booth']), schedule=sorted(rows,key=lambda r:(r['day'],r['start'],r['booth'])),
             presenterDuty=duty,presenterCount=len(people),reliefPresenters=max(0,len(people)-len(booths)),
             session=session,slots=(brief['duration']//session)*brief['days'],adjusted=session!=brief['session'],staff=len(people)+c['floorHosts']+1,
             staffingPolicy='agent-authored',scheduleAuthor='Alex',scheduleCriteria=reasons,maxConsecutiveSessions=limit,
             assumptions='One visit per attendee. Presenter slots are unassigned. Dedicated topic specialists; session time includes handover. '+ ' '.join(reasons))
    return c


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
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if urlsplit(newurl).scheme!='https' or urlsplit(newurl).hostname!='blogs.nvidia.com': raise ValueError('Unexpected research redirect.')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    request=urllib.request.Request(url,headers={'User-Agent':'BaC-Agent-Research/1.0'})
    with urllib.request.build_opener(Redirect()).open(request,timeout=12) as response:
        raw=response.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError('Article exceeds the read limit.')
    parser=ArticleText();parser.feed(raw.decode('utf-8',errors='replace'))
    return re.sub(r'\s+',' ',' '.join(parser.parts)).strip()[:16000]


def schedule_html(brief,calc):
    from event_timetable import tables
    criteria=escape(' '.join(calc['scheduleCriteria']))
    return '<section class="section" id="schedule"><h2>Presenter timetable</h2><p>Alex · '+criteria+'</p>'+tables(brief,calc)+'</section>'


def run(workspace, action, values):
    workspace=Path(workspace).resolve()
    contract=json.loads((workspace/'inbox/agent-task.json').read_text())
    out=workspace/'artifacts';out.mkdir(exist_ok=True)
    files=contract['files'];stamp=datetime.now(timezone.utc).isoformat()
    if action=='search':
        from nvidia_research import search_one
        if not 1<=len(values)<=4 or any(not 1<=len(q)<=100 for q in values): raise ValueError('Supply 1–4 concise search queries.')
        saved=workspace/files['research']
        previous=json.loads(saved.read_text()) if saved.exists() else {}
        queries=list(dict.fromkeys(previous.get('queries',[])+values))
        if len(queries)>4:raise ValueError('Use at most four distinct queries per mission.')
        sources={row['url']:row for row in previous.get('sources',[])};failures=list(previous.get('failedQueries',[]));found={}
        def search(query):
            try:return query, search_one(query), None
            except Exception as error:return query, [], type(error).__name__
        with ThreadPoolExecutor(max_workers=min(3, len(values))) as pool:
            for query, matches, error in pool.map(search, values):
                for row in matches:found[row['url']]=row
                if error:failures.append({'query':query,'error':error})
        for row in sorted(found.values(),key=lambda r:(r['published'],r['url']),reverse=True):
            if row['url'] in sources:
                sources[row['url']].update({k:v for k,v in row.items() if k!='id'})
            elif len(sources)<24:
                sources[row['url']]={**row,'id':'S'+str(len(sources)+1)}
        rows=list(sources.values())
        research={'retrieved':stamp,'queries':queries,'sources':rows,'failedQueries':failures,'status':'available' if rows else 'unavailable','method':'Agent-selected NVIDIA Blog search queries'}
        saved.write_text(json.dumps(research,ensure_ascii=False,indent=2))
        result=research
    elif action=='read':
        research=json.loads((workspace/files['research']).read_text());selected=set(values)
        if not 1<=len(selected)<=6 or not selected.issubset({s['id'] for s in research['sources']}):raise ValueError('Read 1–6 retrieved source IDs.')
        chosen = [source for source in research['sources'] if source['id'] in selected]
        def read(source):
            try:return read_article(source['url']), None
            except Exception as error:return None, type(error).__name__
        with ThreadPoolExecutor(max_workers=min(3, len(chosen))) as pool:
            for source, (article, error) in zip(chosen, pool.map(read, chosen)):
                if error:source['readError']=error
                else:source.update(article=article,readAt=stamp);source.pop('readError',None)
        (workspace/files['research']).write_text(json.dumps(research,ensure_ascii=False,indent=2))
        # Keep each selected source visible within the native tool output limit.
        # Full retrieved text stays in the saved research file; excerpts are explicit.
        excerpts = []
        budget = 18000 // len(chosen)
        for source in chosen:
            view = dict(source)
            if len(view.get('article', '')) > budget:
                view.update(article=view['article'][:budget], articleTruncated=True,
                            fullArticleChars=len(source['article']), fullArticleFile=files['research'])
            excerpts.append(view)
        result={'sources':excerpts}
    elif action=='schedule':
        from event_planner import workbook
        spec=json.loads((workspace/files['plan']).read_text());calc=compile_schedule(contract['brief'],contract['capacity'],spec)
        (workspace/files['schedule']).write_text(json.dumps({'brief':contract['brief'],'capacity':calc,'plan':spec},ensure_ascii=False,indent=2))
        (workspace/files['xlsx']).write_bytes(workbook(contract['brief'],calc))
        (workspace/files['scheduleHtml']).write_text(schedule_html(contract['brief'],calc))
        result={'status':'validated','visits':len(calc['schedule']),'presenters':calc['presenterCount'],'files':[files['schedule'],files['xlsx']]}
    else:raise ValueError('Unknown event tool action.')
    with (out/'agent-tool-log.jsonl').open('a') as log:
        log.write(json.dumps({'time':stamp,'action':action,'arguments':values,'job':contract['job']})+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['search','read','schedule']);parser.add_argument('values',nargs='*')
    args=parser.parse_args()
    try:print(json.dumps(run(Path.cwd(),args.action,args.values),ensure_ascii=False))
    except Exception as error:parser.exit(1,str(error)+'\n')

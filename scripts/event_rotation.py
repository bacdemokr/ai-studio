"""One booth per researched theme, with deterministic presenter relief."""
import math

PRESENTER_COLORS=['#e1edcb','#d8e9f3','#f4e5ce','#e7dcf2','#f0dce2','#d7e9e1','#e5e8cc','#dce1f4','#f0e0d0']

def plan_themes(data):
    from event_planner import plan, TOPICS
    n=data['themeCount']
    if type(n) is not int or not 2<=n<=6:raise ValueError('Choose 2 to 6 themes.')
    base={k:v for k,v in data.items() if k not in ('themeCount','topicWeights')}
    base.update(topics=list(TOPICS)[:n],harnesses=['openclaw'],boothLimit=n)
    b,c=plan(base)
    b['themeCount']=n
    from event_staffing import single_presenter_slots, work_slots, presenter_limit, presenter_duty
    start=int(b['startTime'][:2])*60+int(b['startTime'][3:])
    daily=b['duration']//c['session']
    clock=lambda value:'%02d:%02d'%divmod(value,60)
    name=lambda i:'Presenter %02d (unassigned)'%(i+1)
    booths=[];schedule=[];people=[]
    for i,t in enumerate(c['topics']):
        count=presenter_limit(b,c['session'],t['groups'])
        names=[name(len(people)+p) for p in range(count)];people.extend(names)
        t.update(topic='Theme %02d'%(i+1),demo='Research pending',source='',stations=1,presenters=count,researchStatus='pending')
        booth=dict(booth='Booth-%d'%(i+1),topicId=t['id'],topic=t['topic'],demo=t['demo'],presenter=' / '.join(names),harnesses='OpenClaw')
        booths.append(booth)
        allowed=single_presenter_slots(daily,c['session'],i) if count==1 else list(range(daily))
        if len(allowed)*b['days']<t['groups']:
            allowed=single_presenter_slots(daily,c['session'])
        available=[(day,slot) for day in range(1,b['days']+1) for slot in allowed]
        remaining=t['attendees']
        for g in range(t['groups']):
            day,slot=available[g*len(available)//t['groups']]
            seats=min(remaining,b['groupSize']);remaining-=seats
            person=names[(slot//work_slots(c['session']))%count]
            schedule.append({**booth,'day':day,'start':clock(start+slot*c['session']),'end':clock(start+(slot+1)*c['session']),
                'presenter':person,'attendees':seats})
    schedule.sort(key=lambda r:(r['day'],r['start'],r['booth']))
    limit=work_slots(c['session'])
    duty,issues=presenter_duty(b,c['session'],people,schedule,limit)
    if issues:raise ValueError('Cannot fit visits with presenter breaks: '+' '.join(issues))
    total=len(people)
    c.update(booths=booths,schedule=schedule,boothCount=n,presenterCount=total,presenterDuty=duty,
             staffingPolicy='load-based-topic-staffing',reliefPresenters=total-n,maxConsecutiveSessions=limit)
    c['floorHosts']=math.ceil(n/3);c['staff']=total+c['floorHosts']+1
    c['assumptions']='One interest-based visit per attendee. One booth per theme. Start with one topic specialist per booth; add a second only when visit demand exceeds single-presenter capacity with breaks. Normally work up to 45 minutes then rest for at least 15 minutes; sessions longer than 45 minutes require rest immediately afterwards. No cross-topic assignments. No visit means unused capacity, not an additional scheduled break. Names are unassigned; confirm staff and hardware. Session time includes handover. OpenClaw is the agent harness.'
    return b,c


def duty_grids(brief,calc):
    result=[]
    for day in range(1,brief['days']+1):
        duty=[r for r in calc.get('presenterDuty',[]) if r['day']==day]
        if not duty:continue
        times=list(dict.fromkeys(r['start'] for r in duty))
        people=list(dict.fromkeys(r['presenter'] for r in duty))
        lookup={(r['presenter'],r['start']):r for r in duty}
        rows=[['Presenter / time']+times]
        for person in people:
            rows.append([person]+[lookup[person,t]['booth'] or lookup[person,t].get('status','Break') for t in times])
        result.append(('Day %d breaks'%day,rows))
    return result

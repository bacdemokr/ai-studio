"""One booth per researched theme, with deterministic presenter relief."""
import math

PRESENTER_COLORS=['#e1edcb','#d8e9f3','#f4e5ce','#e7dcf2','#f0dce2','#d7e9e1','#e5e8cc','#dce1f4','#f0e0d0']

def plan_themes(data):
    from event_planner import plan, TOPICS
    n=data['themeCount']
    if type(n) is not int or not 3<=n<=6:raise ValueError('Choose 3 to 6 themes.')
    base={k:v for k,v in data.items() if k not in ('themeCount','topicWeights')}
    base.update(topics=list(TOPICS)[:n],harnesses=['openclaw'],boothLimit=n)
    b,c=plan(base)
    b['themeCount']=n
    total=2*n
    start=int(b['startTime'][:2])*60+int(b['startTime'][3:])
    daily=b['duration']//c['session']
    clock=lambda value:'%02d:%02d'%divmod(value,60)
    name=lambda i:'Presenter %02d (unassigned)'%(i+1)
    booths=[];schedule=[]
    for i,t in enumerate(c['topics']):
        t.update(topic='Theme %02d'%(i+1),demo='Research pending',source='',stations=1,presenters=2,researchStatus='pending')
        booth=dict(booth='Booth-%d'%(i+1),topicId=t['id'],topic=t['topic'],demo=t['demo'],presenter=name(i)+' / '+name(n+i),harnesses='OpenClaw')
        booths.append(booth)
        remaining=t['attendees']
        for g in range(t['groups']):
            # Spread visits across each day instead of filling only the morning.
            day=g%b['days']+1
            day_groups=math.ceil((t['groups']-(day-1))/b['days'])
            slot=(g//b['days'])*daily//max(1,day_groups)
            seats=min(remaining,b['groupSize']);remaining-=seats
            schedule.append({**booth,'day':day,'start':clock(start+slot*c['session']),'end':clock(start+(slot+1)*c['session']),
                'presenter':name(i+n*((g//b['days'])%2)),'attendees':seats})
    schedule.sort(key=lambda r:(r['day'],r['start'],r['booth']))
    # Each booth has its own two specialists. Alternate actual visits, not clock
    # slots, so sparse schedules still offer relief without changing topics.
    # Theme IDs remain stable while Dylan researches their names in parallel.
    assignments={(r['day'],r['start'],r['presenter']):r for r in schedule}
    duty=[]
    for day in range(1,b['days']+1):
        for slot in range(daily):
            time=clock(start+slot*c['session'])
            for p in range(total):
                visit=assignments.get((day,time,name(p)))
                duty.append(dict(day=day,start=time,end=clock(start+(slot+1)*c['session']),presenter=name(p),
                    booth=visit['booth'] if visit else '',status='Presenting' if visit else 'Break',topic=visit['topic'] if visit else '',topicId=visit['topicId'] if visit else ''))
    c.update(booths=booths,schedule=schedule,boothCount=n,presenterCount=total,presenterDuty=duty,
             staffingPolicy='dedicated-topic-pairs',reliefPresenters=n,staff=total+c['floorHosts']+1)
    c['floorHosts']=math.ceil(n/3);c['staff']=total+c['floorHosts']+1
    c['assumptions']='One interest-based visit per attendee. Exactly one booth per theme. Two dedicated topic specialists per booth alternate visits and keep the same topic across all event days. No cross-topic assignments. This plan budgets two presenters per booth because no staffing cap was supplied; a smaller team needs an organizer-confirmed expertise and relief plan. Presenter numbers are unassigned staffing slots. Unassigned slots are scheduled breaks, not standby. Session length includes handover; staffing and hardware need organizer confirmation. OpenClaw is the agent harness.'
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
            rows.append([person]+[lookup[person,t]['booth'] or 'Break' for t in times])
        result.append(('Day %d breaks'%day,rows))
    return result

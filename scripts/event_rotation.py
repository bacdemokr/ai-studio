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
    from event_agent_tools import compile_schedule
    from event_staffing import schedule_spec
    for i,t in enumerate(c['topics']):
        t.update(topic='Theme %02d'%(i+1),demo='Research pending',source='',stations=1,researchStatus='pending')
    c['floorHosts']=math.ceil(n/3)
    c=compile_schedule(b,c,schedule_spec(b,c))
    c['boothCount']=n
    c['assumptions'] += ' Actual topic expertise awaits research. Confirm staff and hardware before opening.'
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

"""Render supplied assignments without making staffing or scheduling decisions."""
from html import escape
from event_dates import day_label
from event_rotation import duty_grids, PRESENTER_COLORS
COLORS=PRESENTER_COLORS
e=lambda value:escape(str(value),quote=True)

def tables(b,c):
    start=int(b['startTime'][:2])*60+int(b['startTime'][3:])
    times=['%02d:%02d'%divmod(t,60) for t in range(start,start+b['duration']-c['session']+1,c['session'])]
    visits={(r['day'],r['booth'],r['start']):r for r in c['schedule']}
    duty_lookup={(r['day'],r['start'],r['presenter']):r['status'] for r in c['presenterDuty']}
    booth_people={booth['booth']:{r['presenter'] for r in c['schedule'] if r['booth']==booth['booth']} for booth in c['booths']}
    people=list(dict.fromkeys(r['presenter'] for r in c['presenterDuty']))
    color={p:COLORS[i%len(COLORS)] for i,p in enumerate(people)}
    heads='<thead><tr><th>Booth / local time</th>'+''.join('<th>'+t+'</th>' for t in times)+'</tr></thead>'
    result='<div class="legend">'+''.join('<span style="--person:'+color[p]+'">'+e(p.replace(' (unassigned)',''))+'</span>' for p in people)+'</div>'
    for day in range(1,b['days']+1):
        rows=[]
        for booth in c['booths']:
            cells=[]
            for time in times:
                r=visits.get((day,booth['booth'],time))
                resting=any(duty_lookup.get((day,time,p))=='Break' for p in booth_people[booth['booth']])
                empty='<td class="break">Break</td>' if resting else '<td class="no-visit">No visit</td>'
                cells.append('<td class="present" style="--person:'+color[r['presenter']]+'"><details><summary><b>'+e(r['presenter'].replace(' (unassigned)',''))+'</b></summary><p>'+e(r['start'])+'–'+e(r['end'])+' · '+str(r['attendees'])+' attendees</p><p>'+e(r.get('presenterExpertise','Topic specialist'))+'</p></details></td>' if r else empty)
            rows.append('<tr><th>'+e(booth['booth'])+'<span>'+e(booth['topic'])+'</span><span>'+e(booth['demo'])+'</span>'+('<span>'+e(booth['presenter'].replace(' (unassigned)',''))+'</span>' if c.get('staffingPolicy')=='dedicated-topic-pairs' else '')+'</th>'+''.join(cells)+'</tr>')
        result+='<details class="day" open><summary>'+e(day_label(b,day))+' · Booth coverage</summary><div class="scroll"><table>'+heads+'<tbody>'+''.join(rows)+'</tbody></table></div></details>'
    staffing=('Two dedicated specialists per theme alternate visits and stay with their booth across all days. No cross-topic assignments. This budgets two presenters per booth; confirm staffing before opening.' if c.get('staffingPolicy')=='dedicated-topic-pairs' else 'A full break slot follows at most two consecutive sessions. Cross-training is required.')
    if c.get('staffingPolicy') in ('load-based-topic-staffing','tool-calculated'):staffing='Staffing follows visit demand. Normally work up to 45 minutes, then rest at least 15 minutes. No visit marks unused capacity, not a scheduled break.'
    if c.get('staffingPolicy')=='agent-authored':staffing='Each presenter stays with one topic. Alex set a maximum of '+str(c.get('maxConsecutiveSessions',2))+' consecutive sessions. Normally work up to 45 minutes, then rest at least 15 minutes. No visit is unused capacity. Confirm each specialist’s availability before opening.'
    result+='<h3 class="ops-title">Presenter shifts and breaks</h3><p>'+str(c['presenterCount'])+' presenters cover '+str(c['boothCount'])+' booths. '+staffing+' Handover is included in each visit slot.</p>'
    for name,rows in duty_grids(b,c):
        result+='<details class="day" open><summary>'+e(name.replace('breaks','· Presenter shifts and breaks'))+'</summary><div class="scroll"><table><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>'
        for row in rows[1:]:
            result+='<tr><th>'+e(row[0].replace(' (unassigned)',''))+'</th>'+''.join('<td class="'+('break' if cell=='Break' else 'no-visit' if cell=='No visit' else 'present')+'" style="--person:'+color[row[0]]+'">'+e(cell)+'</td>' for cell in row[1:])+'</tr>'
        result+='</tbody></table></div></details>'
    return result

"""Shared staffing arithmetic and explicit rest validation for event plans."""
import math


def work_slots(session):
    return max(1, 45 // session)


def rest_slots(session):
    return math.ceil(15 / session)


def single_presenter_slots(daily, session, offset=0):
    work, rest = work_slots(session), rest_slots(session)
    return [slot for slot in range(daily) if (slot + offset) % (work + rest) < work]


def presenter_limit(brief, session, groups):
    # A second topic specialist is justified only if the first cannot cover the
    # required visits while taking a full rest slot around each hour.
    capacity = len(single_presenter_slots(brief['duration']//session, session))*brief['days']
    return 1 if groups <= capacity else 2


def presenter_duty(brief, session, people, rows, consecutive_limit):
    start = int(brief['startTime'][:2])*60 + int(brief['startTime'][3:])
    clock = lambda t: '%02d:%02d' % divmod(t,60)
    lookup = {(r['day'],r['start'],r['presenter']):r for r in rows}
    duty, issues = [], []
    for day in range(1,brief['days']+1):
        runs = dict.fromkeys(people,0)
        rests = dict.fromkeys(people,15)
        for slot in range(brief['duration']//session):
            time = clock(start+slot*session)
            for person in people:
                visit = lookup.get((day,time,person))
                if visit:
                    runs[person] += 1
                    rests[person] = 0
                    if runs[person] == consecutive_limit+1:
                        issues.append(person+' exceeds the chosen consecutive-session limit on day '+str(day)+' at '+time+'. Adjust its rotation or spacing.')
                    if runs[person] == work_slots(session)+1:
                        issues.append(person+' needs at least 15 minutes of rest after a work block (normally 45 minutes) on day '+str(day)+' at '+time+'.')
                    status = 'Presenting'
                else:
                    status = 'Break' if rests[person] < 15 else 'No visit'
                    rests[person] += session
                    if rests[person] >= 15:runs[person] = 0
                duty.append(dict(day=day,start=time,end=clock(start+(slot+1)*session),presenter=person,
                    booth=visit['booth'] if visit else '',status=status,
                    topic=visit['topic'] if visit else '',topicId=visit['topicId'] if visit else ''))
    return duty, issues

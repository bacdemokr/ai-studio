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


def spread_slots(candidates, count, total, max_idle):
    """Select evenly spaced visits, retaining a feasible suffix at every step.

    A greedy nearest slot can strand later visits. Reachability layers ensure
    both edge coverage and the maximum gap without changing the visit count.
    """
    from bisect import bisect_right
    if not 0 <= count <= len(candidates):
        return None
    if not count:
        return []
    if count == 1:
        return [min(candidates, key=lambda slot: abs(slot - (total - 1) / 2))]
    n = len(candidates)
    ends = [bisect_right(candidates, slot + max_idle + 1) for slot in candidates]
    layers = [None, bytearray(total - 1 - slot <= max_idle for slot in candidates)]
    for remaining in range(2, count + 1):
        prefix = [0]
        for possible in layers[-1]:
            prefix.append(prefix[-1] + possible)
        layers.append(bytearray(prefix[ends[i]] > prefix[i + 1] for i in range(n)))
    chosen, previous_index, previous = [], -1, -1
    for index in range(count):
        target = (index + .5) * total / count - .5
        end = bisect_right(candidates, previous + max_idle + 1)
        viable = [i for i in range(previous_index + 1, end) if layers[count - index][i]]
        if not viable:
            return None
        previous_index = min(viable, key=lambda i: (abs(candidates[i] - target), i))
        previous = candidates[previous_index]
        chosen.append(previous)
    return chosen


def schedule_spec(brief, capacity):
    """Shared deterministic assignment for the form preview and Alex's tool."""
    session = capacity['session']
    daily = brief['duration'] // session
    total = daily * brief['days']
    work, rest = work_slots(session), rest_slots(session)
    if not total:
        raise ValueError('The event window has no complete visit slots. Increase the event duration.')
    plans, used_names = [], 0
    for topic_index, topic in enumerate(capacity['topics']):
        groups = topic['groups']
        if groups > total:
            raise ValueError('Too many visits for ' + topic['id'] + '. Increase event time or days, '
                             'increase group size, or reduce attendance.')
        max_idle = math.ceil(total / max(1, groups)) + rest - 1
        people = presenter_limit(brief, session, groups)
        selected = None
        if people == 1:
            # Stagger if feasible, but never add staff because this particular
            # phase loses capacity at the opening/closing edge of a short day.
            phases = list(range(work + rest))
            preferred = topic_index % len(phases)
            phases = phases[preferred:] + phases[:preferred]
            for phase in phases:
                available = [day * daily + slot for day in range(brief['days'])
                             for slot in single_presenter_slots(daily, session, phase)]
                selected = spread_slots(available, groups, total, max_idle)
                if selected is not None:
                    break
        else:
            selected = spread_slots(list(range(total)), groups, total, max_idle)
        if selected is None:
            raise ValueError('Cannot fit ' + topic['id'] + ' visits with full breaks and event-wide spacing. '
                             'Increase event time or days, increase group size, or reduce attendance.')
        names = [f'Presenter {used_names + i + 1:02d} (unassigned)' for i in range(people)]
        used_names += people
        days = []
        for day in range(brief['days']):
            slots = [slot % daily for slot in selected if slot // daily == day]
            if not slots:
                continue
            # Alternate WORK BLOCKS, not individual short visits: the other
            # presenter must get at least 15 continuous minutes to recover.
            rotation = [0] if people == 1 else [(slot // work) % 2 for slot in slots]
            days.append({'day': day + 1, 'slots': slots, 'rotation': rotation})
        plans.append({'topicId': topic['id'], 'presenters': names, 'days': days})
    return {'sessionMinutes': session, 'maxConsecutiveSessions': work,
            'scheduleSource': 'deterministic-tool',
            'criteria': ['Spread visits across the event', 'Reserve full presenter breaks'],
            'tradeoff': 'Use one specialist per topic when feasible; otherwise alternate work blocks between two specialists.',
            'check': 'Confirm presenter availability and topic expertise before the event.', 'booths': plans}


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

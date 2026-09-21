"""Deterministic event planning and portable exports; no extra Spark dependencies."""
import io
import math
import re
from html import escape
from zipfile import ZipFile, ZIP_DEFLATED

TOPICS = {
    'agents': {'title': 'Personal agents', 'demo': 'Build an assistant with memory and tools', 'source': 'https://github.com/openclaw/openclaw'},
    'multiagent': {'title': 'Multi-agent teams', 'demo': 'Delegate a brief and inspect the handoffs', 'source': 'https://build.nvidia.com/blueprints'},
    'physical': {'title': 'Physical AI', 'demo': 'Plan a robot task in a simulated scene', 'source': 'https://developer.nvidia.com/isaac/sim'},
    'cudax': {'title': 'CUDA-X agents', 'demo': 'Turn a planning question into a cuOpt optimization task', 'source': 'https://developer.nvidia.com/cuopt'},
    'vision': {'title': 'Vision AI', 'demo': 'Ask questions about a video with source timestamps', 'source': 'https://build.nvidia.com/nvidia/video-search-and-summarization'},
    'creative': {'title': 'Creative AI', 'demo': 'Create and iterate on a small interactive app', 'source': 'https://build.nvidia.com/blueprints'},
}
HARNESS = {'openclaw': 'OpenClaw', 'hermes': 'Hermes'}
# Public sources checked 2026-09-20; Zurich and Seoul BaC dates corrected by the organizer.
# Attendance and demo timing are
# editable planning examples, not the official event's published capacity/agenda.
TEMPLATES = [
    {'id': 'zurich', 'title': 'Zurich · Meet your agents', 'description': 'A welcoming introduction to assistants and teams.', 'city': 'Zurich', 'region': 'Europe / EMEA', 'attendees': 120, 'duration': 180, 'days': 1, 'topics': ['agents', 'multiagent', 'cudax'], 'startDate': '2026-10-01', 'endDate': '2026-10-01', 'venue': 'StageOne Event & Convention Hall', 'sourceUrl': '', 'sourceNote': 'One-day BaC event on October 1, 2026 at StageOne Event & Convention Hall. Date and venue confirmed by the organizer.'},
    {'id': 'seoul', 'title': 'Seoul · AI Day', 'description': 'An editable demo plan for AI Day Seoul.', 'city': 'Seoul', 'region': 'Asia Pacific', 'attendees': 240, 'duration': 120, 'days': 1, 'topics': ['physical', 'vision', 'cudax', 'agents'], 'startDate': '2026-11-09', 'endDate': '2026-11-09', 'venue': 'COEX', 'sourceUrl': 'https://www.nvidia.com/ko-kr/ai-days/', 'sourceNote': 'One-day BaC event on November 9, 2026 at COEX. This template covers the BaC day, not the full AI Day event.'},
    {'id': 'singapore', 'title': 'Singapore · AI Day', 'description': 'An editable demo plan for AI Day Singapore.', 'city': 'Singapore', 'region': 'Asia Pacific', 'attendees': 360, 'duration': 180, 'days': 2, 'topics': list(TOPICS), 'startDate': '2026-09-22', 'endDate': '2026-09-23', 'venue': 'Raffles City Convention Centre', 'sourceUrl': 'https://www.nvidia.com/en-sg/ai-days/', 'sourceNote': 'AI Day event dates and venue from NVIDIA. BaC is listed on September 23; adjust the date range for a BaC-only plan.'},
]
VENUE_STARTS = {
    'zurich': {'name': 'Park Hyatt Zurich', 'url': 'https://www.hyatt.com/park-hyatt/en-US/zurph-park-hyatt-zurich/meetings'},
    'austin': {'name': 'Four Seasons Hotel Austin', 'url': 'https://www.fourseasons.com/austin/meetings-and-events/meetings/'},
    'singapore': {'name': 'Mandarin Oriental, Singapore', 'url': 'https://www.mandarinoriental.com/en/singapore/marina-bay/meet'},
}


def plan(data):
    if not isinstance(data, dict):
        raise ValueError('Enter an event brief.')
    if 'themeCount' in data:
        from event_rotation import plan_themes
        return plan_themes(data)
    def number(key, default, low, high):
        value = data.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError('%s must be a whole number from %d to %d.' % (key, low, high))
        return value
    def label(key, default, limit=80):
        value = data.get(key, default)
        if not isinstance(value, str) or (key!='region' and not value.strip()) or len(value) > limit or any(ord(c) < 32 for c in value):
            raise ValueError('Enter a valid ' + key + '.')
        return value.strip()
    topics = data.get('topics', TEMPLATES[0]['topics'])
    harnesses = data.get('harnesses', ['openclaw', 'hermes'])
    for values, options, title in ((topics, TOPICS, 'topics'), (harnesses, HARNESS, 'harnesses')):
        if not isinstance(values, list) or not values or len(values) > len(options) or any(not isinstance(v, str) or v not in options for v in values) or len(set(values)) != len(values):
            raise ValueError('Choose available, distinct ' + title + '.')
    b = dict(schema=2, city=label('city', 'Zurich'), region=label('region', 'Europe / EMEA'),
             language=label('language', 'English', 40), attendees=number('attendees', 120, 1, 3000),
             duration=number('duration', 180, 30, 720), days=number('days', 1, 1, 5),
             groupSize=number('groupSize', 5, 1, 30), session=number('session', 15, 5, 60),
             boothLimit=number('boothLimit', 6, 1, 6), topics=list(topics), harnesses=list(harnesses))
    shared_booths = b['boothLimit'] < len(topics)
    start = data.get('startTime', '10:00')
    if not isinstance(start, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', start):
        raise ValueError('Choose a valid local start time.')
    start_minute = int(start[:2]) * 60 + int(start[3:])
    if start_minute + b['duration'] > 1440:
        raise ValueError('The daily event window must finish before midnight.')
    b['startTime'] = start
    venue=data.get('venue','')
    if not isinstance(venue,str) or len(venue)>120 or any(ord(x)<32 for x in venue):raise ValueError('Enter a valid venue.')
    b['venue']=venue.strip()
    from event_dates import normalize_dates
    normalize_dates(data,b)
    weights = data.get('topicWeights', [1] * len(topics))
    if not isinstance(weights, list) or len(weights) != len(topics) or any(type(w) is not int or not 0 <= w <= 10000 for w in weights) or not sum(weights):
        raise ValueError('Interest weights must contain one nonnegative count per topic and at least one response.')
    b['topicWeights'] = weights
    raw = [b['attendees'] * w / sum(weights) for w in weights]
    counts = [math.floor(n) for n in raw]
    for i in sorted(range(len(topics)), key=lambda i: raw[i] - counts[i], reverse=True)[:b['attendees'] - sum(counts)]:
        counts[i] += 1
    groups = [math.ceil(n / b['groupSize']) for n in counts]
    for minutes in range(b['session'], 4, -1):
        slots = (b['duration'] // minutes) * b['days']
        if not slots:
            continue
        stations = [math.ceil(n / slots) for n in groups]
        fits = sum(groups) <= slots * b['boothLimit'] if shared_booths else sum(stations) <= b['boothLimit']
        if fits:
            break
    else:
        raise ValueError('Even five-minute demos exceed the booth limit. Add event time or days, increase group size, or reduce attendance.')
    rows, booths, schedule = [], [], []
    def clock(value):
        return '%02d:%02d' % divmod(value, 60)
    for i, topic in enumerate(topics):
        info = TOPICS[topic]
        row = dict(id=topic, topic=info['title'], demo=info['demo'], source=info['source'], attendees=counts[i], groups=groups[i], stations=stations[i], presenters=stations[i])
        rows.append(row)
        pool = []
        if shared_booths:
            rows[-1]['stations'] = min(b['boothLimit'], groups[i])
            rows[-1]['presenters'] = rows[-1]['stations']
            remaining = counts[i]
            for g in range(groups[i]):
                index = len(schedule)
                booth_index = index % b['boothLimit']
                slot = index // b['boothLimit']
                day = slot % b['days'] + 1
                round_index = slot // b['days']
                seats = min(b['groupSize'], remaining)
                remaining -= seats
                schedule.append(dict(day=day, booth='Booth-%d' % (booth_index+1),
                    presenter='Presenter %02d (unassigned)' % (booth_index+1),
                    topic=info['title'], demo=info['demo'], harnesses=', '.join(HARNESS[h] for h in harnesses),
                    start=clock(start_minute+round_index*minutes), end=clock(start_minute+(round_index+1)*minutes), attendees=seats))
            continue
        for _ in range(stations[i]):
            index = len(booths) + 1
            booth = dict(booth='Booth-%d' % index, topic=info['title'], demo=info['demo'], presenter='Presenter %02d (unassigned)' % index, harnesses=', '.join(HARNESS[h] for h in harnesses))
            booths.append(booth)
            pool.append(booth)
        remaining = counts[i]
        for g in range(groups[i]):
            day = g % b['days']
            day_group = g // b['days']
            round_index = day_group // len(pool)
            seats = min(b['groupSize'], remaining)
            remaining -= seats
            schedule.append(dict(day=day+1, start=clock(start_minute + round_index * minutes), end=clock(start_minute + (round_index+1) * minutes), attendees=seats, **pool[day_group % len(pool)]))
    if shared_booths:
        for key in sorted({r['booth'] for r in schedule}):
            visits = [r for r in schedule if r['booth']==key]
            booths.append(dict(booth=key, topic=' / '.join(dict.fromkeys(r['topic'] for r in visits)),
                demo='Rotating experiences', presenter=visits[0]['presenter'], harnesses=visits[0]['harnesses']))
    schedule.sort(key=lambda row: (row['day'], row['start'], row['booth']))
    staff = len(booths) + math.ceil(len(booths) / 3) + 1
    return b, dict(schema=2, topics=rows, booths=booths, schedule=schedule, session=minutes, slots=slots,
                   boothCount=len(booths), presenterCount=len(booths), floorHosts=math.ceil(len(booths)/3), staff=staff,
                   adjusted=minutes != b['session'], shortfall=0,
                   assumptions=('Booths rotate experiences between time slots. ' if shared_booths else '') + 'One interest-based demo per attendee across the entire event. Attendance is split by interest weights (equal until survey results are used). One presenter per active booth, one floor host per three booths, and one event lead. Presenter names are unassigned staffing slots. Demos run inside the daily event window; presenter relief and breaks need a final human rota. Equipment suitability is assessed per demo, not inferred from headcount. Session times include the complete booth visit.')


def worksheet(name, rows):
    grid = name.startswith('Day ')
    widths = [18]+[22]*(len(rows[0])-1) if grid else {'Event plan':[28,100], 'Booth assignments':[12,26,60,34,28,48], 'Presenter rota':[8,18,18,12,26,34,14,28]}[name]
    def col(n):
        out = ''
        while n:
            n, r = divmod(n-1, 26)
            out = chr(65+r)+out
        return out
    def clean(value):
        return escape(''.join(c for c in str(value) if ord(c) >= 32 or c in '\n\t'))
    xml = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, value in enumerate(row, 1):
            ref = col(c)+str(r)
            person=re.search(r'Presenter (\d+)', str(value) if not name.endswith('breaks') else str(row[0]))
            style = '11' if value == 'Break' else str(2+(int(person.group(1))-1)%9) if grid and r>1 and c>1 and person and value else ('1' if r == 1 or grid and c == 1 else '0')
            cells.append('<c r="%s" s="%s"%s>%s</c>' % (ref, style, '' if type(value) in (int, float) else ' t="inlineStr"', '<v>%s</v>' % value if type(value) in (int, float) else '<is><t xml:space="preserve">%s</t></is>' % clean(value)))
        height = 56 if grid and r>1 else max(34, max(math.ceil(len(str(v))/(widths[i]-3)) for i,v in enumerate(row))*18+12)
        xml.append('<row r="%d" ht="%d" customHeight="1">%s</row>' % (r, height, ''.join(cells)))
    columns = ''.join('<col min="%d" max="%d" width="%d" customWidth="1"/>' % (i,i,width) for i,width in enumerate(widths,1))
    pane = '<pane xSplit="1" ySplit="1" topLeftCell="B2" activePane="bottomRight" state="frozen"/>' if grid else '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
    return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetViews><sheetView workbookViewId="0" showGridLines="0">'+pane+'</sheetView></sheetViews><cols>'+columns+'</cols><sheetData>'+''.join(xml)+'</sheetData>'+('' if grid else '<autoFilter ref="A1:'+col(len(rows[0]))+str(len(rows))+'"/>')+'<pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.2" footer="0.2"/><pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>'


def rota_grids(brief, calc):
    """One booth/time matrix per day, derived from the same scheduled visits."""
    start = sum(int(v)*m for v,m in zip(brief['startTime'].split(':'), (60,1)))
    times = ['%02d:%02d' % divmod(t,60) for t in range(start,start+brief['duration']-calc['session']+1,calc['session'])]
    lookup = {(r['day'],r['booth'],r['start']):r for r in calc['schedule']}
    result = []
    for day in range(1,brief['days']+1):
        rows = [['Booth / time']+times]
        for booth in calc['booths']:
            values = []
            for time in times:
                visit = lookup.get((day,booth['booth'],time))
                values.append(visit['presenter'] if visit else '')
            rows.append([booth['booth']]+values)
        result.append(('Day %d rota' % day, rows))
    return result


def workbook(brief, calc):
    """A snapshot workbook produced by the application calculator, not an LLM claim."""
    sheets = [
        ('Event plan', [['Item', 'Plan'], ['City', brief['city']], ['Event start date', brief.get('startDate') or 'TBC'], ['Event end date', brief.get('endDate') or 'TBC'], ['Venue', brief.get('venue') or 'TBC'], ['Total attendees', brief['attendees']], ['Event days', brief['days']], ['Minutes per day', brief['duration']], ['People per group', brief['groupSize']], ['Minutes per demo', calc['session']], ['Booths', calc['boothCount']], ['Presenters per day', calc['presenterCount']], ['Floor hosts per day', calc['floorHosts']], ['Event lead per day', 1], ['Harnesses to showcase', ', '.join(HARNESS[h] for h in brief['harnesses'])], ['Staff names', 'Unassigned placeholders; not confirmed bookings'], ['Planning basis', calc['assumptions']], ['Export type', 'Calculated snapshot; change the brief in the app to recalculate']]),
        ('Booth assignments', [['Booth', 'Topic', 'Demo concept', 'Presenter slot', 'Harnesses', 'Presenter expertise']]+[[r[k] for k in ('booth','topic','demo','presenter','harnesses')]+[r.get('presenterExpertise','Topic specialist — confirm with demo producer')] for r in calc['booths']]),
        ('Presenter rota', [['Day', 'Start (local)', 'End (local)', 'Booth', 'Topic', 'Presenter slot', 'Attendees', 'Harnesses']]+[[r[k] for k in ('day','start','end','booth','topic','presenter','attendees','harnesses')] for r in calc['schedule']])]
    from event_rotation import duty_grids, PRESENTER_COLORS
    sheets = rota_grids(brief, calc) + duty_grids(brief, calc) + sheets
    out = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/'
    with ZipFile(out, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="'+ns+'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="'+ns+'package/2006/relationships"><Relationship Id="rId1" Type="'+ns+'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="'+ns+'spreadsheetml/2006/main" xmlns:r="'+ns+'officeDocument/2006/relationships"><sheets>'+''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (name,i,i) for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="'+ns+'package/2006/relationships">'+''.join('<Relationship Id="rId%d" Type="%sofficeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i,ns,i) for i in range(1,len(sheets)+1))+'<Relationship Id="rIdStyles" Type="'+ns+'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml','<styleSheet xmlns="'+ns+'spreadsheetml/2006/main"><fonts count="2"><font><sz val="12"/><name val="Calibri"/></font><font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="13"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF22312D"/><bgColor indexed="64"/></patternFill></fill>'+''.join('<fill><patternFill patternType="solid"><fgColor rgb="FF'+color+'"/><bgColor indexed="64"/></patternFill></fill>' for color in [color[1:].upper() for color in PRESENTER_COLORS]+['F5F5F5'])+'</fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="12"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'+''.join('<xf numFmtId="0" fontId="0" fillId="%d" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>' % i for i in range(3,12))+'<xf numFmtId="0" fontId="0" fillId="12" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i,(name,rows) in enumerate(sheets,1):
            z.writestr('xl/worksheets/sheet%d.xml' % i, worksheet(name, rows))
    return out.getvalue()


def venue_seed(brief):
    seed = VENUE_STARTS.get(brief['city'].casefold())
    return {'candidate': seed, 'status': 'Research starting point only; verify live and do not claim a booking or star rating without a source.'}

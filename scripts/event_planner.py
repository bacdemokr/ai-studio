"""Deterministic event planning and portable exports; no extra Spark dependencies."""
import csv
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
TEMPLATES = [
    {'id': 'zurich', 'title': 'Zurich · Meet your agents', 'description': 'A welcoming introduction to assistants and teams.', 'city': 'Zurich', 'region': 'Europe / EMEA', 'attendees': 120, 'duration': 180, 'days': 1, 'topics': ['agents', 'multiagent', 'cudax']},
    {'id': 'austin', 'title': 'Austin · Applied AI lab', 'description': 'A busy, short event: watch the crew adjust demo length.', 'city': 'Austin', 'region': 'Americas', 'attendees': 240, 'duration': 120, 'days': 1, 'topics': ['physical', 'vision', 'cudax', 'agents']},
    {'id': 'singapore', 'title': 'Singapore · AI showcase', 'description': 'Two days, six topics and a complete presenter rota.', 'city': 'Singapore', 'region': 'Asia Pacific', 'attendees': 360, 'duration': 180, 'days': 2, 'topics': list(TOPICS)},
]
VENUE_STARTS = {
    'zurich': {'name': 'Park Hyatt Zurich', 'url': 'https://www.hyatt.com/park-hyatt/en-US/zurph-park-hyatt-zurich/meetings'},
    'austin': {'name': 'Four Seasons Hotel Austin', 'url': 'https://www.fourseasons.com/austin/meetings-and-events/meetings/'},
    'singapore': {'name': 'Mandarin Oriental, Singapore', 'url': 'https://www.mandarinoriental.com/en/singapore/marina-bay/meet'},
}


def plan(data):
    if not isinstance(data, dict):
        raise ValueError('Enter an event brief.')
    def number(key, default, low, high):
        value = data.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError('%s must be a whole number from %d to %d.' % (key, low, high))
        return value
    def label(key, default, limit=80):
        value = data.get(key, default)
        if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
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
    if b['boothLimit'] < len(topics):
        raise ValueError('Allow at least one booth per topic, up to six booths.')
    start = data.get('startTime', '10:00')
    if not isinstance(start, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', start):
        raise ValueError('Choose a valid local start time.')
    start_minute = int(start[:2]) * 60 + int(start[3:])
    if start_minute + b['duration'] > 1440:
        raise ValueError('The daily event window must finish before midnight.')
    b['startTime'] = start
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
        if sum(stations) <= b['boothLimit']:
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
        for _ in range(stations[i]):
            index = len(booths) + 1
            booth = dict(booth='B%02d' % index, topic=info['title'], demo=info['demo'], presenter='Presenter %02d (unassigned)' % index, harnesses=', '.join(HARNESS[h] for h in harnesses))
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
    schedule.sort(key=lambda row: (row['day'], row['start'], row['booth']))
    staff = len(booths) + math.ceil(len(booths) / 3) + 1
    return b, dict(schema=2, topics=rows, booths=booths, schedule=schedule, session=minutes, slots=slots,
                   boothCount=len(booths), presenterCount=len(booths), floorHosts=math.ceil(len(booths)/3), staff=staff,
                   adjusted=minutes != b['session'], shortfall=0,
                   assumptions='One interest-based demo per attendee across the entire event. Attendance is split by interest weights (equal until survey results are used). One presenter per active booth, one floor host per three booths, and one event lead. Presenter names are unassigned staffing slots. Demos run inside the daily event window; presenter relief and breaks need a final human rota. Equipment suitability is assessed per demo, not inferred from headcount. Session times include the complete booth visit.')


def worksheet(name, rows):
    widths = {'Event plan':[28,100], 'Booth assignments':[12,26,60,34,28,48], 'Presenter rota':[8,18,18,12,26,34,14,28]}[name]
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
            style = '1' if r == 1 else '0'
            cells.append('<c r="%s" s="%s"%s>%s</c>' % (ref, style, '' if type(value) in (int, float) else ' t="inlineStr"', '<v>%s</v>' % value if type(value) in (int, float) else '<is><t xml:space="preserve">%s</t></is>' % clean(value)))
        height = max(34, max(math.ceil(len(str(v))/(widths[i]-3)) for i,v in enumerate(row))*18+12)
        xml.append('<row r="%d" ht="%d" customHeight="1">%s</row>' % (r, height, ''.join(cells)))
    columns = ''.join('<col min="%d" max="%d" width="%d" customWidth="1"/>' % (i,i,width) for i,width in enumerate(widths,1))
    return '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>'+columns+'</cols><sheetData>'+''.join(xml)+'</sheetData><autoFilter ref="A1:'+col(len(rows[0]))+str(len(rows))+'"/><pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.2" footer="0.2"/><pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>'


def workbook(brief, calc):
    """A snapshot workbook produced by the application calculator, not an LLM claim."""
    sheets = [
        ('Event plan', [['Item', 'Plan'], ['City', brief['city']], ['Region', brief['region']], ['Total attendees', brief['attendees']], ['Event days', brief['days']], ['Minutes per day', brief['duration']], ['People per group', brief['groupSize']], ['Minutes per demo', calc['session']], ['Booths', calc['boothCount']], ['Presenters per day', calc['presenterCount']], ['Floor hosts per day', calc['floorHosts']], ['Event lead per day', 1], ['Harnesses to showcase', ', '.join(HARNESS[h] for h in brief['harnesses'])], ['Staff names', 'Unassigned placeholders; not confirmed bookings'], ['Planning basis', calc['assumptions']], ['Export type', 'Calculated snapshot; change the brief in the app to recalculate']]),
        ('Booth assignments', [['Booth', 'Topic', 'Demo concept', 'Presenter slot', 'Harnesses', 'Presenter expertise']]+[[r[k] for k in ('booth','topic','demo','presenter','harnesses')]+[r.get('presenterExpertise','Topic specialist — confirm with demo producer')] for r in calc['booths']]),
        ('Presenter rota', [['Day', 'Start (local)', 'End (local)', 'Booth', 'Topic', 'Presenter slot', 'Attendees', 'Harnesses']]+[[r[k] for k in ('day','start','end','booth','topic','presenter','attendees','harnesses')] for r in calc['schedule']])]
    out = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/'
    with ZipFile(out, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="'+ns+'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i for i in range(1,4))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="'+ns+'package/2006/relationships"><Relationship Id="rId1" Type="'+ns+'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="'+ns+'spreadsheetml/2006/main" xmlns:r="'+ns+'officeDocument/2006/relationships"><sheets>'+''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (name,i,i) for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="'+ns+'package/2006/relationships">'+''.join('<Relationship Id="rId%d" Type="%sofficeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i,ns,i) for i in range(1,4))+'<Relationship Id="rId4" Type="'+ns+'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml','<styleSheet xmlns="'+ns+'spreadsheetml/2006/main"><fonts count="2"><font><sz val="12"/><name val="Calibri"/></font><font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF22312D"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i,(name,rows) in enumerate(sheets,1):
            z.writestr('xl/worksheets/sheet%d.xml' % i, worksheet(name, rows))
    return out.getvalue()


def rota_csv(calc):
    out=io.StringIO();writer=csv.writer(out)
    keys=['day','start','end','booth','topic','presenter','attendees','harnesses']
    writer.writerow(keys)
    for r in calc['schedule']:
        writer.writerow([r[k] for k in keys])
    return '\ufeff'+out.getvalue()


def venue_seed(brief):
    seed = VENUE_STARTS.get(brief['city'].casefold())
    return {'candidate': seed, 'status': 'Research starting point only; verify live and do not claim a booking or star rating without a source.'}

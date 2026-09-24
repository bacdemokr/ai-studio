"""Contracts and validation for agent-led event work. Never runs the agents' tools."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

MODE='agent-led-v1'


def enabled(payload):return payload.get('executionMode')==MODE


def paths(job):
    return {key:'artifacts/'+job+'-'+name for key,name in {
        'research':'research.json','demos':'themes.json','plan':'schedule-plan.json',
        'schedule':'schedule.json','xlsx':'presenter-rota.xlsx','scheduleHtml':'schedule.html'}.items()}


def prepare(workspace,job,payload,stage):
    from studio import safe_file
    (Path(workspace)/'artifacts').mkdir(exist_ok=True)
    contract={'job':job,'files':paths(job),'brief':payload['brief'],'capacity':payload['capacity']}
    if stage==1:
        contract['capacity']={'topics':[{'id':t['id']} for t in payload['capacity']['topics']]}
        contract['outputGuidance']='Write only demos with the required short fields and sourceId. Each description: one brief phrase, usually 40–80 characters; use fewer when clear, hard limit 600. Never copy articles or search results. Topic IDs are neutral slots, not mandatory search subjects. Choose distinct evidence-backed subjects from retrieved articles. Final response: at most 30 words; do not repeat the JSON.'
    elif stage==2:
        contract['capacity']={k:v for k,v in payload['capacity'].items() if k not in ('schedule','presenterDuty','booths','assumptions')}
        contract['capacity']['topics']=[{k:v for k,v in topic.items() if k!='presenters'} for topic in payload['capacity']['topics']]
        from event_staffing import presenter_limit, work_slots
        minutes=payload['capacity']['session']
        contract['slotMinutes']=minutes
        contract['staffingPolicy']={'workMinutes':45,'minBreakMinutes':15,'suggestedMaxConsecutiveSessions':work_slots(minutes),
            'maxPresentersByTopic':{t['id']:presenter_limit(payload['brief'],minutes,t['groups']) for t in payload['capacity']['topics']},
            'guidance':'Use one dedicated presenter per topic whenever it can cover the visits with breaks. A second is allowed only above single-presenter capacity. At 15 minutes, normally use three consecutive visits then one break slot; stagger break slots across booths. Longer idle periods are No visit, not extra breaks. Do not reduce the session length just to avoid a break or add unnecessary staff.'}
        contract['inputPriority']='The brief and capacity in this JSON are authoritative. Casey handoff prose may contain mistakes: never override attendee counts, group size, duration or topic allocations with prose. A group has brief.groupSize people; capacity.topics[].groups is the required number of visits.'
        contract['distributionPolicy']='Spread visits across the full event, with flexible staggered starts. For each topic with G>1 visits and T=floor(duration/sessionMinutes)*days slots, no empty interval (including before first and after last visit) may exceed ceil(T/G) + ceil(15/sessionMinutes) - 1 slots to allow a full break. Exact visit positions are your choice; do not force one exact slot per visit. Keep the supplied visit count. Single-visit topics may use any slot. Correct all reported distribution/rotation errors together by editing only the affected booth slots/rotation.'

    elif stage==3:
        # A second, full-capacity contract used to expose ~190 KB of timetable
        # rows even when Morgan's HTML starter was small. Keep one compact input.
        contract={'job':job,'contract':'inbox/morgan-page.json',
                  'instructions':'Read inbox/morgan-page.json for themes, schedule summary and output paths. Author the HTML and post files. The app inserts the validated timetable; do not read or rewrite its rows.'}
    safe_file(workspace,'inbox/agent-task.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2))


def task(stage):
    return {
        0:'Write a concise common brief for the selected crew. Copy organizer numbers exactly; do not infer different group sizes, visit counts or staffing from attendee totals. The app dispatches the preset workflow: Dylan and Alex run in parallel, then Morgan receives their completed contributions. You write the brief; do not claim you chose this execution order or invoked delegation tools. Dylan selects queries, searches NVIDIA Blog, reads articles and writes themes. Alex chooses booth visit slots, staffing and rotations, then calls the supplied validation/export tool. The app binds theme names to stable booth/topic IDs without changing those assignments. Morgan edits the supplied HTML starter and authors the page content and LinkedIn post; the app renders and inserts the timetable. Return the complete brief itself, not a completion receipt; the app saves it. No publishing.',
        1:'Use bac-event-tools and bac-nvidia-research. Read both skill files and inbox/agent-task.json together when possible; they are independent inputs. On research access failure, retry the same command once only; when retryAllowed is false, stop immediately and report the failure without further tools or placeholder files. Choose 1–4 search queries; invoke the search tool yourself, inspect the results, then invoke read on the source IDs you will use. Write the demos JSON to the contract demos file using a file-writing tool; a chat completion claim does not save it. Then execute the validate-themes event tool and fix any reported fields before finishing. Use one brief phrase per description, usually 40–80 characters; use fewer when clear (hard limit 600), title 5–100 and theme 1–100 characters. Topic IDs such as cudax are neutral slot identifiers, not mandatory subjects; do not exhaust searches trying to match their names. Read only the sources needed for the requested themes, together in one call when possible. Never copy articles, URLs or the research bundle into the demos file; cite sourceId only. Every selected source needs a successful article read. Do not use model memory or invent sources. The app has not performed this research for you. After validate-themes passes, stop editing and return at most 30 words naming the themes and saved file; do not repeat JSON or full findings.',
        2:'Use bac-event-tools and bac-event-scheduling. Read the two skill files and inbox/agent-task.json; use one `read` call per file path. Do not calculate visit-slot lists by hand or run scratch scripts. First call `python3 skills/bac-event-tools/scripts/event_agent_tools.py draft-schedule`, which writes and internally validates a deterministic candidate at the contract plan path. Check only the returned visit and presenter counts against the contract, then call the `schedule` action once to export it. If it passes, stop. Do not inspect or rewrite the slot arrays. If it fails, fix only the reported errors once. The structured brief/capacity is authoritative over Casey prose. Preserve every supplied topic and exact visit count; use stable topic IDs. Presenter labels must be exactly `Presenter NN (unassigned)` and remain dedicated to one topic. The draft uses one topic presenter when feasible and two alternating presenters only when one cannot satisfy rest and spacing. Finish with the validated staffing and spacing choices.',
    }.get(stage,'')


def read_json(workspace,path):
    from morgan_page import read_output,PageError
    try:value=json.loads(read_output(workspace,path,500000))
    except PageError as error:raise ValueError(str(error)) from error
    if not isinstance(value,dict):raise ValueError('Write a JSON object to '+path)
    return value


def research_failure_count(workspace,job):
    path=Path(workspace)/paths(job)['research']
    if not path.exists():return 0
    try:return read_json(workspace,paths(job)['research']).get('networkFailures',0)
    except ValueError:return 0


def research_stopped(workspace,job):
    return research_failure_count(workspace,job)>=2


def validate(workspace,job,payload,stage,activity):
    from agent_activity import require_action
    files=paths(job)
    if stage==1:
        require_action(activity,'search');require_action(activity,'read')
        research=read_json(workspace,files['research']);output=read_json(workspace,files['demos'])
        from event_theme_content import validate_saved_themes
        validate_saved_themes(payload['brief'],output,research)
        return {'research':research,'demos':output}
    if stage==2:
        require_action(activity,'schedule')
        from event_agent_tools import compile_schedule,schedule_html
        from event_planner import workbook
        spec=read_json(workspace,files['plan']);saved=read_json(workspace,files['schedule'])
        contract=read_json(workspace,'inbox/agent-task.json')
        expected=compile_schedule(payload['brief'],contract['capacity'],spec)
        if saved.get('capacity')!=expected or saved.get('brief')!=payload['brief'] or saved.get('plan')!=spec:
            raise ValueError('Export the current schedule plan with the schedule tool.')
        def archive(raw):
            with ZipFile(io.BytesIO(raw)) as z:return {name:z.read(name) for name in z.namelist()}
        if archive((Path(workspace)/files['xlsx']).read_bytes())!=archive(workbook(payload['brief'],expected)):
            raise ValueError('The Excel file does not match the validated schedule.')
        html=(Path(workspace)/files['scheduleHtml']).read_text()
        if html!=schedule_html(payload['brief'],expected):raise ValueError('Re-export the schedule HTML from the current plan.')
        return {'capacity':expected,'plan':spec,'scheduleHtml':html}
    return {}


def merge_schedule(payload,result):
    # Bind Dylan's names to Alex's stable topic IDs, without altering any assignments.
    topics={t['id']:t for t in payload['capacity']['topics']}
    calc=result['capacity']
    for topic in calc['topics']:
        topic.update({k:v for k,v in topics[topic['id']].items() if k not in ('presenters','stations')})
    for row in calc['booths']+calc['schedule']+calc['presenterDuty']:
        topic=topics.get(row.get('topicId'))
        if topic:
            row['topic']=topic['topic']
            if 'demo' in row:row.update(demo=topic['demo'],presenterExpertise=topic.get('presenterExpertise','Dedicated topic specialist'))
    payload['capacity'].update(calc)
    payload['schedulePlan']=result['plan']
    payload['decisionNotes']={'summary':' '.join(result['plan']['criteria']), 'tradeoff':result['plan'].get('tradeoff',''), 'check':result['plan'].get('check','')}
    payload['scheduleProvenance']={'author':'Alex','tool':'schedule','planSHA256':hashlib.sha256(json.dumps(result['plan'],sort_keys=True).encode()).hexdigest()}

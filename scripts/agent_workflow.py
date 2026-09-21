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
    if stage==2:
        contract['capacity']={k:v for k,v in payload['capacity'].items() if k not in ('schedule','presenterDuty','booths','assumptions')}
        contract['capacity']['topics']=[{k:v for k,v in topic.items() if k!='presenters'} for topic in payload['capacity']['topics']]
        contract['slotMinutes']=payload['brief']['session']
    elif stage==3:
        # A second, full-capacity contract used to expose ~190 KB of timetable
        # rows even when Morgan's HTML starter was small. Keep one compact input.
        contract={'job':job,'contract':'inbox/morgan-page.json',
                  'instructions':'Read inbox/morgan-page.json for themes, schedule summary and output paths. Author the HTML and post files. The app inserts the validated timetable; do not read or rewrite its rows.'}
    safe_file(workspace,'inbox/agent-task.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2))


def task(stage):
    return {
        0:'Write a concise common brief for the selected crew. The app dispatches the preset workflow: Dylan and Alex run in parallel, then Morgan receives their completed contributions. You write the brief; do not claim you chose this execution order or invoked delegation tools. Dylan selects queries, searches NVIDIA Blog, reads articles and writes themes. Alex chooses booth visit slots, staffing and rotations, then calls the supplied validation/export tool. The app binds theme names to stable booth/topic IDs without changing those assignments. Morgan edits the supplied HTML starter and authors the page content and LinkedIn post; the app renders and inserts the timetable. Return the complete brief itself, not a completion receipt; the app saves it. No publishing.',
        1:'Use bac-event-tools and bac-nvidia-research. Read both skill files and inbox/agent-task.json together when possible; they are independent inputs. Choose 1–4 search queries; invoke the search tool yourself, inspect the results, then invoke read on the source IDs you will use. Write the demos JSON to the contract demos file. Every selected source needs a successful article read. Do not use model memory or invent sources. The app has not performed this research for you. Finish with a short human-readable account of queries, findings and saved file.',
        2:'Use bac-event-tools and bac-event-scheduling. Read both skill files and inbox/agent-task.json together when possible; they are independent inputs. Presenter labels must be exactly Presenter NN (unassigned), for example Presenter 01 (unassigned); put expertise notes in check, never inside labels. Author the schedule-plan JSON: choose visit slots, topic-dedicated presenter slots, rotations, consecutive-session limit and explain criteria/tradeoffs. Use stable topic/booth IDs as placeholders while Dylan researches names. Each presenter stays on one booth/topic; mark actual expertise as awaiting Dylan’s handoff. Run the schedule tool to validate and export your plan; correct any errors once. The app supplies capacity arithmetic but no finished schedule. The supplied tool expands your chosen rotation and renders the HTML and Excel; do not claim you wrote its renderer or scheduling algorithm. Finish with your concrete scheduling choices and output files.',
    }.get(stage,'')


def read_json(workspace,path):
    from morgan_page import read_output,PageError
    try:value=json.loads(read_output(workspace,path,500000))
    except PageError as error:raise ValueError(str(error)) from error
    if not isinstance(value,dict):raise ValueError('Write a JSON object to '+path)
    return value


def validate(workspace,job,payload,stage,activity):
    from agent_activity import require_action
    files=paths(job)
    if stage==1:
        require_action(activity,'search');require_action(activity,'read')
        research=read_json(workspace,files['research']);output=read_json(workspace,files['demos'])
        from event_theme_content import theme_issues
        issues=theme_issues(payload['brief'],output.get('demos'),research)
        sources={s['id']:s for s in research.get('sources',[])}
        for demo in output.get('demos',[]):
            source=sources.get(demo.get('sourceId'),{})
            if not source.get('readAt') or not source.get('article') or source.get('readError'):
                issues[demo.get('topic','unknown')]=['Read the cited article successfully before selecting it.']
        if issues:raise ValueError(json.dumps(issues,ensure_ascii=False))
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

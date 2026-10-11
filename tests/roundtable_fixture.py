"""Explicit test-only replies for visual and lifecycle checks."""
import json
from test_roundtable import RoundtableTests

case=RoundtableTests();case.setUp()
try:
    keys=case.hire(4)
    event=case.studio.crew_owner(case.owner,'event-brief')
    case.studio.enqueue(event, {'kind':'crew','preset':True,'workflow':'showcase','brief':{'schema':2}})
    case.studio.execute(case.studio.next_job())
    state=case.studio.state(case.owner,'event-brief')
    job=state['jobs'][0]
    state['runtime']={'ready':True,'model':True,'openclaw':True,'mode':'fixture'}
    page=(case.studio.workspace(event)/job['payload']['website']['path']).read_text()
    print(json.dumps({'state':state,'page':page,'keys':keys}))
finally:
    case.doCleanups()

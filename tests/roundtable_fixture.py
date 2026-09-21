"""Explicit test-only replies for visual and lifecycle checks."""
import json
from test_roundtable import RoundtableTests

case=RoundtableTests();case.setUp()
try:
    keys=case.hire(4);case.queue();job=case.execute()
    state=case.studio.state(case.owner)
    state['runtime']={'ready':True,'model':True,'openclaw':True,'mode':'fixture'}
    page=(case.studio.workspace(case.owner)/job['payload']['website']['path']).read_text()
    print(json.dumps({'state':state,'page':page,'keys':keys}))
finally:
    case.doCleanups()

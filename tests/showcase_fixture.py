from test_showcase import ShowcaseTests
import json
from pathlib import Path
case=ShowcaseTests();case.setUp()
try:
    job=case.run_job();state=case.studio.state(case.owner)
    state['runtime']={'ready':True,'model':True,'openclaw':True,'mode':'fixture'}
    page=(case.studio.workspace(case.owner)/job['payload']['website']['path']).read_text()
    print(json.dumps({'state':state,'page':page}))
finally:case.doCleanups()

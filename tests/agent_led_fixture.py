"""Explicitly simulated model replies; actual workflow/tool/export implementation."""
import base64
import json
from test_agent_workflow import AgentWorkflowTests
case=AgentWorkflowTests();case.setUp()
try:
    job=case.event(6,days=2,attendees=180);state=case.studio.state(case.owner)
    state['runtime']={'ready':True,'model':True,'openclaw':True,'testFixture':True}
    page=(case.studio.workspace(case.owner)/job['payload']['website']['path']).read_text()
    files={}
    for relative in job['payload']['packageFiles']:
        path=case.studio.workspace(case.owner)/relative
        if path.suffix=='.json':files[relative]={'content':path.read_text(),'mime':'application/json'}
        elif path.suffix=='.xlsx':files[relative]={'content':base64.b64encode(path.read_bytes()).decode(),'encoding':'base64','mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    print(json.dumps({'state':state,'page':page,'files':files}))
finally:case.doCleanups()

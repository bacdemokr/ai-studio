from test_researched_event import ResearchedEventTests
import json
case=ResearchedEventTests();case.setUp()
try:
    job=case.make_event(6);state=case.studio.state(case.owner)
    state['runtime']={'ready':True,'model':True,'openclaw':True,'testFixture':True}
    page=(case.studio.workspace(case.owner)/job['payload']['website']['path']).read_text()
    print(json.dumps({'state':state,'page':page}))
finally:case.doCleanups()

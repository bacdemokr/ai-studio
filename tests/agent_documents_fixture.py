"""Saved fixture files, read by the real inspector; no model or runtime startup."""
import json
from test_agent_documents import AgentDocumentsTests
from agent_documents import read_documents

case=AgentDocumentsTests();case.setUp()
try:
    case.save('SOUL.md','# Tone\nWarm and curious.\n\n# Role\nFind the evidence in documents and explain it clearly.\n\n<script>window.identityInjected = true</script>\n')
    case.save('IDENTITY.md','# Identity\nName: Scout\nRole: Document researcher\n')
    case.save('AGENTS.md','# Workspace\nTreat documents as evidence.\n')
    case.save('MEMORY.md','# Saved preferences\nPrefers concise answers with sources.\n')
    case.save('skills/bac-documents/SKILL.md','---\nname: bac-documents\ndescription: Document Q&A\n---\n\nRead the supplied document and cite the supporting passage.\n')
    for role,name in ((0,'Casey'),(1,'Dylan')):
        case.save('SOUL.md','# Role\n'+name+' has these distinct saved crew instructions.\n',role)
        case.save('IDENTITY.md','# Identity\nName: '+name+'\n',role)
    state=case.studio.state(case.owner)
    print(json.dumps({'state':state,'documents':{'personal':read_documents(case.studio,case.owner),'0':read_documents(case.studio,case.owner,0),'1':read_documents(case.studio,case.owner,1)}}))
finally:case.doCleanups()

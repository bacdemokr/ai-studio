const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio-crew.js','utf8');
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const context=vm.createContext({escape,messageMarkup:escape,webpageButtons:()=>'',data:{crewChats:[]},window:{BacCrewCatalog:JSON.parse(fs.readFileSync('src/crew-catalog.json','utf8'))},defaultNames:['Casey','Dylan','Alex','Morgan','Vera','Cody','Ada','Iris','Scout']});
vm.runInContext(source.slice(0,source.indexOf('function assignedVisitor(')),context);
vm.runInContext(source.slice(source.indexOf('function collaborationRoleOrder('),source.indexOf('function renderMissionControl(')),context);
const render=(plan,status='running',result={},advanced=false)=>context.missionControlTraceMarkup({id:'fixture',status,result,payload:{collaboration:plan}},advanced);
const kinds=html=>[...html.matchAll(/data-trace-kind="([^"]+)"/g)].map(m=>m[1]);
const base={summary:'Research, then review.',tasks:[{role:8,task:'Find sources.',expected:'Cited evidence.'},{role:4,task:'Review evidence.'}],outputs:{},handoffs:{},checks:[]};
assert.equal(JSON.stringify(context.collaborationTeam({...base,calledRoles:[8]})),'[0,8,4]');
assert.equal(JSON.stringify(context.collaborationTeam({...base,calledRoles:[8],skippedRoles:[4]})),'[0,8,4]');
assert.equal(JSON.stringify(context.collaborationTeam({tasks:[],calledRoles:[]})),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam({calledRoles:[8,4]})),'[0,8,4]');
// A new plan must never inherit only role numbers from previous hired work.
context.data.crewChats=[{created:1,payload:{collaboration:{tasks:[{role:8},{role:5}],visitorBindings:{8:{key:'orbit'},5:{key:'jinny'}}}}}];
assert.equal(JSON.stringify(context.collaborationTeam({})),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam({},'hired')),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam(base,'hired')),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam(base,'mixed')),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam({...base,visitorBindings:{}},'hired')),'[0]');
assert.equal(JSON.stringify(context.collaborationTeam({...base,visitorBindings:{}},'mixed')),'[0,8,4]');
assert.equal(JSON.stringify(context.collaborationTeam({...base,visitorBindings:{8:{key:'orbit'},4:{key:'jinny'}}},'hired')),'[0,8,4]');
context.data.crewChats=[];
assert.deepEqual(kinds(render(base)),['user','plan','planned','planned']);
const delivered={...base,calledRoles:[8],activeRole:0,handoffs:{8:{task:'Find sources.',started:1,receivedFrom:[]}},outputs:{8:{answer:'Research result.'}}};
assert.deepEqual(kinds(render(delivered)),['user','plan','contribution','review','planned']);
assert.match(render(delivered),/Reviewing/);
assert(!render(delivered).includes('No additional agents will be called.'));
const continued={...delivered,checks:[{afterRole:8,done:false,reason:'Independent review remains.'}],activeRole:4,calledRoles:[8,4],handoffs:{...delivered.handoffs,4:{task:'Review evidence.',started:2,receivedFrom:['8']}}};
const running=render(continued);
assert.deepEqual(kinds(running),['user','plan','contribution','review','contribution']);
assert(running.indexOf('Research result.')<running.indexOf('Independent review remains.'));
assert(running.indexOf('Independent review remains.')<running.indexOf('data-plan-role="4"'));
assert.match(running,/Working/);
const stopped={...delivered,activeRole:null,checks:[{afterRole:8,done:true,reason:'Enough evidence.'}],skippedRoles:[4],finalAnswer:'Final answer.',responseReady:true};
const complete=render(stopped,'done');
assert.deepEqual(kinds(complete),['user','plan','contribution','review','skipped','response']);
assert.equal(complete.split('Enough evidence.').length-1,1);
assert(complete.indexOf('Research result.')<complete.indexOf('Enough evidence.'));
assert.match(complete,/04 · RESPONSE/); // An uncalled role is not an execution step.
const cancelled=render(delivered,'cancelled');
assert.deepEqual(kinds(cancelled),['user','plan','contribution','skipped','stopped']);
assert(!cancelled.includes('Enough to finish'));
const failed=render({...continued,activeRole:null},'error',{error:'Runtime failed.'});
assert.match(failed,/Incomplete/);assert.match(failed,/Runtime failed\./);
const unavailable=render({...base,tasks:[],outcome:'unavailable',finalAnswer:'No deployment tool.'},'done');
assert.deepEqual(kinds(unavailable),['user','plan','response']);assert.match(unavailable,/Capability unavailable/);
// Legacy saved plans without calledRoles still follow recorded handoff order.
const legacy=render({...base,tasks:[base.tasks[1],base.tasks[0]],handoffs:continued.handoffs,outputs:{8:{answer:'First'},4:{answer:'Second'}},checks:[{afterRole:'8',done:false,reason:'Review next.'},{afterRole:4,done:true,reason:'Finished.'}],finalAnswer:'Done.'},'done');
assert(legacy.indexOf('data-plan-role="8"')<legacy.indexOf('data-plan-role="4"'));
assert.deepEqual(kinds(legacy),['user','plan','contribution','review','contribution','review','response']);
assert(!render({...base,summary:'<script>bad</script>'}).includes('<script>'));
// Chat contributions and reviews follow execution order, not numeric role IDs.
Object.assign(context,{shieldReplyHeld:()=>false,customSkillMarkup:()=>'',imageHistoryMarkup:()=>'',roundtableMarkup:()=>'',window:{BacCrewCatalog:Array.from({length:9},()=>({collaboration:{title:'Specialist'}}))}});
vm.runInContext(source.slice(source.indexOf('function collaborationRevisionBody('),source.indexOf('function showCollaboration(')),context);
const chatPlan={...stopped,origin:{role:0},outputs:{8:{name:'Scout',answer:'Research first.'},4:{name:'Vera',answer:'Review second.'}},calledRoles:[8,4],checks:[{afterRole:8,done:false,reason:'Review still needed.'},{afterRole:4,done:true,reason:'Both complete.'}],skippedRoles:[]};
const chatJob={id:'chat',status:'done',payload:{collaboration:chatPlan,prompt:'/plan Research and review'},result:{answer:'Finished.'}};
const chat=context.collaborationMarkup(chatJob,0);
assert(chat.indexOf('Research first.')<chat.indexOf('Review still needed.'));
assert(chat.indexOf('Review still needed.')<chat.indexOf('Review second.'));
assert(chat.indexOf('Review second.')<chat.indexOf('Both complete.'));
const skippedChat=context.collaborationMarkup({...chatJob,payload:{...chatJob.payload,collaboration:stopped}},4);
assert.match(skippedChat,/Casey did not call Vera for this plan/);
const interrupted={...chatJob,status:'error',result:{error:'App restarted.'},payload:{...chatJob.payload,collaboration:{...chatPlan,finalAnswer:'Saved final answer.'}}};
assert.match(context.collaborationMarkup(interrupted,0),/Saved final answer/);
assert.match(context.collaborationHistoryMarkup(interrupted),/Saved final answer/);
const partialPlan={...chatPlan,outcome:'partial',remaining:['Browser testing <pending>'],checks:[{afterRole:4,done:true,outcome:'partial',reason:'Prototype saved; no execution tool.',remaining:['Browser testing <pending>']}]};
const partialJob={...chatJob,payload:{...chatJob.payload,collaboration:partialPlan},result:{answer:'A working draft was saved.'}};
for(const markup of [render(partialPlan,'done',{answer:'Draft saved.'}),context.collaborationMarkup(partialJob,0),context.collaborationHistoryMarkup(partialJob)]){
 assert.match(markup,/Partial result/);assert.match(markup,/Browser testing &lt;pending&gt;/);
 assert(!markup.includes('Why this result is sufficient'));assert(!markup.includes('Enough to finish'));
}
console.log('PASS: trace order, live review/continuation, early finish, uncalled roles, cancellation/failure, unsupported work, legacy ordering and escaping.');

// Selection explanations use saved plan identities, including declined hires.
const fit='Orbit’s Web research skill covers this brief, including <verified> sources.';
context.chatStopButton=()=>'';
const decline='Live weather does not cover programming <script>bad</script>.';
const fitPlan={...base,visitorBindings:{8:{key:'orbit',name:'Orbit'}},
 tasks:[{...base.tasks[0],roleFit:fit},base.tasks[1]],
 declinedAgents:[{agent:'jinny',reason:decline}]};
const fitJob={id:'fit',status:'running',payload:{prompt:'/goal Research and build',roster:[{key:'jinny',name:'Jinny <saved>'}],collaboration:fitPlan}};
const advancedPlan={...fitPlan,calledRoles:[8],handoffs:{8:{task:'Find sources.',receivedFrom:[]}},outputs:{8:{answer:'Sources support the conclusion <carefully>.'}}};
const advanced=render(advancedPlan,'running',{},true);
assert.deepEqual(kinds(advanced),['user','plan','reasoning','contribution','reasoning','planned']);
assert.equal((advanced.match(/· REASONING</g)||[]).length,2);
assert(advanced.includes(escape(fit)));assert.match(advanced,/Sources support the conclusion &lt;carefully&gt;/);
assert.match(advanced,/not private model chain-of-thought/);assert(!advanced.includes('<carefully>'));
for(const markup of [context.missionControlTraceMarkup(fitJob),context.collaborationMarkup(fitJob,0)]){
 assert.match(markup,/Why this agent/);assert(markup.includes(escape(fit)));
 assert.match(markup,/Not assigned/);assert(markup.includes('Jinny &lt;saved&gt;'));
 assert(markup.includes(escape(decline)));assert(!markup.includes('<script>'));
 assert.equal((markup.match(/Why this agent/g)||[]).length,1);
}
// Explanations remain visible once work starts and after completion.
for(const status of ['running','done']){
 const job={...fitJob,status,payload:{...fitJob.payload,collaboration:{...fitPlan,...{calledRoles:[8],handoffs:delivered.handoffs,outputs:delivered.outputs}}}};
 assert(context.missionControlTraceMarkup(job).includes(escape(fit)));
}
// Older plans without saved reasons must not invent qualifications or show blanks.
assert(!render(base).includes('Why this agent'));
assert(!context.collaborationMarkup(chatJob,0).includes('Why this agent'));
assert(!context.missionControlTraceMarkup({...fitJob,payload:{...fitJob.payload,roster:[]}}).includes('Jinny &lt;saved&gt;'));
assert.match(context.missionControlTraceMarkup({...fitJob,payload:{...fitJob.payload,roster:[]}}),/Requested agent/);
const unavailableJob={...fitJob,payload:{...fitJob.payload,roster:[],unavailableVisitors:[{key:'jinny',name:'Jinny <saved>',reason:'Preparing.'}]}};
assert.match(context.missionControlTraceMarkup(unavailableJob),/Jinny &lt;saved&gt;/);
const declinedStandby={...fitJob,payload:{...fitJob.payload,roster:[],collaboration:{...fitPlan,declinedAgents:[{agent:'Cody',reason:'Hired only is selected.'}]}}};
assert.match(context.missionControlTraceMarkup(declinedStandby),/<strong>Cody<\/strong>/);
console.log('PASS: assignment reasons and declined hires in chat and Mission Control; historical identities, escaping and legacy plans.');

// The final reply and specialist research are distinct files, not two team responses.
const responsePath='artifacts/plan-chat.md',briefPath='artifacts/shared-chat-r8-brief.md',htmlPath='artifacts/page-chat-r5.html';
const withFiles={...chatJob,result:{answer:'Finished.',files:[responsePath,briefPath,htmlPath,responsePath]},payload:{...chatJob.payload,collaboration:{...chatPlan,handoffs:{8:{task:'Research',receivedFrom:[]}},outputs:{8:{name:'Scout',answer:'Research first.',files:[briefPath,briefPath,htmlPath]}}}}};
const fileMarkup=context.collaborationMarkup(withFiles,0);
assert.equal((fileMarkup.match(/>Open team response</g)||[]).length,1);
assert.equal((fileMarkup.match(/>Open supporting file</g)||[]).length,1);
assert.equal((fileMarkup.match(/data-plan-file=/g)||[]).length,2);
assert(fileMarkup.indexOf(briefPath)<fileMarkup.indexOf('</details>'));
assert(!fileMarkup.includes('data-plan-file="'+htmlPath+'"'));
assert.match(context.collaborationMarkup(withFiles,8),/>Open supporting file</);
assert(!context.collaborationMarkup(withFiles,8).includes('Open team response'));
assert(!context.collaborationMarkup({...withFiles,result:{files:[briefPath]}},0).includes('Open team response'));
console.log('PASS: one final-response button; deduplicated supporting files stay with their specialist.');

const revision={role:8,evidenceRole:4,status:'delivered',reason:'A key source was missing.',issue:'Required date lacked evidence.',task:'Verify the missing date only.',expected:'Cited date.',output:{answer:'Date verified from the source.',files:[]}};
const revisedPlan={...chatPlan,revision,checks:[...chatPlan.checks.filter(check=>!check.done),{afterRole:4,afterRevision:true,done:true,outcome:'partial',reason:'Date verified; webpage update remains.'}],outcome:'partial',remaining:['Update webpage']};
const revised=render(revisedPlan,'done',{answer:'The source is verified; implementation still needs updating.'});
assert.deepEqual(kinds(revised),['user','plan','contribution','review','contribution','revision','revision-work','review','response']);
assert(revised.indexOf('data-plan-role="4"')<revised.indexOf('data-revision-request'));
assert(revised.indexOf('data-revision-role="8"')<revised.indexOf('data-after-revision'));
assert.equal((revised.match(/Date verified; webpage update remains/g)||[]).length,1);
const revisedJob={...chatJob,payload:{...chatJob.payload,collaboration:revisedPlan}};
assert.match(context.collaborationMarkup(revisedJob,0),/One targeted revision/);
const specialist=context.collaborationMarkup(revisedJob,8);
assert(specialist.indexOf('Research first.')<specialist.indexOf('Date verified from the source.'));
const working=render({...revisedPlan,checks:[],revision:{...revision,status:'working',output:null},responseReady:false,finalAnswer:null,activeRole:8});
assert.match(working,/Revising/);assert(!working.includes('Revised result delivered'));
console.log('PASS: repair request, participating specialist revision and final check retain chronological history.');

// A completion claim with no required file must never be labelled Delivered.
const missingHandoff={...delivered,activeRole:8,outputs:{8:{answer:'Unverified claim',handoffStatus:'missing'}},handoffRecovery:{role:8,status:'working'}};
assert.match(render(missingHandoff),/Saving missing handoff/);
assert(!render(missingHandoff).includes('>Delivered<'));
assert.match(render({...missingHandoff,handoffRecovery:{role:8,status:'failed'}},'done'),/Handoff incomplete/);
assert.match(render({...delivered,handoffRecovery:{role:8,status:'delivered'}}),/saved and verified in one repair/);
const interruptedOutput={...delivered,outputs:{8:{answer:'Saved but unverified',incomplete:true}},outcome:'partial',responseReady:true,finalAnswer:'Partial work preserved.'};
assert.match(render(interruptedOutput,'done'),/Partial work saved/);
assert(!render(interruptedOutput,'done').includes('>Delivered<'));

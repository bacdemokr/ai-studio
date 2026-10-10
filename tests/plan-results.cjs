const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const surfaces=fs.readFileSync('src/studio-surfaces.js','utf8'),crew=fs.readFileSync('src/studio-crew.js','utf8');
function fn(source,name){const start=source.indexOf('function '+name+'('),end=source.indexOf('\n}',start)+2;assert(start>=0&&end>start);return source.slice(start,end);}
const nodes=new Map();
const el=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,dataset:{},children:[],querySelector(){return null},append(){},remove(){}});return nodes.get(id);};
const old={id:'zurich',created:1,kind:'crew',payload:{brief:{schema:2}}};
const plan={id:'website',created:2,updated:127,status:'done',payload:{prompt:'Make the website visual',metrics:{'plan-Planning':{agent:'casey',name:'Casey',endpoint:'External · NVIDIA Inference · https://inference-api.nvidia.com/v1',input:100,output:20,total:120,runSeconds:5},'plan-Working Cody':{agent:'cody',name:'Cody',endpoint:'Local · Local model · http://127.0.0.1:8000/v1',input:200,output:30,total:230,runSeconds:9}},collaboration:{task:'Make the website visual',finalAnswer:'Updated plots',outputs:{2:{files:['artifacts/index.html','artifacts/handoffs.md']}},webpages:{2:['artifacts/index.html']}}},result:{files:[]}};
const ctx={data:{crewChats:[plan],crewChatReset:{},teamConnection:{}},crewMission:()=>old,planResults:el('plan-results'),usageTime:el('usage-time'),el,runtime:{},teamConnectionBar:el('connection'),localTaskWarning:el('warning'),standbyPanel:el('standby'),teamResetButton:{},removingAgent:false,resultsButton:{},usageTimeButton:{},comparison:null,activeSurface:null,selectedScenario:'plan',selectedJob:null,selectedCrewRole:0,board:false,surfaceStore:{append(){}},surfaceDialog:{open:false,showModal(){this.open=true}},surfaceDefinitions:{deliverables:{title:'Results',ids:['plan-results']},usage:{title:'Usage & time',ids:['usage-time']},control:{title:'Mission Control',ids:['board']}},clearTimeout(){},policyRefreshTimer:null,teamReady:()=>true,teamRuntime:()=>({teamModel:true}),syncResetButtons(){},renderEventPackage(){},render(){},selectEventContribution(){ctx.legacySelections++},navigateShowcaseContribution(){ctx.legacyNavigations++},legacySelections:0,legacyNavigations:0,escape:s=>s,messageMarkup:s=>s,collaborationCompletionMarkup:()=>'',webpageButtons:(files,id)=>JSON.stringify({files:files.filter(f=>f.endsWith('.html')),id}),collaborationFileButtons:(files,id)=>JSON.stringify({files:files.filter(f=>!f.endsWith('.html')),id})};
vm.createContext(ctx);
vm.runInContext([fn(crew,'collaborationTime'),fn(crew,'collaborationTimeMarkup'),fn(crew,'currentCollaboration'),'function collaborationAnswer(job){return job.result?.answer||job.payload.collaboration.finalAnswer||"";}',fn(surfaces,'renderPlanResults'),fn(surfaces,'usageNumber'),fn(surfaces,'usageDuration'),fn(surfaces,'scenarioTaskSummary'),fn(surfaces,'scenarioUsageSummary'),fn(surfaces,'renderUsageTime'),fn(surfaces,'syncTeamTotalTime'),fn(surfaces,'syncSurface'),fn(surfaces,'openSurface')].join('\n'),ctx);
ctx.openSurface('deliverables');
assert.equal(ctx.selectedJob,null,'Opening plan results must not select the old crew job');
assert.equal(el('plan-results').hidden,false);
assert.match(ctx.planResults.innerHTML,/Updated plots/);assert.match(ctx.planResults.innerHTML,/artifacts\/index.html/);assert.match(ctx.planResults.innerHTML,/handoffs.md/);assert.match(ctx.planResults.innerHTML,/website/);assert.equal(ctx.legacySelections,0);assert.equal(ctx.legacyNavigations,0);
assert.equal(ctx.usageTimeButton.hidden,false,'Completed scenario exposes recorded usage');
ctx.openSurface('usage');assert.match(ctx.usageTime.innerHTML,/Make the website visual/);assert.match(ctx.usageTime.innerHTML,/350/);assert.match(ctx.usageTime.innerHTML,/Casey/);assert.match(ctx.usageTime.innerHTML,/Cody/);assert.match(ctx.usageTime.innerHTML,/NVIDIA Inference/);assert.match(ctx.usageTime.innerHTML,/127.0.0.1:8000/);assert.match(ctx.usageTime.innerHTML,/2m 5s/);
// Polls must refresh the response without exposing old results, even before completion.
ctx.openSurface('deliverables');plan.status='running';plan.payload.collaboration.finalAnswer='';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/Work is in progress/);assert.equal(ctx.usageTimeButton.hidden,true);
plan.status='error';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/did not finish/);assert.equal(ctx.usageTimeButton.hidden,false);
// Plans also work with no legacy event present.
ctx.crewMission=()=>null;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,false);
assert.match(el('team-total-time').textContent,/Total/);
// Reset clears plan results, and hides the button when no team jobs remain.
ctx.data.crewChatReset.at=3;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,true);assert.equal(ctx.planResults.innerHTML,'');assert.equal(el('team-total-time').hidden,true);
// Legacy events cannot resurrect results or displace a current plan.
ctx.crewMission=()=>old;ctx.openSurface('deliverables');assert.equal(ctx.selectedJob,null);assert.equal(el('plan-results').hidden,true);assert.equal(ctx.resultsButton.hidden,true);
ctx.data.crewChatReset.at=0;old.created=99;ctx.syncSurface();assert.equal(ctx.currentCollaboration().id,'website');
// Event Brief uses the same scenario-scoped panel with a readable structured-brief summary.
ctx.selectedScenario='event-brief';old.status='done';old.updated=159;old.payload={brief:{schema:2,city:'Zurich',days:2,attendees:50,themeCount:3},metrics:{'1':{agent:'dylan',name:'Dylan',input:40,output:10,total:50,runSeconds:4}}};
ctx.syncSurface();assert.equal(ctx.usageTimeButton.hidden,false);ctx.openSurface('usage');assert.match(ctx.usageTime.innerHTML,/Plan an event in Zurich/);assert.match(ctx.usageTime.innerHTML,/Dylan/);
ctx.selectedScenario='plan';
console.log('PASS: plan routing, saved files, progress/error, reset, and retired event isolation');
// Reset clears a previous execution trace instead of rebuilding a preset crew.
for(const id of ['board','lanes'])el(id).classList={toggle(){}};
const intro={h3:{},p:{},'[data-mission-total]':{},querySelector(tag){return this[tag]}};
el('board').querySelector=()=>intro;
el('lanes').innerHTML='Old execution trace';
ctx.missionControlPlan=()=>null;
vm.runInContext(fn(crew,'renderMissionControl'),ctx);
ctx.renderMissionControl();
assert.equal(el('lanes').innerHTML,'');
assert.equal(intro.h3.textContent,'No active plan');
assert.match(intro.p.textContent,/\/goal/);
console.log('PASS: Mission Control reset clears old cards and provides an empty state');

assert.equal(ctx.collaborationTime({created:100,updated:225,status:'done'},900),'Total time: 2m 5s');
assert.equal(ctx.collaborationTime({created:100,updated:110,status:'running'},235),'Total elapsed: 2m 15s');
assert.equal(ctx.collaborationTime({created:100,updated:3761,status:'cancelled'},9000),'Total time: 1h 1m 1s');
assert.equal(ctx.collaborationTime({status:'done'}),'');
assert.equal(ctx.collaborationTime({created:100,updated:90,status:'error'}),'Total time: 0s');
console.log('PASS: total process timing is live while active and frozen for terminal states');
// Inline clock follows Casey and disappears for specialists or reset.
const clockNode=el('team-total-time');
ctx.currentCollaboration=()=>({created:100,updated:225,status:'done'});
ctx.syncTeamTotalTime();assert.equal(clockNode.hidden,false);assert.equal(clockNode.textContent,'Total time: 2m 5s');
ctx.selectedCrewRole=5;ctx.syncTeamTotalTime();assert.equal(clockNode.hidden,true);
ctx.selectedCrewRole=0;ctx.syncTeamTotalTime();assert.equal(clockNode.hidden,false);
ctx.currentCollaboration=()=>null;ctx.syncTeamTotalTime();assert.equal(clockNode.hidden,true);
console.log('PASS: inline timer follows Casey and disappears after reset');

// Retries are distinct turns; zero is reported usage, missing fields stay unknown.
const summary=ctx.scenarioUsageSummary({created:10,updated:15,payload:{metrics:{
  a:{agent:'riley',name:'Riley',input:100,output:10,total:110,runSeconds:4},
  b:{agent:'riley',name:'Riley',input:200,output:20,total:220,runSeconds:4},
  c:{agent:'morgan',name:'Morgan',input:0,output:0,total:0,runSeconds:0},
  d:{agent:'morgan',name:'Morgan',total:12}
}}});
assert.equal(summary.total,342);assert.equal(summary.apiSeconds,8);assert.equal(summary.elapsed,5);
assert.equal(summary.agents[0].calls,2);assert.equal(summary.unreportedCalls,1);
assert.equal(summary.agents[1].outputReported,true);
ctx.selectedScenario='event-brief';ctx.selectedCrewRole=0;ctx.crewMission=()=>({created:100,updated:160,status:'done'});
ctx.syncTeamTotalTime();assert.equal(clockNode.textContent,'Total time: 1m 0s');
console.log('PASS: repeated turns, missing/zero metrics, parallel duration and Event Brief clock');

// Completed older jobs must not show an invitation as permanently pending.
const reactions=vm.createContext({escape:String,messageMarkup:String,customSkillMarkup:()=>''});
vm.runInContext(fn(crew,'roundtableMarkup'),reactions);
const reactionJob={id:'reaction-test',status:'done',payload:{collaboration:{responseReady:true,outcome:'complete'},roundtable:{status:'invited',members:[{key:'guest',name:'Guest'}],replies:{}}}};
assert.match(reactions.roundtableMarkup(reactionJob),/No personal reaction was recorded/);
assert.doesNotMatch(reactions.roundtableMarkup(reactionJob),/Waiting for the results/);
reactionJob.payload.roundtable.replies.guest={status:'skipped',reason:'Personal reactions were skipped because the task time limit was reached.'};
assert.match(reactions.roundtableMarkup(reactionJob),/time limit/);
reactionJob.payload.roundtable.replies.guest={status:'done',answer:'An actual personal reaction.'};
assert.match(reactions.roundtableMarkup(reactionJob),/An actual personal reaction/);
console.log('PASS: completed and skipped reactions have truthful terminal labels');

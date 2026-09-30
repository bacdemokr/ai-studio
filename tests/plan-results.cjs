const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const surfaces=fs.readFileSync('src/studio-surfaces.js','utf8'),crew=fs.readFileSync('src/studio-crew.js','utf8');
function fn(source,name){const start=source.indexOf('function '+name+'('),end=source.indexOf('\n}',start)+2;assert(start>=0&&end>start);return source.slice(start,end);}
const nodes=new Map();
const el=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,dataset:{},children:[],querySelector(){return null},append(){},remove(){}});return nodes.get(id);};
const old={id:'zurich',created:1,kind:'crew',payload:{brief:{schema:2}}};
const plan={id:'website',created:2,updated:127,status:'done',payload:{prompt:'Make the website visual',collaboration:{finalAnswer:'Updated plots',outputs:{2:{files:['artifacts/index.html','artifacts/handoffs.md']}},webpages:{2:['artifacts/index.html']}}},result:{files:[]}};
const ctx={data:{crewChats:[plan],crewChatReset:{}},crewMission:()=>old,planResults:el('plan-results'),el,runtime:{},teamConnectionBar:el('connection'),teamResetButton:{},removingAgent:false,resultsButton:{},comparison:null,activeSurface:null,selectedJob:null,board:false,surfaceStore:{append(){}},surfaceDialog:{open:false,showModal(){this.open=true}},surfaceDefinitions:{deliverables:{title:'Results',ids:['plan-results']},control:{title:'Mission Control',ids:['board']}},clearTimeout(){},policyRefreshTimer:null,render(){},selectEventContribution(){ctx.legacySelections++},navigateShowcaseContribution(){ctx.legacyNavigations++},legacySelections:0,legacyNavigations:0,escape:s=>s,messageMarkup:s=>s,collaborationCompletionMarkup:()=>'',webpageButtons:(files,id)=>JSON.stringify({files:files.filter(f=>f.endsWith('.html')),id}),collaborationFileButtons:(files,id)=>JSON.stringify({files:files.filter(f=>!f.endsWith('.html')),id})};
vm.createContext(ctx);
vm.runInContext([fn(crew,'collaborationTime'),fn(crew,'collaborationTimeMarkup'),fn(crew,'currentCollaboration'),'function collaborationAnswer(job){return job.result?.answer||job.payload.collaboration.finalAnswer||"";}',fn(surfaces,'renderPlanResults'),fn(surfaces,'syncTeamTotalTime'),fn(surfaces,'syncSurface'),fn(surfaces,'openSurface')].join('\n'),ctx);
ctx.openSurface('deliverables');
assert.equal(ctx.selectedJob,null,'Opening plan results must not select the old crew job');
assert.equal(el('plan-results').hidden,false);
assert.match(ctx.planResults.innerHTML,/Updated plots/);assert.match(ctx.planResults.innerHTML,/artifacts\/index.html/);assert.match(ctx.planResults.innerHTML,/handoffs.md/);assert.match(ctx.planResults.innerHTML,/website/);assert.equal(ctx.legacySelections,0);assert.equal(ctx.legacyNavigations,0);
// Polls must refresh the response without exposing old results, even before completion.
plan.status='running';plan.payload.collaboration.finalAnswer='';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/Work is in progress/);
plan.status='error';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/did not finish/);
// Plans also work with no legacy event present.
ctx.crewMission=()=>null;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,false);
assert.match(el('team-total-time').textContent,/Total/);
// Reset clears plan results, and hides the button when no team jobs remain.
ctx.data.crewChatReset.at=3;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,true);assert.equal(ctx.planResults.innerHTML,'');assert.equal(el('team-total-time').hidden,true);
// Legacy events cannot resurrect results or displace a current plan.
ctx.crewMission=()=>old;ctx.openSurface('deliverables');assert.equal(ctx.selectedJob,null);assert.equal(el('plan-results').hidden,true);assert.equal(ctx.resultsButton.hidden,true);
ctx.data.crewChatReset.at=0;old.created=99;ctx.syncSurface();assert.equal(ctx.currentCollaboration().id,'website');
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
assert.match(intro.p.textContent,/\/plan/);
console.log('PASS: Mission Control reset clears old cards and provides an empty state');

assert.equal(ctx.collaborationTime({created:100,updated:225,status:'done'},900),'Total time: 2m 5s');
assert.equal(ctx.collaborationTime({created:100,updated:110,status:'running'},235),'Total elapsed: 2m 15s');
assert.equal(ctx.collaborationTime({created:100,updated:3761,status:'cancelled'},9000),'Total time: 1h 1m 1s');
assert.equal(ctx.collaborationTime({status:'done'}),'');
assert.equal(ctx.collaborationTime({created:100,updated:90,status:'error'}),'Total time: 0s');
console.log('PASS: total process timing is live while active and frozen for terminal states');
// The same timer is lifted above newly opened dialogs and hidden after reset.
let popoverOpen=false,shows=0,hides=0;
const clockNode=el('team-total-time');
clockNode.matches=()=>popoverOpen;
clockNode.showPopover=()=>{popoverOpen=true;shows++};
clockNode.hidePopover=()=>{popoverOpen=false;hides++};
ctx.currentCollaboration=()=>({created:100,updated:225,status:'done'});
ctx.syncTeamTotalTime();assert.equal(popoverOpen,true);assert.equal(shows,1);
ctx.syncTeamTotalTime();assert.equal(shows,1,'Timer ticks must not repeatedly reopen the overlay');
ctx.syncTeamTotalTime(true);assert.equal(shows,2);assert.equal(hides,1);
ctx.currentCollaboration=()=>null;ctx.syncTeamTotalTime();
assert.equal(popoverOpen,false);assert.equal(clockNode.hidden,true);
console.log('PASS: timer stays above dialogs without reopening on every tick, and disappears after reset');

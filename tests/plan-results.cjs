const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const surfaces=fs.readFileSync('src/studio-surfaces.js','utf8'),crew=fs.readFileSync('src/studio-crew.js','utf8');
function fn(source,name){const start=source.indexOf('function '+name+'('),end=source.indexOf('\n}',start)+2;assert(start>=0&&end>start);return source.slice(start,end);}
const nodes=new Map();
const el=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,dataset:{},children:[],append(){},remove(){}});return nodes.get(id);};
const old={id:'zurich',created:1,kind:'crew',payload:{brief:{schema:2}}};
const plan={id:'website',created:2,status:'done',payload:{prompt:'Make the website visual',collaboration:{finalAnswer:'Updated plots',outputs:{2:{files:['artifacts/index.html','artifacts/handoffs.md']}},webpages:{2:['artifacts/index.html']}}},result:{files:[]}};
const ctx={data:{crewChats:[plan],crewChatReset:{}},crewMission:()=>old,planResults:el('plan-results'),el,runtime:{},teamConnectionBar:el('connection'),teamResetButton:{},removingAgent:false,resultsButton:{},comparison:null,activeSurface:null,selectedJob:null,board:false,surfaceStore:{append(){}},surfaceDialog:{open:false,showModal(){this.open=true}},surfaceDefinitions:{deliverables:{title:'Results',ids:['plan-results','event-package','workspace']},control:{title:'Mission Control',ids:['board']}},clearTimeout(){},policyRefreshTimer:null,render(){},selectEventContribution(){ctx.legacySelections++},navigateShowcaseContribution(){ctx.legacyNavigations++},legacySelections:0,legacyNavigations:0,escape:s=>s,messageMarkup:s=>s,collaborationCompletionMarkup:()=>'',webpageButtons:(files,id)=>JSON.stringify({files:files.filter(f=>f.endsWith('.html')),id}),collaborationFileButtons:(files,id)=>JSON.stringify({files:files.filter(f=>!f.endsWith('.html')),id})};
vm.createContext(ctx);
vm.runInContext([fn(crew,'currentCollaboration'),'function collaborationAnswer(job){return job.result?.answer||job.payload.collaboration.finalAnswer||"";}',fn(surfaces,'renderPlanResults'),fn(surfaces,'syncSurface'),fn(surfaces,'openSurface')].join('\n'),ctx);
ctx.openSurface('deliverables');
assert.equal(ctx.selectedJob,null,'Opening plan results must not select the old crew job');
assert.equal(el('event-package').hidden,true);assert.equal(el('workspace').hidden,true);assert.equal(el('plan-results').hidden,false);
assert.match(ctx.planResults.innerHTML,/Updated plots/);assert.match(ctx.planResults.innerHTML,/artifacts\/index.html/);assert.match(ctx.planResults.innerHTML,/handoffs.md/);assert.match(ctx.planResults.innerHTML,/website/);assert.equal(ctx.legacySelections,0);assert.equal(ctx.legacyNavigations,0);
// Polls must refresh the response without exposing old results, even before completion.
plan.status='running';plan.payload.collaboration.finalAnswer='';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/Work is in progress/);assert.equal(el('event-package').hidden,true);
plan.status='error';ctx.syncSurface();assert.match(ctx.planResults.innerHTML,/did not finish/);
// Plans also work with no legacy event present.
ctx.crewMission=()=>null;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,false);
// Reset clears plan results, and hides the button when no team jobs remain.
ctx.data.crewChatReset.at=3;ctx.syncSurface();assert.equal(ctx.resultsButton.hidden,true);assert.equal(ctx.planResults.innerHTML,'');
// Existing event-only sessions retain their results view.
ctx.crewMission=()=>old;ctx.openSurface('deliverables');assert.equal(ctx.selectedJob,'zurich');assert.equal(el('plan-results').hidden,true);assert.equal(el('event-package').hidden,false);
console.log('PASS: current plan routing, saved files, progress/error, reset, and legacy event results');

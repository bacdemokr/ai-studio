// Run the real telemetry module against small DOM stubs and changing mission state.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const summary={},panel={},listeners={};
const meter={querySelector:s=>s==='summary'?summary:panel,addEventListener(){}};
const history=[{agent:'morgan',name:'Morgan',crew:true,context:24000,limit:32768,outputTokensPerSecond:40,total:100000,calls:2}];
const snapshot={agents:history,host:{cpu:10,memory:30},total:100000};
const roster=[{id:'casey',name:'Casey'},{id:'morgan',name:'Morgan'}];
let mission={id:'new',status:'running',payload:{roster,enabledRoles:[0,1],activeStages:[0],metrics:{}}};
let respond=()=>Promise.resolve(snapshot);
const context=vm.createContext({console,Intl,Date,Number,Math,connected:true,agentId:'owner',room:'mission',escape:String,
 document:{hidden:false,createElement:()=>meter,addEventListener(){}},
 root:{querySelector:()=>({prepend(){}}),addEventListener:(name,fn)=>listeners[name]=fn},
 crewMission:()=>mission,api:()=>respond(),setInterval(){}});
vm.runInContext(fs.readFileSync('src/studio-telemetry.js','utf8'),context);
(async()=>{
 await context.updateTelemetry();
 assert.match(summary.innerHTML,/Context —/);assert.match(panel.innerHTML,/Morgan<\/strong><span>Waiting · —/);
 assert.doesNotMatch(panel.innerHTML,/40.0 tok\/s|73.2%/);assert.match(panel.innerHTML,/100K cumulative/);
 mission.payload.metrics[0]={agent:'casey',context:3200,limit:32000,outputTokensPerSecond:20};
 listeners['bac:state-rendered']();assert.match(summary.innerHTML,/Context 10.0%/);
 const old={id:'old',status:'done',payload:{roster,metrics:{1:history[0]},outputs:{1:'done'}}};
 mission=old;listeners['bac:state-rendered']();assert.match(summary.innerHTML,/Context 73.2%/);assert.match(panel.innerHTML,/40.0 tok\/s/);
 // New mission clears immediately without a reload or waiting for telemetry polling.
 mission={id:'newer',status:'queued',payload:{roster,metrics:{}}};
 listeners['bac:state-rendered']();assert.match(summary.innerHTML,/Context —/);assert.doesNotMatch(panel.innerHTML,/40.0 tok\/s/);
 // An outstanding old request must paint the currently selected mission.
 let finish;respond=()=>new Promise(resolve=>finish=resolve);
 const pending=context.updateTelemetry();mission=old;finish(snapshot);await pending;
 assert.match(summary.innerHTML,/Context 73.2%/);
 mission.payload.enabledRoles=[0];listeners['bac:state-rendered']();assert.doesNotMatch(panel.innerHTML,/>Morgan</);
 mission=null;listeners['bac:state-rendered']();assert.match(summary.innerHTML,/Context —/);
 context.room='lounge';listeners['bac:world-room']();assert.doesNotMatch(panel.innerHTML,/>Morgan</);
 console.log('PASS: mission isolation, waiting roles, cumulative preservation, immediate reset, selection and request race.');
})().catch(e=>{console.error(e);process.exitCode=1;});

// Open Task reads only its own recorded turns, even if Event Brief has newer history.
(async()=>{await new Promise(resolve=>setImmediate(resolve));
context.room='mission';context.selectedScenario='plan';
context.currentCollaboration=()=>({payload:{collaboration:{task:'test'},metrics:{p:{agent:'cody',name:'Cody',context:1000,limit:10000}}}});
context.renderTelemetry({...snapshot,agents:[...history,{agent:'cody',crew:true,total:42,calls:1}]});
assert.match(summary.innerHTML,/Context 10.0%/);assert.match(panel.innerHTML,/>Cody</);assert.doesNotMatch(panel.innerHTML,/>Morgan</);
context.currentCollaboration=()=>null;context.renderTelemetry(snapshot);assert.match(summary.innerHTML,/Context —/);
console.log('PASS: Open Task and Event Brief context remain isolated');
})().catch(e=>{console.error(e);process.exitCode=1;});

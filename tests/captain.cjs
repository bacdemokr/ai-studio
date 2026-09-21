const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
const p=await b.newPage({viewport:{width:1500,height:960}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.addInitScript(()=>window.setInterval=()=>0);await p.goto('http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio&&BacCampus.inspect().navigation.overview);await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
const inject=async(completed,activeStages,status='running')=>p.evaluate(({completed,activeStages,status})=>{const s=BacDemo.snapshot();s.agents.forEach((a,i)=>{a.lane=activeStages.includes(i)?1:0;a.included=true});BacCampus.setLive({...s,live:true,phase:1,jobId:'visual-fixture',selected:0,crewMission:{id:'visual-fixture',status,activeStages,enabledRoles:[0,1,2,3,4,5],completed}});},{completed,activeStages,status});
const bubble=i=>p.locator('.campus-agent-label[data-crew-member="'+i+'"] .crew-work-bubble');
await inject([], [0]);await inject([0],[1,2]);
assert.equal(await bubble(1).count(),0);assert.equal(await bubble(2).count(),0);
let c=await p.evaluate(()=>BacCampus.inspect().captain);assert.deepEqual([...c.pending,...(c.inFlight?[c.inFlight]:[])].map(d=>d.role).sort(),[1,2]);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(1));assert.equal(await bubble(1).count(),1);assert.equal(await bubble(2).count(),0);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(2));assert.equal(await bubble(2).count(),1);assert.equal(await bubble(3).count(),0);
await inject([0,1,2],[3]);assert.equal(await bubble(1).count(),0);assert.equal(await bubble(3).count(),0);
c=await p.evaluate(()=>BacCampus.inspect().captain);assert.deepEqual([...c.pending,...(c.inFlight?[c.inFlight]:[])].filter(d=>d.kind==='assignment').map(d=>d.role),[3]);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(3));assert.equal(await bubble(3).count(),1);assert.deepEqual((await p.evaluate(()=>BacCampus.inspect().captain.received)).sort(),[1,2]);
await inject([0,1,2],[3]);c=await p.evaluate(()=>BacCampus.inspect().captain);assert.equal(c.pending.length,0);assert.equal(c.inFlight,null);
// Cancel while a later assignment is pending: no ghost deliveries or work bubbles.
await inject([0,1,2,3],[4]);await inject([0,1,2,3],[],'cancelled');c=await p.evaluate(()=>BacCampus.inspect().captain);assert(![...c.pending,...(c.inFlight?[c.inFlight]:[])].some(d=>d.kind==='assignment'));assert.equal(await bubble(4).count(),0);
await p.emulateMedia({reducedMotion:'reduce'});await inject([0,1,2,3],[5]);await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(5));assert.equal(await bubble(5).count(),1);assert.equal(await p.evaluate(()=>BacCampus.inspect().captain.inFlight),null);
assert.deepEqual(errors,[]);console.log('PASS: active-only dispatch, receipt-gated work bubbles, returns before Morgan dispatch, no duplicates, cancellation, reduced motion.');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});

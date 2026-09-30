const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
const p=await b.newPage({viewport:{width:1500,height:960}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.addInitScript(()=>window.setInterval=()=>0);await p.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio&&BacCampus.inspect().navigation.overview);await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
const inject=async(completed,activeStages,status='running',options={})=>p.evaluate(({completed,activeStages,status,options})=>{const s=BacDemo.snapshot();s.agents.forEach((a,i)=>{a.lane=activeStages.includes(i)?1:0;a.included=true;if(options.team)a.displayed=options.team.includes(i)});const id=options.id||'visual-fixture';BacCampus.setLive({...s,live:true,phase:1,jobId:id,selected:0,crewMission:{id,kind:options.team?'plan':'event',status,activeStages,enabledRoles:options.team||[0,1,2,3,4,5],completed}});},{completed,activeStages,status,options});
const watchDelivery=role=>p.evaluate(role=>{
 window.deliveryWatch={role,seatedAt:null,flightAt:null,sawWalking:false};
 function sample(){const w=window.deliveryWatch,s=BacCampus.inspect(),r=s.crewExchange[role];
  const seated=r.visible&&!r.phase&&Math.hypot(...s.robots[role].map((v,j)=>v-s.crewHomes[role][j]))<.12;
  if(!seated){w.seatedAt=null;w.sawWalking=true;}else if(w.seatedAt===null)w.seatedAt=s.clock;
  if(s.captain.inFlight?.kind==='assignment'&&s.captain.inFlight.role===role){w.flightAt=s.clock;w.settledFor=s.captain.inFlight.settledFor;return;}
  requestAnimationFrame(sample);
 }requestAnimationFrame(sample);
},role);
const assertSettledDelivery=async()=>{await p.waitForFunction(()=>window.deliveryWatch.flightAt!==null);const w=await p.evaluate(()=>window.deliveryWatch);assert.notEqual(w.seatedAt,null);assert.ok(w.flightAt-w.seatedAt>=1.44,JSON.stringify(w));assert.equal(w.settledFor,1.5);return w;};
const bubble=i=>p.locator('.campus-agent-label[data-crew-member="'+i+'"] .crew-work-bubble');
await inject([], [0]);await watchDelivery(1);await inject([0],[1,2]);
assert.equal(await bubble(1).count(),0);assert.equal(await bubble(2).count(),0);
let c=await p.evaluate(()=>BacCampus.inspect().captain);assert.deepEqual([...c.pending,...(c.inFlight?[c.inFlight]:[])].map(d=>d.role).sort(),[1,2]);
await assertSettledDelivery();await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(1));assert.equal(await bubble(1).count(),1);assert.equal(await bubble(2).count(),0);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(2));assert.equal(await bubble(2).count(),1);assert.equal(await bubble(3).count(),0);
await inject([0,1,2],[3]);assert.equal(await bubble(1).count(),0);assert.equal(await bubble(3).count(),0);
c=await p.evaluate(()=>BacCampus.inspect().captain);assert.deepEqual([...c.pending,...(c.inFlight?[c.inFlight]:[])].filter(d=>d.kind==='assignment').map(d=>d.role),[3]);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(3));assert.equal(await bubble(3).count(),1);assert.deepEqual((await p.evaluate(()=>BacCampus.inspect().captain.received)).sort(),[1,2]);
await inject([0,1,2],[3]);c=await p.evaluate(()=>BacCampus.inspect().captain);assert.equal(c.pending.length,0);assert.equal(c.inFlight,null);
// Cancel while a later assignment is pending: no ghost deliveries or work bubbles.
await inject([0,1,2,3],[4]);await inject([0,1,2,3],[],'cancelled');c=await p.evaluate(()=>BacCampus.inspect().captain);assert(![...c.pending,...(c.inFlight?[c.inFlight]:[])].some(d=>d.kind==='assignment'));assert.equal(await bubble(4).count(),0);
await p.emulateMedia({reducedMotion:'reduce'});await inject([0,1,2,3],[5]);await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(5));assert.equal(await bubble(5).count(),1);assert.equal(await p.evaluate(()=>BacCampus.inspect().captain.inFlight),null);
// A substitute must walk through the door and reach its desk before the delay starts.
await inject([0],[],'running',{id:'seated-fixture',team:[0,1,2,3]});
await p.waitForFunction(()=>!BacCampus.inspect().crewExchange[5].visible);
await p.emulateMedia({reducedMotion:'no-preference'});await p.waitForFunction(()=>BacCampus.inspect().motion);await watchDelivery(5);
await inject([0],[5],'running',{id:'substitute-fixture',team:[0,5]});
assert.equal((await assertSettledDelivery()).sawWalking,true);
await p.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(5));
// Finishing during the settling delay discards the pending assignment.
await inject([0],[5],'running',{id:'fast-fixture',team:[0,5]});
await p.waitForFunction(()=>BacCampus.inspect().captain.pending.some(d=>d.kind==='assignment'&&d.settledFor>0));
await inject([0,5],[],'succeeded',{id:'fast-fixture',team:[0,5]});
await p.waitForTimeout(1800);c=await p.evaluate(()=>BacCampus.inspect().captain);
assert(!c.assigned.includes(5));assert(![...c.pending,...(c.inFlight?[c.inFlight]:[])].some(d=>d.kind==='assignment'));
// Reset during that delay also clears its timer and prevents a late paper flight.
await inject([0],[5],'running',{id:'reset-fixture',team:[0,5]});
await p.waitForFunction(()=>BacCampus.inspect().captain.pending.some(d=>d.kind==='assignment'&&d.settledFor>0));
await p.evaluate(()=>{const s=BacDemo.snapshot();BacCampus.setLive({...s,crewMission:null});});
await p.waitForTimeout(1800);c=await p.evaluate(()=>BacCampus.inspect().captain);
assert.equal(c.job,null);assert.equal(c.pending.length,0);assert.equal(c.inFlight,null);assert.deepEqual(c.assigned,[]);
assert.deepEqual(errors,[]);console.log('PASS: desk arrival plus 1.5s before dispatch, incoming substitute, receipt-gated work bubbles, returns, cancellation, completion/reset during delay, reduced motion.');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});

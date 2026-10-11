// Real WebGL scene, controlled workflow snapshots, no model or live-user data.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync(path.join(__dirname,'../app/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,s=>s.includes('window.BacStudio=')?'':s);
  await page.route('http://visitor.test/',r=>r.fulfill({contentType:'text/html',body:html}));
  await page.goto('http://visitor.test/');await page.waitForFunction(()=>window.BacCampus?.inspect().sceneStyle);
  await page.evaluate(()=>{
   const root=document.querySelector('#agent-campus');root.hidden=false;delete root.dataset.boot;root.classList.add('studio-enabled');
   window.fixtureAgents=[{key:'pixel',name:'Pixel',persona:'maker',tone:'playful',avatar:{body:'claw',color:'coral',accessory:'headset'},activity:null},{key:'orbit',name:'Orbit',persona:'guide',avatar:{body:'round',color:'cyan',accessory:'none'},activity:null}];
   window.fixturePlan=(status='running',key='pixel',role=5,id='job1')=>{
    const s=BacDemo.snapshot();
    s.live=true;s.phase=role;s.selected=0;s.agents=s.agents.map((a,i)=>({...a,lane:0,displayed:i===0||i===role,included:i===0||i===role}));
    if(key){const a=fixtureAgents.find(a=>a.key===key);Object.assign(s.agents[role],{visitorKey:key,name:a.name,avatar:a.avatar,role:'Programmer',lane:1});}
    s.crewMission={id,kind:'plan',status,visitorsActive:status==='running'||status==='stopping',assignedRoles:[role],activeStages:[role],enabledRoles:[0,role],completed:[]};
    fixtureAgents.forEach(a=>a.activity=s.crewMission.visitorsActive?{kind:'mission',job:id,status}:null);
    BacCampus.setCollection(fixtureAgents,'pixel');BacCampus.setLive(s);window.fixtureState=s;
   };
   BacCampus.setScenario('plan');BacCampus.setRoom('mission',{instant:true});BacCampus.setCollection(fixtureAgents,'pixel');
  });
  const inspect=()=>page.evaluate(()=>BacCampus.inspect());
  const wait=fn=>page.waitForFunction(fn,null,{timeout:20000});
  assert.equal((await inspect()).visitorTravel.length,0,'Entering the room alone invites nobody');
  await page.evaluate(()=>fixturePlan());
  let s=await inspect();assert.equal(s.visitorTravel.length,1);assert.equal(s.visitorTravel[0].key,'pixel');
  assert.equal(s.visitorTravel[0].phase,'entering');assert(!s.residents.find(r=>r.key==='pixel').visible);assert(s.residents.find(r=>r.key==='orbit').visible);
  assert(!s.crewExchange[5].visible,'No duplicate at the built-in desk');assert.equal(s.visitorTravel[0].avatar.body,'claw');
  await wait(()=>BacCampus.inspect().visitorTravel[0]?.phase==='working');
  await page.locator('[data-visitor-agent="pixel"]').click();assert.equal(await page.locator('[data-campus-agent="5"]').getAttribute('aria-pressed'),'true');
  await page.screenshot({path:'/tmp/bac-visitor-team-seated.png'});
  const point=(await inspect()).visitorTravel[0].position;
  // Switch scenarios during actual work: the actor stays on the Open Task floor.
  await page.evaluate(()=>{BacCampus.setScenario('event-brief');const s=BacDemo.snapshot();s.live=true;s.crewMission=null;BacCampus.setLive(s);BacCampus.setCollection(fixtureAgents,'pixel');});
  assert.deepEqual((await inspect()).visitorTravel[0].position,point);
  await page.evaluate(()=>{BacCampus.setScenario('plan');BacCampus.setLive(fixtureState);BacCampus.setRoom('lounge',{instant:true});BacCampus.setRoom('workshop',{instant:true});BacCampus.setRoom('mission',{instant:true});});
  assert.equal((await inspect()).visitorTravel[0].phase,'working');assert.deepEqual((await inspect()).visitorTravel[0].position,point);
  await page.evaluate(()=>fixturePlan('done'));await wait(()=>BacCampus.inspect().visitorTravel.length===0);
  assert((await inspect()).residents.find(r=>r.key==='pixel').visible);
  await page.evaluate(()=>BacCampus.setLive(fixtureState));assert.equal((await inspect()).visitorTravel.length,0,'Completed history does not replay arrival');
  // Cancellation in the corridor must reverse from the current position.
  await page.evaluate(()=>fixturePlan('running','pixel',5,'job2'));await page.waitForTimeout(700);
  const before=(await inspect()).visitorTravel[0].position;
  await page.evaluate(()=>fixturePlan('cancelled','pixel',5,'job2'));
  const after=(await inspect()).visitorTravel[0];assert.equal(after.phase,'returning');assert(Math.hypot(...after.position.map((v,i)=>v-before[i]))<2,'No teleport on cancellation');
  // Assign another role before the walk home completes, preserving one actor.
  await page.evaluate(()=>fixturePlan('running','pixel',8,'job3'));assert.equal((await inspect()).visitorTravel.length,1);
  await wait(()=>BacCampus.inspect().visitorTravel[0]?.phase==='working');assert.equal((await inspect()).visitorTravel[0].role,8);
  // Complete while looking at Event Brief, using the shared activity snapshot.
  await page.evaluate(()=>{BacCampus.setScenario('event-brief');const s=BacDemo.snapshot();s.live=true;s.crewMission=null;BacCampus.setLive(s);fixtureAgents.forEach(a=>a.activity=null);BacCampus.setCollection(fixtureAgents,'pixel');});
  s=await inspect();assert.deepEqual(s.visitorTravel[0].destination,s.residents.find(r=>r.key==='pixel').position,'Reassignment retains the full route home, not just the last turning point');
  await wait(()=>BacCampus.inspect().visitorTravel.length===0);assert((await inspect()).residents.find(r=>r.key==='pixel').visible);
  // Reduced motion and pause settle immediately; deletion never leaves a ghost.
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.evaluate(()=>{BacCampus.setScenario('plan');fixturePlan('running','orbit',5,'job4');});
  await wait(()=>BacCampus.inspect().visitorTravel[0]?.phase==='working');
  await page.evaluate(()=>fixturePlan('error','orbit',5,'job4'));await wait(()=>BacCampus.inspect().visitorTravel.length===0);
  // Mixed hired/built-in team, then reset while motion is paused.
  await page.evaluate(()=>{
   fixturePlan('running','pixel',5,'mixed');const s=fixtureState;
   Object.assign(s.agents[8],{visitorKey:'orbit',name:'Orbit',avatar:fixtureAgents[1].avatar,displayed:true,included:true});
   Object.assign(s.agents[6],{displayed:true,included:true});s.crewMission.enabledRoles=[0,5,6,8];s.crewMission.assignedRoles=[5,6,8];BacCampus.setLive(s);
  });
  await wait(()=>BacCampus.inspect().visitorTravel.length===2&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='working'));
  s=await inspect();assert(!s.residents.some(r=>r.visible));assert(s.crewExchange[6].visible);assert.notDeepEqual(s.visitorTravel[0].position,s.visitorTravel[1].position);
  await page.emulateMedia({reducedMotion:'no-preference'});await page.locator('#campus-motion').click();assert(!(await inspect()).motion);
  await page.evaluate(()=>{fixtureState.crewMission=null;fixtureState.agents.forEach((a,i)=>a.displayed=i===0);BacCampus.setLive(fixtureState);});
  await wait(()=>BacCampus.inspect().visitorTravel.length===0);assert((await inspect()).residents.every(r=>r.visible));
  await page.evaluate(()=>fixturePlan('running','pixel',5,'job5'));await wait(()=>BacCampus.inspect().visitorTravel[0]?.phase==='working');
  await page.evaluate(()=>{fixtureAgents=fixtureAgents.filter(a=>a.key!=='pixel');BacCampus.setCollection(fixtureAgents,'orbit');});
  assert.equal((await inspect()).visitorTravel.length,0);assert.equal(await page.locator('[data-visitor-agent="pixel"]').count(),0);
  await page.evaluate(()=>fixturePlan('running',null,5,'job6'));assert.equal((await inspect()).visitorTravel.length,0);assert((await inspect()).crewExchange[5].visible,'Built-in backup still enters');
  assert.deepEqual(errors,[]);
  console.log('PASS: selected visitors only, identity, no duplicate, label selection, room/scenario switching, completion/history, mid-walk cancellation/reassignment, offscreen completion, reduced motion, deletion, backup entrance. Real WebGL with simulated workflow snapshots.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

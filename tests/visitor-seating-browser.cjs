// Real WebGL scene with controlled workflow snapshots; no model or user data.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync(path.join(__dirname,'../app/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,s=>s.includes('window.BacStudio=')?'':s);
  await page.route('http://seating.test/',r=>r.fulfill({contentType:'text/html',body:html}));
  await page.goto('http://seating.test/');await page.waitForFunction(()=>window.BacCampus?.inspect().sceneStyle);
  await page.evaluate(()=>{
   const root=document.querySelector('#agent-campus');root.hidden=false;delete root.dataset.boot;root.classList.add('studio-enabled');
   window.hires=[{key:'jinny',name:'Jinny',avatar:{body:'classic',color:'green',accessory:'none'}},{key:'orbit',name:'Orbit',avatar:{body:'round',color:'cyan',accessory:'none'}}];
   window.renderSeating=(count=2,meetingStatus=null,id='saved-plan',scenario='plan')=>{
    const agents=Array.from({length:count},(_,i)=>hires[i]||{key:'hire-'+i,name:'Hire '+i,avatar:hires[0].avatar});
    const s=BacDemo.snapshot();s.live=true;s.phase=0;s.visitorTeamMode='mixed';s.agents=s.agents.map((a,i)=>({...a,lane:0,displayed:[0,5,8].includes(i),included:[0,5,8].includes(i)}));
    s.crewMission=meetingStatus?{id,kind:'plan',status:meetingStatus,visitorsPresent:false,assignedRoles:[5,8],activeStages:[],enabledRoles:[0,5,8],completed:[5,8],roundtable:{members:agents,replies:{}}}:null;
    BacCampus.setScenario(scenario);BacCampus.setCollection(agents,'jinny');BacCampus.setLive(s);BacCampus.setRoom('mission',{instant:true});window.seatingState=s;
   };
   renderSeating();
  });
  const inspect=()=>page.evaluate(()=>BacCampus.inspect());
  const seats=async expected=>page.waitForFunction(n=>{const s=BacCampus.inspect();return s.visitorSeating.chairs+s.roundtable.visibleChairs===n;},expected,{timeout:5000});
  await seats(2);
  // Reopening completed personal reactions previously left a second set of chairs.
  await page.evaluate(()=>renderSeating(2,'done'));await seats(2);
  let s=await inspect();assert.equal(s.roundtable.visible,false);assert.equal(s.visitorSeating.chairs,2);
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  if(process.env.BAC_TEST_SCREENSHOT)await page.locator('#campus-viewport').screenshot({path:process.env.BAC_TEST_SCREENSHOT});
  for(const count of [3,1,0,2,5,12,2]){await page.evaluate(n=>renderSeating(n),count);await seats(count);assert.equal((await inspect()).visitorSeating.chairs,count);}
  await page.evaluate(()=>renderSeating(2,'running','new-reactions'));await seats(2);
  s=await inspect();assert.equal(s.visitorSeating.chairs,2);assert.equal(s.roundtable.visibleChairs,0);
  await page.evaluate(()=>{seatingState.crewMission.status='cancelled';BacCampus.setLive(seatingState);});
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.every(g=>g.phase==='returned'));
  await page.evaluate(()=>BacCampus.setLive(seatingState));await seats(2);assert.equal((await inspect()).roundtable.visible,false);
  await page.evaluate(()=>renderSeating(2,'done'));await seats(2);assert.equal((await inspect()).roundtable.visible,false);
  // One contributor and five idle hires return together after a completed task.
  await page.evaluate(()=>{
   renderSeating(6);const s=seatingState;s.visitorTeamMode='hired';
   s.agents.forEach((a,i)=>a.displayed=i===0||i===5);
   Object.assign(s.agents[5],{visitorKey:hires[0].key,name:'Jinny',avatar:hires[0].avatar,role:'Programmer'});
   s.crewMission={id:'finished-task',visitorJobId:'finished-task',kind:'plan',status:'done',visitorsPresent:true,visitorsFinished:true,assignedRoles:[5],activeStages:[],enabledRoles:[0,5],completed:[5]};
   BacCampus.setLive(s);
  });
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.find(v=>v.key==='jinny')?.phase==='working');
  const desk=(await inspect()).visitorTravel.find(v=>v.key==='jinny').position;
  await page.evaluate(()=>BacCampus.setLive(seatingState));
  assert.deepEqual((await inspect()).visitorTravel.find(v=>v.key==='jinny').position,desk,'Completion alone keeps the contributor at the desk');
  await page.evaluate(()=>BacCampus.overview({instant:true}));
  assert.equal((await inspect()).visitorTravel.find(v=>v.key==='jinny').phase,'working','Overview does not release a completed desk');
  await page.evaluate(()=>{BacCampus.setRoom('mission',{instant:true});BacCampus.setRoom('lounge',{instant:true});BacCampus.setLive(seatingState);});
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===0);
  assert.equal((await inspect()).residents.filter(r=>r.visible).length,6,'All six hires return to Lounge');
  await page.evaluate(()=>{BacCampus.setLive(seatingState);BacCampus.setRoom('mission',{instant:true});});
  const allSeated=()=>page.waitForFunction(()=>{const v=BacCampus.inspect().visitorTravel;return v.length===6&&v.every(v=>v.phase==='seated'&&v.role===null);});
  await allSeated();await seats(6);
  // The next plan initially retains old bindings; they must not replay old work.
  await page.evaluate(()=>{Object.assign(seatingState.crewMission,{id:'next-task',status:'running',activeStages:[0]});BacCampus.setLive(seatingState);});
  await allSeated();
  await page.evaluate(()=>{Object.assign(seatingState.crewMission,{visitorJobId:'next-task',visitorsFinished:false,activeStages:[5],completed:[]});BacCampus.setLive(seatingState);});
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.find(v=>v.key==='jinny')?.phase==='working');
  await page.evaluate(()=>BacCampus.setRoom('lounge',{instant:true}));
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===1);
  assert.equal((await inspect()).visitorTravel[0].phase,'working','Navigation preserves active work');
  // The result can be ready while optional reactions keep the job running.
  await page.evaluate(()=>{Object.assign(seatingState.crewMission,{visitorsFinished:true,activeStages:[],completed:[5]});BacCampus.setLive(seatingState);});
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===0);
  await page.evaluate(()=>BacCampus.setRoom('mission',{instant:true}));await allSeated();await seats(6);
  assert(!(await inspect()).crewExchange[5].visible,'No duplicate built-in specialist appears');
  assert.deepEqual(errors,[]);console.log('PASS: chairs follow 0/1/2/3/5/12 hires; six-hire Lounge return, standby re-entry, saved history, next-plan bindings, active work and result-ready reactions.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

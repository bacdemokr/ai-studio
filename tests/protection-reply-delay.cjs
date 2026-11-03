const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let events=[],jobs=[],crewChats=[],latestMission=null,owner;
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();owner=state.agentId;
   const profile={name:'Shield',persona:'guide',tone:'kind',skills:['weather'],protection:'openshell',avatar:{body:'round',color:'cyan',accessory:'headset'}};
   await route.fulfill({response,json:{...state,profile,agents:[{...profile,key:owner,pending:0,activity:null,latestMission}],jobs,crewChats,protectionEvents:events}});
  });
  const turn=(id,answer,role=null,time=Date.now()/1000)=>({id,kind:role===null?'chat':'crew-chat',status:'done',created:time-5,events:[{time,message:'Completed'}],payload:{prompt:'Read example.com',...(role===null?{}:{crewRole:role})},result:{answer}});
  const deny=(id,role)=>{const time=Date.now()/1000;return{id,owner,role,time,observedAt:time,source:'OpenShell policy log',action:'deny',host:'example.com'}};
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8094');
  await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  jobs=[turn('old-personal','Earlier personal reply',null,Date.now()/1000-100)];await page.evaluate(()=>BacStudio.refresh());
  jobs.push(turn('new-personal','Delayed personal reply'));latestMission={id:'new-personal',status:'done',answerPreview:'Delayed personal reply'};
  events.push(deny('personal-delay',null));await page.evaluate(()=>BacStudio.refresh());
  assert((await page.locator('#studio-conversation').innerText()).includes('Earlier personal reply'));
  assert((await page.locator('#studio-conversation').innerText()).includes('Delayed personal reply'),'Completed replies must be visible while the shield animates');
  assert.equal(await page.locator('#studio-conversation .shield-reply-wait').count(),0);
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.id==='personal-delay'&&h.visible));
  await page.evaluate(()=>BacStudio.refresh());
  assert.equal((await page.evaluate(()=>BacCampus.inspect().protectionHits)).filter(h=>h.id==='personal-delay').length,1,'Polling must not replay the shield');
  await page.emulateMedia({reducedMotion:'reduce'});
  jobs.push(turn('normal','Normal reply without delay'));await page.evaluate(()=>BacStudio.refresh());
  assert((await page.locator('#studio-conversation').innerText()).includes('Normal reply without delay'));
  events.push(deny('reduced-motion',null));await page.waitForTimeout(4600);events[events.length-1]=deny('reduced-motion',null);jobs.push(turn('reduced','Reduced-motion reply'));await page.evaluate(()=>BacStudio.refresh());
  assert((await page.locator('#studio-conversation').innerText()).includes('Reduced-motion reply'));
  assert.equal(await page.locator('.shield-reply-wait').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: Lounge replies appear alongside native-evidence shield; reduced motion, earlier replies and normal replies preserved, no replay. Fixture only.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

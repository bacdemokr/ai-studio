const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});const errors=[];let events=[],owner;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',e=>{if(e.type()==='error')errors.push(e.text())});
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();owner=state.agentId;
   const profile={name:'Shield',persona:'guide',skills:['weather'],protection:'openshell',avatar:{body:'round',color:'cyan',accessory:'headset'}};
   await route.fulfill({response,json:{...state,profile,agents:[{...profile,key:owner,pending:0}],protectionEvents:events}});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8094');await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  function deny(id,role){const now=Date.now()/1000;return{id,owner,role,action:'deny',source:'OpenShell policy log',host:'example.com',time:now,observedAt:now};}
  events=[deny('crew-hit',1)];await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.visible));
  assert.equal(await page.locator('.world-protection-hit:visible').count(),1);
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.phase==='impact'));
  await page.waitForTimeout(180);
  await page.screenshot({path:'../../work/dylan-shield-hit.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===1&&h.phase==='blocked'));
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0,'polling must not replay');
  await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>BacCampus.inspect().motion===false);
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  events=[...events,deny('personal-hit',null)];await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.some(h=>h.role===null&&h.visible));
  assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.find(h=>h.role===null).animated,false);
  await page.screenshot({path:'../../work/lounge-shield-hit.png'});
  await page.waitForFunction(()=>BacCampus.inspect().protectionHits.length===0);
  events=[deny('stale',1)];events[0].time-=100;events[0].observedAt-=100;
  await page.evaluate(()=>BacStudio.refresh());assert.equal((await page.evaluate(()=>BacCampus.inspect())).protectionHits.length,0);
  assert.deepEqual(errors,[]);console.log('PASS: crew and personal shield, correct target, native event trigger, dedupe, expiry, reduced motion. Injected fixture evidence.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

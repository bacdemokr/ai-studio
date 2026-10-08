// Read-only navigation checks; no agents, jobs or model requests are created.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacCampus?.inspect().navigation&&window.BacStudio);
  const settled=()=>page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const click=id=>page.locator('.world-room-map [data-world-room='+id+']').click();
  const scenario=async id=>{await page.locator('.world-room-map [data-world-scenario='+id+']').click();await page.waitForFunction(id=>{const n=BacCampus.inspect().navigation;return n.activeScenario===id&&!n.overview;},id);};
  const nav=()=>page.evaluate(()=>BacCampus.inspect().navigation);
  const targetFocus=n=>[n.rooms.mission[0],.25,n.rooms.mission[2]+.6];
  await settled();await click('workshop');await settled();
  for(const id of ['event-brief','plan']){
   const start=(await nav()).focus;
   await scenario(id);await page.waitForFunction(()=>BacCampus.inspect().navigation.travelling);
   assert.equal((await nav()).route.length,1,'One destination, no intermediate Lounge stop');
   const samples=await page.evaluate(async()=>{
    const points=[];
    do{points.push(BacCampus.inspect().navigation.focus);await new Promise(requestAnimationFrame);}
    while(BacCampus.inspect().navigation.travelling);
    return points;
   });
   const end=targetFocus(await nav());
   assert.deepEqual((await nav()).focus,end);
   for(const p of samples){
    const dx=end[0]-start[0],dz=end[2]-start[2];
    assert(Math.abs((p[0]-start[0])*dz-(p[2]-start[2])*dx)<.001,'Camera focus follows a direct path');
   }
   await click('workshop');await page.waitForFunction(()=>BacCampus.inspect().navigation.travelling);
   assert.equal((await nav()).route.length,1);await settled();
   assert.deepEqual((await nav()).focus,[0,1,18.6]);
  }
  // A new selection replaces the in-flight destination immediately.
  await scenario('plan');await page.waitForFunction(()=>BacCampus.inspect().navigation.travelling);
  await click('lounge');await click('workshop');await settled();
  assert.deepEqual((await nav()).focus,[0,1,18.6]);
  await scenario('event-brief');await page.setViewportSize({width:1280,height:800});await settled();
  assert.deepEqual((await nav()).focus,targetFocus(await nav()));
  await page.locator('.world-overview-button').click();await settled();assert((await nav()).overview);
  await scenario('plan');await settled();assert(!(await nav()).overview);
  await page.emulateMedia({reducedMotion:'reduce'});
  await click('workshop');assert(!(await nav()).travelling);
  await scenario('event-brief');await page.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='event-brief');
  assert(!(await nav()).travelling);assert.deepEqual((await nav()).focus,targetFocus(await nav()));
  assert.deepEqual(errors,[]);
  console.log('PASS: direct paths in both scenarios, return, rapid retargeting, resize, overview and reduced motion.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

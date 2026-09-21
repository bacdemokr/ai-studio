const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8082');await page.waitForFunction(()=>window.BacStudio);
  for(const [body,color,accessory] of [['claw','violet','glasses'],['crab','coral','cap'],['round','cyan','headset']]){
   await page.locator('.world-room-map [data-world-room=workshop]').click();
   await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-body-picker [data-body='+body+']').click();
   await page.locator('#studio-color-picker [data-avatar-color='+color+']').click();
   await page.locator('#studio-accessory').selectOption(accessory);
   const expected={body,color,accessory,protection:'standard'};
   const previous=await page.evaluate(()=>BacCampus.inspect().residents.map(r=>r.key));
   await page.locator('#studio-create').click();
   await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='loading');
   const arrival=await page.evaluate(()=>BacCampus.inspect().arrival);
   assert(!previous.includes(arrival.key));assert.deepEqual(arrival.avatar,expected);
   assert.equal(await page.locator('#studio-onboarding').evaluate(e=>e.inert),true);
   // A stale selection event or poll must not change the actor during the walk.
   if(previous.length)await page.evaluate(key=>document.querySelector('#agent-campus').dispatchEvent(new CustomEvent('bac:collection-select',{detail:key})),previous[0]);
   await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='walking');
   assert.deepEqual((await page.evaluate(()=>BacCampus.inspect().arrival)).avatar,expected);
   await page.waitForFunction(()=>!BacCampus.inspect().arrival&&BacCampus.inspect().room==='lounge',{}, {timeout:18000});
   const resident=await page.evaluate(key=>BacCampus.inspect().residents.find(r=>r.key===key),arrival.key);
   assert.deepEqual(resident.avatar,expected);
   assert.equal(await page.locator('#studio-onboarding').evaluate(e=>e.inert),false);
  }
  assert.deepEqual(errors,[]);console.log('PASS: three distinct created identities retain body, color and accessories through loading, walking and arrival; stale selection ignored.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

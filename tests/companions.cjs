const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1500,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await p.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
 for(const body of ['operative','claw','crab']){
  await p.locator('.world-room-map [data-world-room=workshop]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await p.locator('[data-body='+body+']').click();await p.locator('#studio-name').fill(body);
  for(const accessory of ['none','antenna','headset','glasses','cap']){await p.locator('#studio-accessory').selectOption(accessory);assert.equal(await p.evaluate(()=>BacCampus.inspect().draft.avatar.body),body);}
  await p.screenshot({path:'/private/tmp/bac-avatar-'+body+'.png'});
  await p.locator('#studio-create').click();await p.waitForFunction(body=>BacStudio.inspect().profile?.name===body,body);await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await p.waitForFunction(()=>BacStudio.inspect().room==='lounge');
  assert.equal(await p.evaluate(()=>BacStudio.inspect().profile.avatar.body),body);
 }
 await p.reload();await p.waitForFunction(()=>window.BacStudio?.inspect().profile?.avatar.body==='crab');
 assert.deepEqual(errors,[]);console.log('PASS: operative/claw/crab with all accessories, native creation and reload persistence; no renderer errors.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

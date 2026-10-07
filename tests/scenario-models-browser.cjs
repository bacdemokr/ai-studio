const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio&&window.BacCampus?.inspect().navigation?.overview);
 assert.equal(await page.evaluate(()=>BacStudio.inspect().runtime.version),'SCENARIO TEST FIXTURE');
 await page.locator('.world-campus-room[data-world-room=workshop]').click();await page.locator('#studio-name').fill('Model fixture');await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Model fixture'&&!BacCampus.inspect().arrival);
 const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);};
 await choose('event-brief');await page.locator('#studio-team-setup').click();
 assert.equal(await page.locator('#studio-scenario-provider').inputValue(),'api');
 await page.locator('#studio-scenario-provider').selectOption('local');await page.locator('#studio-scenario-load').click();await page.waitForFunction(()=>document.querySelector('#studio-scenario-model').options.length===1);
 await page.locator('#studio-scenario-apply').click();await page.waitForFunction(()=>document.querySelector('#studio-scenario-status').textContent.startsWith('Applied.'));
 await page.locator('#studio-dialog').evaluate(d=>d.close());await choose('plan');await page.locator('#studio-team-setup').click();assert.equal(await page.locator('#studio-scenario-provider').inputValue(),'api');
 await page.locator('#studio-dialog').evaluate(d=>d.close());await choose('event-brief');await page.locator('#studio-team-setup').click();assert.equal(await page.locator('#studio-scenario-provider').inputValue(),'local');assert.equal(await page.locator('#studio-scenario-model').inputValue(),'fixture-local-model');
 await page.locator('#studio-scenario-provider').selectOption('api');await page.locator('#studio-scenario-apply').click();await page.waitForFunction(()=>document.querySelector('#studio-scenario-status').textContent.startsWith('Applied.'));
 await page.locator('#studio-dialog').evaluate(d=>d.close());await page.locator('#studio-team-setup').click();assert.equal(await page.locator('#studio-scenario-provider').inputValue(),'api');await page.locator('#studio-scenario-provider').selectOption('local');assert.equal(await page.locator('#studio-scenario-model').inputValue(),'fixture-local-model');
 assert.deepEqual(errors,[]);console.log('PASS: local model discovery/application, scenario isolation, persistence and API restore.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

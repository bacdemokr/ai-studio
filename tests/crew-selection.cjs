const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];let submitted;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/jobs',r=>{submitted=r.request().postDataJSON();return r.fulfill({status:503,json:{error:'Fixture mission unavailable; try again.'}});});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row[data-status=ready]').length===4);
  assert.equal(await page.locator('[name=crewRole]:checked').count(),4);
  assert(await page.locator('[name=crewRole][value="0"]').isDisabled(),'Casey remains the required coordinator');
  assert.equal(await page.locator('[name=personalLead],[name^=member]').count(),0);
  for(const i of [1,3])await page.locator('[name=crewRole][value="'+i+'"]').uncheck();
  await page.locator('#studio-launch-event').click();
  await page.waitForFunction(()=>document.querySelector('#studio-demo-preparation').textContent.includes('Fixture mission unavailable'));
  assert.deepEqual(submitted.enabledRoles,[0,2]);assert(submitted.preparationId);assert.equal(submitted.workflow,'showcase');
  assert(await page.locator('#studio-dialog').evaluate(e=>e.open));
  assert.deepEqual(await page.locator('[name=crewRole]:checked').evaluateAll(nodes=>nodes.map(n=>Number(n.value))),[0,2],'Failed launch preserves crew choices');
  assert.deepEqual(errors,[]);
  console.log('PASS: four current crew roles, mandatory Casey, selected roles submitted with preparation, failed launch preserves choices. No real inference.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

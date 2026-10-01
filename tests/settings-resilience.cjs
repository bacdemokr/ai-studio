const assert=require('node:assert/strict'),{chromium}=require('playwright');
const settings={provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{local:{model:'original',contextWindow:32768}},location:{city:'Zurich'}};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});let failures=0;
 async function scenario(name,run){
  const page=await browser.newPage(),errors=[];page.setDefaultTimeout(6000);
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/settings',r=>r.fulfill({json:settings}));
  await page.route('**/api/telegram',r=>r.fulfill({json:{connected:false}}));
  try{
   await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');
   await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
   await run(page);assert.deepEqual(errors,[]);console.log('PASS:',name);
  }catch(error){failures++;console.error('FAIL:',name,error.message);}
  finally{await page.unrouteAll({behavior:'wait'});await page.close();}
 }
 try{
  await scenario('Telegram status failure does not block model, location or reset settings',async page=>{
   await page.route('**/api/telegram',r=>r.fulfill({status:503,json:{error:'Telegram status temporarily unavailable.'}}));
   await page.locator('#studio-config').click();
   await page.locator('#studio-model').waitFor();
   await page.locator('#studio-settings-location-tab').click();assert.equal(await page.locator('#studio-location-city').inputValue(),'Zurich');
   await page.locator('#studio-settings-reset-tab').click();assert.equal(await page.locator('#studio-settings-reset-panel #studio-bac-reset').count(),0);assert.equal(await page.locator('#studio-reset-all').count(),0);assert.equal(await page.locator('#studio-settings-reset-panel button').count(),1);
   await page.locator('#studio-settings-telegram-tab').click();
   assert.match(await page.locator('#studio-telegram-status').innerText(),/temporarily unavailable/);
   assert(await page.locator('#studio-telegram-test').isHidden());
  });
  await scenario('a slower first settings open cannot overwrite a newer form draft',async page=>{
   let finish,reads=0;
   await page.route('**/api/settings',async r=>{if(++reads===1)await new Promise(resolve=>finish=resolve);await r.fulfill({json:settings});});
   try{
    await page.locator('#studio-config').click();
    while(!finish)await page.waitForTimeout(25);
    await page.locator('#studio-config').click();
    await page.locator('#studio-model').fill('keep-my-new-draft');
    finish();await page.waitForTimeout(350);
    assert.equal(await page.locator('#studio-model').inputValue(),'keep-my-new-draft');
   }finally{finish?.();}
  });
 }finally{await browser.close();}
 if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});

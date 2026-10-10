// Run with fixture_scenarios.py. All keys, catalogs and Telegram replies are fake.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
  let telegram={connected:false},writes=0;
  await page.route('**/api/telegram',route=>{
   if(route.request().method()==='POST'){const value=route.request().postDataJSON();telegram=value.disconnect?{connected:false}:{connected:true,bot:'fixture_bot',chatId:value.chatId};writes++;}
   return route.fulfill({json:telegram});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();
  assert.deepEqual(await page.locator('[data-settings-tab]').allTextContents(),['Model','Location','Telegram','Reset']);
  assert.equal(await page.locator('#studio-provider,#studio-api-key,#studio-team-config-form').count(),0);
  await page.locator('[data-connection-edit=api]').click();await page.locator('#studio-connect-provider').selectOption('openai');
  await page.locator('#studio-connect-key').fill('fixture-unsaved-key');await page.locator('#studio-connect-model').fill('fixture-draft-model');
  await page.locator('#studio-settings-location-tab').click();await page.locator('#studio-location-city').fill('Seoul');
  await page.locator('#studio-settings-telegram-tab').click();await page.locator('#studio-telegram-chat').fill('123456');await page.locator('#studio-telegram-token').fill('fixture-token');
  await page.locator('#studio-settings-telegram-tab').press('Home');
  assert(await page.locator('#studio-model-connections').isVisible());assert.equal(await page.locator('#studio-connect-model').inputValue(),'fixture-draft-model');assert.equal(await page.locator('#studio-connect-key').inputValue(),'fixture-unsaved-key');
  await page.locator('#studio-settings-model-tab').press('ArrowLeft');assert(await page.locator('#studio-settings-reset-panel').isVisible());
  await page.locator('#studio-settings-reset-tab').press('ArrowRight');assert(await page.locator('#studio-model-connections').isVisible());
  await page.locator('#studio-settings-location-tab').click();assert.equal(await page.locator('#studio-location-city').inputValue(),'Seoul');
  await page.locator('#studio-save-settings').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent.startsWith('Saved.'));
  assert.equal((await page.evaluate(()=>fetch('/api/settings').then(r=>r.json()))).location.city,'Seoul');
  await page.locator('#studio-settings-telegram-tab').click();assert.equal(await page.locator('#studio-telegram-token').inputValue(),'fixture-token');
  await page.locator('#studio-save-settings').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent.startsWith('Bot connected.'));
  assert.equal(await page.locator('#studio-telegram-token').inputValue(),'');assert(await page.locator('#studio-telegram-test').isEnabled());
  await page.locator('#studio-telegram-disconnect').click();await page.waitForFunction(()=>document.querySelector('#studio-settings-status').textContent==='Disconnected.');assert.equal(writes,2);
  await page.locator('#studio-settings-model-tab').click();await page.locator('#studio-dialog-close').click();
  await page.waitForFunction(()=>document.querySelector('#studio-connect-key').value==='');
  await page.locator('#studio-config').click();await page.locator('[data-connection-edit=api]').click();assert.equal(await page.locator('#studio-connect-key').inputValue(),'');
  await page.screenshot({path:'/tmp/bac-unified-settings.png'});
  assert.deepEqual(errors,[]);console.log('PASS: unified settings, keyboard navigation, retained drafts, location save, Telegram connect/disconnect and key clearing.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

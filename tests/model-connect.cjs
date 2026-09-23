const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/agent_led_fixture.py'],{encoding:'utf8'}));
 fixture.state.runtime={installed:true,gateway:true,model:false,ready:false};
 fixture.state.canConfigure=true;
 const settings={provider:'nvidia',providers:{nvidia:{label:'NVIDIA Inference (Employee only)',baseUrl:'https://inference-api.nvidia.com/v1'}},profiles:{nvidia:{model:'fixture-model',baseUrl:'https://inference-api.nvidia.com/v1',contextWindow:32768,hasKey:false}}};
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));let attempts=0,ready=false;
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
  await page.route('**/api/telegram',r=>r.fulfill({json:{connected:false}}));
  await page.route('**/api/runtime',r=>r.fulfill({json:{installed:true,gateway:true,model:ready,ready}}));
  await page.route('**/api/settings',async r=>{
   if(r.request().method()==='GET')return r.fulfill({json:settings});
   const body=r.request().postDataJSON();assert.equal(body.verifyConnection,true);assert.equal(body.apiKey,'fixture-secret-not-real');assert.equal(body.model,'fixture-model');attempts++;
   await new Promise(resolve=>setTimeout(resolve,350));
   if(attempts===1)return r.fulfill({status:502,json:{error:'Authentication failed (HTTP 401).'}});
   ready=true;settings.profiles.nvidia.hasKey=true;await r.fulfill({json:settings});
  });
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  assert.equal(await page.locator('#studio-model').inputValue(),'fixture-model','Reconnect preserves the selected model even if runtime is not ready');
  await page.locator('#studio-api-key').fill('fixture-secret-not-real');await page.locator('#studio-save-settings').click();
  assert.equal(await page.locator('#studio-save-settings').innerText(),'Connecting');assert(await page.locator('#studio-save-settings').isDisabled());
  assert.equal(await page.locator('#studio-api-key').inputValue(),'fixture-secret-not-real');
  await page.waitForFunction(()=>document.querySelector('#studio-settings-status').dataset.state==='error');
  assert.match(await page.locator('#studio-settings-status').innerText(),/HTTP 401/);
  assert.equal(await page.locator('#studio-api-key').inputValue(),'fixture-secret-not-real','Failed connection keeps the input for retry');
  assert.equal(await page.locator('#studio-model').inputValue(),'fixture-model');
  assert.equal(await page.locator('#studio-save-settings').innerText(),'Connect model');
  await page.locator('#studio-save-settings').click();await page.waitForFunction(()=>!document.querySelector('#studio-dialog').open);
  assert.equal(attempts,2);assert.equal(await page.locator('#studio-api-key').inputValue(),'');
  assert.deepEqual(errors,[]);console.log('PASS: configured model retained, visible connecting state, failure detail, key retained on failure, immediate retry and clearing only after verified success.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

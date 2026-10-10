const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const state=JSON.parse(execFileSync('python3',['-B','-c',`
import sys,json
sys.path[:0]=['scripts','tests']
from test_agent_deletion import DeletionTests
c=DeletionTests();c.setUp()
try:
 s=c.studio.state(c.scout);s.update(csrf='fixture',canConfigure=True)
 print(json.dumps(s))
finally:c.tearDown()
`],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  let runtime={gateway:true,ready:true,model:true,gatewayState:'ready'},retries=0,settingsWrites=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const interval=window.setInterval;window.setInterval=(fn,ms,...args)=>{if(ms===10000)window.__runtimePoll=fn;return interval(fn,ms,...args);};});
  // No fixture action reaches the live API or changes the user's data.
  await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/session')return route.fulfill({json:{...state,runtime}});
   if(url.pathname==='/api/state')return route.fulfill({json:state});
   if(url.pathname==='/api/runtime'){if(url.searchParams.has('retry'))retries++;return route.fulfill({json:runtime});}
   if(url.pathname==='/api/settings/connections')return route.fulfill({json:{connections:{local:{ready:false,enabled:false,message:'Not configured'},api:{ready:false,enabled:false,message:'Not configured'}},loungePreference:'auto',scenarioPreferences:{}}});
   if(url.pathname==='/api/settings'){if(route.request().method()==='POST')settingsWrites++;return route.fulfill({json:{provider:'nvidia',providers:{nvidia:{label:'Fixture provider',baseUrl:'https://example.invalid/v1'}},profiles:{}}});}
   return route.fulfill({json:{}});
  });
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');
  await page.waitForFunction(()=>window.BacStudio);
  const badge=page.locator('.campus-sim');
  assert.equal(await badge.innerText(),'● Ready');
  await page.evaluate(()=>BacStudio.setRoom('lounge'));
  await page.locator('#studio-prompt').fill('Keep this draft');
  runtime={...runtime,gatewayState:'slow'};await page.evaluate(()=>window.__runtimePoll());
  assert.match(await badge.innerText(),/responding slowly/);assert.equal(await badge.getAttribute('data-warning'),'false');
  if(process.env.BAC_HEALTH_SCREENSHOT)await badge.screenshot({path:process.env.BAC_HEALTH_SCREENSHOT});
  assert.equal(await badge.getAttribute('data-slow'),'true');assert.equal(await page.locator('#studio-send').isDisabled(),false);
  assert.equal(await badge.getAttribute('data-actionable'),'false');
  runtime={...runtime,gateway:false,ready:false,gatewayState:'unavailable'};await page.evaluate(()=>window.__runtimePoll());
  assert.equal(await page.locator('#studio-send').isDisabled(),true);assert.match(await badge.innerText(),/unavailable/);
  assert.equal(await page.locator('#studio-chat-connect').innerText(),'Retry connection');
  await page.locator('#studio-chat-connect').click();assert.equal(retries,1);assert.equal(await page.locator('#studio-dialog').evaluate(e=>e.open),false);
  runtime={...runtime,gateway:true,ready:true,gatewayState:'ready'};await page.evaluate(()=>window.__runtimePoll());
  assert.equal(await badge.innerText(),'● Ready');assert.equal(await page.locator('#studio-prompt').inputValue(),'Keep this draft');
  assert.equal(await page.locator('#studio-send').isDisabled(),false);
  runtime={...runtime,model:false,ready:false};await page.evaluate(()=>window.__runtimePoll());
  assert.match(await badge.innerText(),/Model not connected/);assert.equal(await page.locator('#studio-chat-connect').innerText(),'Connect model');
  await badge.click();await page.waitForFunction(()=>document.querySelector('#studio-dialog').open);
  assert.equal(settingsWrites,0);assert.deepEqual(errors,[]);
  console.log('PASS: slow/unavailable/recovered/model-missing states, composer gating, draft retention, retry without Settings or API-key writes. Stubbed API only.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

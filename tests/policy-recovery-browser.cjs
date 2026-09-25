// Policy reads are mocked; no real OpenShell permissions or user data are changed.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const original=setTimeout;window.setTimeout=(fn,ms,...args)=>original(fn,ms===45000?250:ms,...args);});
  await page.route(/\/api\/(session|state)$/,async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),json=await response.json();
   const profile={name:'Shield',persona:'guide',tone:'kind',verbosity:'balanced',purpose:'Check weather.',skills:['weather'],protection:'openshell',avatar:{body:'classic',color:'green',accessory:'none'}};
   Object.assign(json,{profile,agents:[{...profile,key:json.agentId,pending:false}],jobs:[]});
   await route.fulfill({response,json});
  });
  let updating=false,failed=false,hung=false,approved=false,reads=0;
  await page.route('**/api/agent-policy',async route=>{
   if(route.request().method()==='POST'){approved=true;updating=true;return route.fulfill({json:{applied:true}});}
   reads++;
   if(hung)return;
   if(failed)return route.fulfill({status:503,json:{error:'Test policy unavailable'}});
   await route.fulfill({json:{status:'applied',updating,requested:approved?['host:one.test']:[],catalog:{'host:one.test':{title:'one.test',hosts:['one.test']}},pendingAccess:[{host:'one.test'}],sandboxes:['fixture']}});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8097');
  await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const open=()=>page.locator('#studio-agent-policy').click(),close=()=>page.locator('#studio-surface-close').click();
  const ready=()=>page.locator('[data-policy-permission="host:one.test"]').waitFor({state:'visible'});
  await open();await ready();await close();

  updating=true;await open();await page.locator('.policy-loading').waitFor();
  updating=false;await ready();assert.equal(await page.locator('.policy-loading').count(),0);await close();

  updating=true;await open();await page.locator('.policy-loading').waitFor();failed=true;
  await page.locator('[data-policy-check]').waitFor();
  assert.equal(await page.locator('.policy-loading').count(),0);
  assert.match(await page.locator('#studio-policy-content').innerText(),/Test policy unavailable/);
  failed=false;updating=false;await page.locator('[data-policy-check]').click();await ready();

  await page.locator('[data-policy-permission="host:one.test"]').click();
  await page.locator('.policy-loading').waitFor();
  await page.waitForTimeout(100);updating=false;await ready();
  assert.equal(await page.locator('[data-policy-permission="host:one.test"]').innerText(),'Revoke');await close();

  hung=true;await open();await page.locator('[data-policy-check]').waitFor();
  assert.match(await page.locator('#studio-policy-content').innerText(),/took too long/);
  assert.equal(await page.locator('.policy-loading').count(),0);
  hung=false;await page.locator('[data-policy-check]').click();await ready();await close();

  updating=true;await open();await page.locator('.policy-loading').waitFor();await close();
  const before=reads;await page.waitForTimeout(2800);assert.equal(reads,before,'Closing the panel cancels refresh polling');
  await open();await page.locator('.policy-loading').waitFor();
  await page.evaluate(()=>document.querySelector('[data-surface="control"]').click());
  const switched=reads;await page.waitForTimeout(2800);assert.equal(reads,switched,'Switching panels cancels policy polling');
  assert.deepEqual(errors,[]);
  console.log('PASS: another-tab apply, own delayed verification, failed/hung reads, recovery and polling cancellation');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

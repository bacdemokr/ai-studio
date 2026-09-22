const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let preparation='running',reads=0;
  await page.route(/\/api\/(session|state)$/,async route=>{
   const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),json=await response.json();
   const profile={name:'Scout',persona:'guide',skills:['web'],protection:'openshell',tone:'kind',avatar:{body:'classic',color:'green',accessory:'antenna'}};
   Object.assign(json,{profile,agents:[{...profile,key:json.agentId,pending:0,activity:null,latestMission:null,workspacePreparation:preparation}],jobs:[]});
   await route.fulfill({response,json});
  });
  await page.route('**/api/agent-policy',async route=>{
   assert.equal(route.request().method(),'GET');reads++;
   await route.fulfill({json:{mode:'openshell',status:preparation==='done'?'applied':'awaiting-first-mission',preparing:preparation==='running',requested:[],catalog:{},sandboxes:preparation==='done'?[{name:'fixture',running:true}]:[],logs:[],history:[]}});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8094');
  await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Scout');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-agent-policy').click();
  await page.getByText('Preparing protected workspace automatically.',{exact:false}).waitFor();
  assert.equal(await page.locator('[data-policy-retry]').count(),0);
  assert.equal(await page.locator('#studio-policy-content .studio-policy-error').count(),0);
  const before=reads;preparation='done';
  await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>document.querySelector('#studio-policy-content')?.textContent.includes('Approved websites'),null,{timeout:8000}).catch(async error=>{console.log({reads,errors,state:await page.evaluate(()=>BacStudio.inspect()),content:await page.locator('#studio-policy-content').innerText()});throw error;});
  assert(reads>before,'completion refreshes the open Policies panel');
  assert.equal(await page.getByText('Preparing protected workspace automatically.',{exact:false}).count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: background preparation notice, no duplicate prepare action, automatic verified-policy refresh. Fixture only.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

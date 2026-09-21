const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1450,height:1050}}),errors=[],posts=[];
  page.on('pageerror',error=>errors.push(error.message));
  let owner='',requested=[],finish,status='applied',pending=0,hold=true;
  let pendingAccess=[{host:'api.open-meteo.com'},{host:'wttr.in'}],pendingFiles=[];
  const catalog={
   'host:api.open-meteo.com':{title:'api.open-meteo.com',hosts:['api.open-meteo.com']},
   'host:wttr.in':{title:'wttr.in',hosts:['wttr.in']},
   'host:geocoding-api.open-meteo.com':{title:'geocoding-api.open-meteo.com',hosts:['geocoding-api.open-meteo.com']},
   weather:{title:'Weather & city lookup',hosts:['api.open-meteo.com','geocoding-api.open-meteo.com','wttr.in'],description:'Read live weather and look up a city.'},
   papers:{title:'arXiv papers',hosts:['export.arxiv.org','arxiv.org'],description:'Research preset'},
   'file:read:/fixture/notes.txt':{kind:'file',access:'read',title:'/fixture/notes.txt',path:'/fixture/notes.txt'},
   'file:write:/fixture/notes.txt':{kind:'file',access:'write',title:'/fixture/notes.txt',path:'/fixture/notes.txt'}
  };
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),json=await response.json();owner=json.agentId;
   const profile={id:'bac-'+owner,name:'Shield',persona:'guide',skills:['web'],protection:'openshell',avatar:{body:'classic',color:'green',accessory:'antenna'}};
   Object.assign(json,{profile,agents:[{...profile,key:owner,pending}],jobs:[]});await route.fulfill({response,json});
  });
  await page.route('**/api/agent-policy',async route=>{
   if(route.request().method()==='POST'){
    const body=route.request().postDataJSON();posts.push(body);if(hold)await new Promise(resolve=>finish=resolve);
    const keys=(body.permissions||[body.permission]).flatMap(key=>key.startsWith('file:')?[key]:catalog[key].hosts.map(host=>'host:'+host));
    requested=body.allow?[...new Set([...requested,...keys])]:requested.filter(key=>!keys.includes(key));
    pendingAccess=[];pendingFiles=[];return route.fulfill({json:{applied:true}});
   }
   return route.fulfill({json:{agentId:owner,mode:'openshell',status,requested,sandboxes:[{}],catalog,pendingAccess,pendingFiles}});
  });
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-agent-policy').click();
  const bulk=page.locator('[data-policy-approve-all]');
  assert.equal(await page.locator('#studio-policy-refresh').count(),0);
  async function reload(){await page.locator('#studio-surface-close').click();const response=page.waitForResponse(r=>r.url().endsWith('/api/agent-policy'));await page.locator('#studio-agent-policy').click();await response;await page.waitForTimeout(100);}
  await bulk.waitFor();assert.equal(await bulk.innerText(),'Approve all (2)');
  assert.equal(await page.locator('[data-policy-section=preset] [data-policy-approve-all]').count(),0);
  const heading=await page.locator('[data-policy-section=blocked] h3').boundingBox(),button=await bulk.boundingBox();
  assert.ok(button.x>heading.x+heading.width,'desktop bulk action follows the heading');
  if(process.env.BAC_TEST_SCREENSHOT)await page.screenshot({path:process.env.BAC_TEST_SCREENSHOT});
  await bulk.click();await page.waitForFunction(()=>document.querySelector('[data-policy-approve-all]')?.textContent==='Applying…');
  assert.equal(await bulk.isDisabled(),true);assert.equal(posts.length,1);
  assert.deepEqual(posts[0].permissions,['host:api.open-meteo.com','host:wttr.in']);assert.equal(posts[0].allow,true);
  assert.equal(await page.locator('[data-policy-permission="papers"]').isDisabled(),true);
  await bulk.evaluate(button=>button.click());assert.equal(posts.length,1,'disabled action cannot submit twice');
  finish();await page.waitForFunction(()=>!document.querySelector('[data-policy-approve-all]'));
  await page.locator('[data-policy-access-tab=webpage]').click();
  assert.equal(await page.locator('[data-policy-section=approved] [data-policy-allow=false]').count(),2);
  assert.ok((await page.locator('[data-policy-section=approved] h3').innerText()).startsWith('Approved access'));
  hold=false;requested=['host:api.open-meteo.com'];await reload();
  await page.locator('[data-policy-section=preset] [data-policy-permission=weather]').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-policy-section=approved] [data-policy-allow=false]').length===3);
  const approved=page.locator('[data-policy-section=approved]');
  assert.equal(await approved.locator('h3 span').innerText(),'3');
  assert.equal(await approved.locator('[data-policy-permission=weather]').count(),0,'preset is only an approval shortcut');
  assert.equal(await approved.locator('[data-policy-permission="host:api.open-meteo.com"]').count(),1,'overlapping host appears once');
  await approved.locator('[data-policy-permission="host:api.open-meteo.com"]').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-policy-section=approved] [data-policy-allow=false]').length===2);
  assert.deepEqual(posts.at(-1),{permission:'host:api.open-meteo.com',allow:false});
  assert.deepEqual(requested.sort(),['host:geocoding-api.open-meteo.com','host:wttr.in']);
  requested=[];pendingAccess=[{host:'wttr.in'}];await reload();assert.equal(await bulk.count(),0,'one request keeps its individual action');
  pendingAccess.push({host:'api.open-meteo.com'});pending=1;
  await page.waitForFunction(()=>BacStudio.inspect().agents?.some(agent=>agent.pending===1));
  await reload();assert.equal(await bulk.isDisabled(),true,'busy agent cannot be changed');
  pending=0;await page.waitForFunction(()=>BacStudio.inspect().agents?.every(agent=>!agent.pending));
  pendingAccess=[{host:'wttr.in'}];pendingFiles=['file:read:/fixture/notes.txt','file:write:/fixture/notes.txt'];
  await reload();assert.equal(await bulk.innerText(),'Approve all (2)');
  assert.deepEqual(JSON.parse(await bulk.getAttribute('data-policy-permissions')),['host:wttr.in','file:write:/fixture/notes.txt']);
  assert.equal(await page.getByText('Includes read/write access to 1 file',{exact:true}).count(),1);
  catalog['file:write:/fixture/notes.txt'].unavailableReason='Fixture unavailable';
  await reload();assert.equal(await bulk.isDisabled(),true,'no silent partial approval for an unavailable file');
  delete catalog['file:write:/fixture/notes.txt'].unavailableReason;
  catalog['file:write:/fixture/notes.txt'].suggested=true;await reload();assert.equal(await bulk.innerText(),'Confirm & approve all (2)');
  await page.setViewportSize({width:390,height:844});
  const mobile=await bulk.boundingBox();assert.ok(mobile.x>=0&&mobile.x+mobile.width<=390,'mobile action stays inside viewport');
  assert.deepEqual(errors,[]);
  console.log('PASS: bulk approval, per-host approved cards/counts, overlapping preset deduplication, individual revoke, busy/file guards and mobile layout. Mock policy only.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

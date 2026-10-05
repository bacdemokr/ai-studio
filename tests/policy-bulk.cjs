const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1450,height:1050}}),errors=[],posts=[];
  page.on('pageerror',error=>errors.push(error.message));
  let owner='',requested=[],finish,status='applied',pending=0,hold=true;
  let pendingAccess=[{host:'api.open-meteo.com'},{host:'wttr.in'}];
  const catalog={
   'host:api.open-meteo.com':{title:'api.open-meteo.com',hosts:['api.open-meteo.com']},
   'host:wttr.in':{title:'wttr.in',hosts:['wttr.in']},
   'host:geocoding-api.open-meteo.com':{title:'geocoding-api.open-meteo.com',hosts:['geocoding-api.open-meteo.com']},
   'host:export.arxiv.org':{title:'export.arxiv.org',hosts:['export.arxiv.org']},
   'host:arxiv.org':{title:'arxiv.org',hosts:['arxiv.org']},
   weather:{title:'Weather & city lookup',hosts:['api.open-meteo.com','geocoding-api.open-meteo.com','wttr.in'],description:'Read live weather and look up a city.'},
   papers:{title:'arXiv papers',hosts:['export.arxiv.org','arxiv.org'],description:'Research preset'},
  };
  await page.route(/\/api\/(session|state)$/,async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),json=await response.json();owner=json.agentId;
   const profile={id:'bac-'+owner,name:'Shield',persona:'guide',skills:['web'],protection:'openshell',avatar:{body:'classic',color:'green',accessory:'antenna'}};
   Object.assign(json,{profile,agents:[{...profile,key:owner,pending}],jobs:[]});await route.fulfill({response,json});
  });
  await page.route('**/api/agent-policy',async route=>{
   if(route.request().method()==='POST'){
    const body=route.request().postDataJSON();posts.push(body);if(hold)await new Promise(resolve=>finish=resolve);
    const keys=(body.permissions||[body.permission]).flatMap(key=>catalog[key].hosts.map(host=>'host:'+host));
    requested=body.allow?[...new Set([...requested,...keys])]:requested.filter(key=>!keys.includes(key));
    pendingAccess=[];return route.fulfill({json:{applied:true}});
   }
   return route.fulfill({json:{agentId:owner,mode:'openshell',status,requested,sandboxes:[{}],catalog,pendingAccess}});
  });
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Shield');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-agent-policy').click();
  const bulk=page.locator('[data-policy-approve-all][data-policy-scope=pending]');
  assert.equal(await page.locator('#studio-policy-refresh').count(),0);
  async function reload(){await page.locator('#studio-surface-close').click();const response=page.waitForResponse(r=>r.url().endsWith('/api/agent-policy'));await page.locator('#studio-agent-policy').click();await response;await page.waitForTimeout(100);}
  await bulk.waitFor();assert.equal(await bulk.innerText(),'Approve all');
  assert.equal(await page.locator('[data-policy-section=preset] [data-policy-approve-all]').count(),1);
  const heading=await page.locator('[data-policy-section=blocked] h3').boundingBox(),button=await bulk.boundingBox();
  assert.ok(button.x>heading.x+heading.width,'desktop bulk action follows the heading');
  if(process.env.BAC_TEST_SCREENSHOT)await page.screenshot({path:process.env.BAC_TEST_SCREENSHOT});
  await bulk.click();await page.getByText('Applying permissions…',{exact:true}).waitFor();
  assert.equal(await bulk.count(),0);assert.equal(posts.length,1);
  assert(await page.locator('#studio-policy-agent').isDisabled());
  assert.deepEqual(posts[0].permissions,['host:api.open-meteo.com','host:wttr.in']);assert.equal(posts[0].allow,true);
  assert.equal(await page.locator('[data-policy-permission="papers"]').count(),0);
  assert.equal(posts[0].scope,'pending');
  finish();await page.waitForFunction(()=>document.querySelectorAll('[data-policy-section=approved] [data-policy-allow=false]').length===2);
  assert.equal(await page.locator('[data-policy-section=approved] [data-policy-allow=false]').count(),2);
  assert.ok((await page.locator('[data-policy-section=approved] h3').innerText()).startsWith('Approved websites'));
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
  pendingAccess=[{host:'wttr.in'},{host:'api.open-meteo.com'}];await reload();
  assert.equal(await bulk.innerText(),'Approve all');
  assert.equal(await page.locator('[data-policy-access-tab]').count(),0,'no File/Webpage tabs');
  assert.equal(await page.locator('#studio-surface-title').innerText(),'OpenShell Policy');
  requested=[];pendingAccess=[];await reload();
  await page.locator('[data-policy-scope=presets]').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-policy-section=approved] [data-policy-allow=false]').length===5);
  assert.deepEqual(posts.at(-1).permissions,['weather','papers']);assert.equal(posts.at(-1).scope,'presets');
  assert.equal(await page.locator('[data-policy-scope=presets]').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: bulk approval, per-host approved cards/counts, overlapping preset deduplication, individual revoke, busy guards and separate pre-approval bulk action. Mock policy only.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

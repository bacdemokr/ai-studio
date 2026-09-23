const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const context=await browser.newContext();
 try{
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));let inference=0;
  page.on('request',r=>{if(r.url().endsWith('/api/jobs')&&r.method()==='POST')inference++;});
  await context.route('**/api/session',async route=>{
   const response=await route.fetch(),json=await response.json();
   json.runtime={...json.runtime,gateway:true,model:false,ready:false};
   await route.fulfill({json});
  });
  await context.route('**/api/runtime',async route=>{
   const response=await route.fetch(),json=await response.json();
   await route.fulfill({json:{...json,gateway:true,model:false,ready:false}});
  });
  const base=process.env.BAC_TEST_URL||'http://127.0.0.1:8082';
  await page.goto(base);
  await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.waitForFunction(async()=>{const s=await fetch('/api/state').then(r=>r.json());return s.preparation?.status==='done';},null,{polling:1000});
  const first=await page.evaluate(()=>fetch('/api/state').then(r=>r.json()).then(s=>s.preparation));
  assert.equal(first.payload.background,true);
  assert.deepEqual(first.payload.checks.map(c=>c.status),['ready','ready','ready','ready']);
  assert.equal(await page.locator('#studio-crew-form').count(),0,'No Plan a BaC click was needed');
  const second=await context.newPage();await second.goto(base);
  await second.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  await page.waitForTimeout(1800);
  assert.equal(await page.evaluate(()=>fetch('/api/state').then(r=>r.json()).then(s=>s.preparation.id)),first.id);
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();
  await page.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row[data-status=ready]').length===4);
  assert.equal(await page.locator('#studio-launch-event').isDisabled(),true,'A real mission still needs a model');
  const selected=await page.evaluate(async()=>{
   const session=await fetch('/api/session').then(r=>r.json());
   const post=(path,body)=>fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify(body)}).then(r=>r.json());
   const profile={name:'Scout',persona:'analyst',skills:['weather'],protection:'standard'};
   await post('onboard',profile);
   const agent=await post('agents',{...profile,name:'Pixel'});
   sessionStorage.setItem('bac-selected-agent',agent.agentId);
   return agent.agentId;
  });
  await page.reload();
  await page.waitForFunction(id=>window.BacStudio?.inspect().agentId===id,selected);
  await page.waitForFunction(async id=>{const s=await fetch('/api/state',{headers:{'X-BaC-Agent':id}}).then(r=>r.json());return s.preparation?.status==='done';},selected,{polling:1000});
  assert.equal(inference,0);
  assert.deepEqual(errors,[]);
  console.log('PASS: app-open crew warmup before hiring or model connection; reload/tab deduplication; saved agent restored before warmup; ready event form; inference remains gated. Fixture runtime.');
 }finally{await context.unrouteAll({behavior:'wait'});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

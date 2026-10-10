// Disposable fixture_scenarios.py; no real model or user workspaces.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];let posts=0,inference=0;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'){if(r.url().endsWith('/api/prepare-demo')){posts++;assert.equal(r.postDataJSON().background,true);}if(r.url().endsWith('/api/jobs'))inference++;}});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  const state=()=>page.evaluate(()=>fetch('/api/state',{headers:{'X-BaC-Scenario':'event-brief'}}).then(r=>r.json()));
  const post=(path,body)=>page.evaluate(async({path,body})=>{
   const s=await fetch('/api/session').then(r=>r.json());
   const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Scenario':'event-brief'},body:JSON.stringify(body)});
   const data=await r.json();if(!r.ok)throw Error(JSON.stringify(data));return data;
  },{path,body});
  const ready=async old=>{
   const deadline=Date.now()+22000;let s;
   do{s=await state();if(s.preparation?.valid&&s.preparation.status==='done'&&s.preparation.id!==old)break;await page.waitForTimeout(200);}while(Date.now()<deadline);
   assert.ok(s.preparation?.valid&&s.preparation.status==='done'&&s.preparation.id!==old,'Crew should prepare again without visiting Stage 3');
   assert.equal(s.preparation.payload.background,true);assert.equal(await page.locator('#studio-crew-form').count(),0);return s.preparation.id;
  };
  const first=await ready();assert.equal(posts,1);
  await post('settings/scenario-model',{provider:'auto'});
  assert.equal((await state()).preparation.valid,false);
  const second=await ready(first);assert.equal(posts,2,'Model change must rewarm without opening Stage 3');
  await post('bac-reset',{scope:'scenario'});
  assert.equal((await state()).preparation,null);
  const third=await ready(second);assert.equal(posts,3,'Reset must not leave startup cache permanently satisfied');
  const s=await state();assert.equal(s.scenarios.find(s=>s.id==='event-brief').hasWork,false,'Automatic warmup is not user work to reset');
  await page.waitForTimeout(12000);assert.equal(posts,3,'Ready crew only needs read-only checks');assert.equal((await state()).preparation.id,third);
  assert.equal(inference,0);assert.deepEqual(errors,[]);
  console.log('PASS: initial preparation, model invalidation, reset, no repeated ready writes, no inference; all while staying in Hiring. Fixture runtime.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

// Disposable fixture_scenarios.py only. No live runtime or user data.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const p=await b.newPage({viewport:{width:1500,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:18083');await p.waitForFunction(()=>window.BacStudio?.inspect().agentId);
  const api=(path,body)=>p.evaluate(async({path,body})=>{
   const s=await fetch('/api/session').then(r=>r.json());const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf,'X-BaC-Scenario':'event-brief'},...(body?{body:JSON.stringify(body)}:{})});
   if(!r.ok)throw Error(await r.text());return r.json();
  },{path,body});
  const prep=async()=> (await api('state?qa=1')).preparation;
  const wait=async fn=>{const until=Date.now()+30000;while(Date.now()<until){const v=await fn();if(v)return v;await p.waitForTimeout(150);}throw Error('Readiness timeout');};
  const first=await wait(async()=>{const v=await prep();return v?.valid&&v.status==='done'&&v;});
  // The form sees an older snapshot even though the server already finished.
  let stale=true,automatic=[];
  await p.route('**/api/state',async route=>{
   const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();
   if(stale&&state.scenario==='event-brief')state.preparation=null;
   await route.fulfill({response,json:state});
  });
  await p.route('**/api/prepare-demo',async route=>{automatic.push(route.request().postDataJSON());stale=false;await route.continue();});
  await p.locator('.world-room-map [data-world-scenario=event-brief]').click();await p.waitForFunction(()=>BacCampus.inspect().navigation.activeScenario==='event-brief'&&!BacCampus.inspect().navigation.travelling);
  await p.locator('#studio-room-action').click();
  await p.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row[data-status=ready]').length===4);
  assert(automatic.length>0);assert(automatic.every(v=>v.background===true),'Automatic form readiness must reuse background preparation');
  assert.equal((await prep()).id,first.id,'Stale form state must not recreate already prepared crew');
  await p.locator('#studio-dialog-close').click();await p.unroute('**/api/state');await p.unroute('**/api/prepare-demo');
  // A later partial preparation must not suppress warmup for missing members.
  await p.locator('.world-room-map [data-world-room=workshop]').click();
  const partial=await api('prepare-demo',{enabledRoles:[0,2]});
  await wait(async()=>{const v=await prep();return v?.id===partial.id&&v.status==='done';});
  const full=await wait(async()=>{const v=await prep();return v?.id!==partial.id&&v?.status==='done'&&v.payload.enabledRoles.length===4&&v;});
  assert(full.payload.background);assert.equal(await p.locator('#studio-dialog').evaluate(el=>el.open),false);assert.deepEqual(errors,[]);
  console.log('PASS: stale form snapshot reuses existing preparation; partial crew warms missing members from Hiring.');
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

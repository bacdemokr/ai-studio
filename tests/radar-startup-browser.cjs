// Use fixture_heartbeat.py with BAC_TEST_RADAR_DENIED=1. No real model or websites.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
  page.setDefaultTimeout(35000);page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:18088');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  const started=Date.now();
  await page.evaluate(async()=>{
   const session=await fetch('/api/session').then(r=>r.json());
   const response=await fetch('/api/onboard',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify({name:'Pixel',purpose:'Weather helper',skills:['weather','radar'],protection:'openshell'})});
   if(!response.ok)throw Error(await response.text());
  });
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Pixel');
  await page.evaluate(()=>BacStudio.setRoom('lounge'));
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  while(Date.now()-started<19000){
   const report=await page.evaluate(()=>fetch('/api/agent-policy').then(r=>r.json()));
   assert.deepEqual(report.pendingAccess,[]);assert.deepEqual(report.recentDenied,[]);
   assert.equal(await page.locator('#studio-agent-policy .policy-pending-badge').count(),0);
   assert.equal(await page.evaluate(()=>BacStudio.inspect().jobs.filter(job=>job.kind==='heartbeat').length),0);
   await page.waitForTimeout(750);
  }
  await page.waitForFunction(()=>BacStudio.inspect().jobs.some(job=>job.result?.systemNotice),null,{timeout:15000});
  const notice=await page.evaluate(()=>BacStudio.inspect().jobs.find(job=>job.result?.systemNotice));
  assert(notice.created*1000-started>=20000,'First request must not run during the initial 20 seconds');
  await page.waitForFunction(()=>document.querySelector('#studio-agent-policy .policy-pending-badge')?.textContent==='2');
  const report=await page.evaluate(()=>fetch('/api/agent-policy').then(r=>r.json()));
  assert.deepEqual(report.pendingAccess.map(item=>item.reason),['blocked','blocked']);
  assert.equal(await page.locator('#studio-prompt').isDisabled(),true);
  assert.match(await page.locator('#studio-radar-monitor').textContent(),/every 20 seconds/);
  assert.deepEqual(errors,[]);
  console.log('PASS: quiet onboarding with no premature policy badge; first attempted access after 20 seconds; two actual fixture denials become visible; mixed-skill chat stays disabled.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

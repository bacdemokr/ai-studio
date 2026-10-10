// Run only against fixture_session_cleanup.py. Own cookies, fake model, isolated data.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  for(const base of (process.env.BAC_TEST_URLS||'http://127.0.0.1:18089').split(',')){
   const context=await browser.newContext();
   const first=await context.newPage();
   const errors=[];
   for(const page of [first]){
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.waitForFunction(()=>BacStudio.inspect().agentId);
    await page.evaluate(async()=>{
     const s=await fetch('/api/session').then(r=>r.json());
     const r=await fetch('/api/onboard',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({name:'Session fixture',skills:['writer'],protection:'standard'})});
     if(!r.ok)throw Error('Fixture onboarding failed');
    });
    await page.reload();await page.waitForFunction(()=>BacStudio.inspect().agents?.length===1);
   }
   const firstId=await first.evaluate(()=>BacStudio.inspect().agentId);
   await first.reload();await first.waitForFunction(id=>BacStudio.inspect().agentId===id,firstId);
   // Finish any queued fixture work before simulating 60 minutes offline.
   await first.waitForTimeout(1500);
   await first.evaluate(()=>fetch('/api/fixture-expire',{method:'POST',body:'{}'}));
   await first.waitForFunction(id=>BacStudio.inspect().agentId&&BacStudio.inspect().agentId!==id,firstId,{timeout:15000});
   assert.equal(await first.evaluate(()=>BacStudio.inspect().agents.length),0);
   assert.deepEqual(errors,[]);
   await first.goto('about:blank');await context.close();
   console.log('PASS refresh preservation and expired-session recovery:',new URL(base).hostname);
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

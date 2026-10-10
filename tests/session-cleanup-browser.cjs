// Run only against fixture_session_cleanup.py. Own cookies, fake model, isolated data.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  for(const base of (process.env.BAC_TEST_URLS||'http://127.0.0.1:18089').split(',')){
   const contexts=await Promise.all([browser.newContext(),browser.newContext()]);
   const [first,second]=await Promise.all(contexts.map(c=>c.newPage()));
   const errors=[];
   for(const page of [first,second]){
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
   const secondId=await second.evaluate(()=>BacStudio.inspect().agentId);
   assert.notEqual(firstId,secondId);
   await first.reload();await first.waitForFunction(id=>BacStudio.inspect().agentId===id,firstId);
   // Finish any queued fixture work before simulating 10 minutes offline.
   await first.waitForTimeout(1500);
   await first.evaluate(()=>fetch('/api/fixture-expire',{method:'POST',body:'{}'}));
   await first.waitForFunction(id=>BacStudio.inspect().agentId&&BacStudio.inspect().agentId!==id,firstId,{timeout:15000});
   assert.equal(await first.evaluate(()=>BacStudio.inspect().agents.length),0);
   assert.equal(await second.evaluate(()=>BacStudio.inspect().agentId),secondId);
   assert.equal(await second.evaluate(()=>BacStudio.inspect().agents.length),1);
   assert.deepEqual(errors,[]);
   for(const context of contexts)await context.close();
   console.log('PASS refresh preservation, expired-session recovery and other-browser isolation:',new URL(base).hostname);
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

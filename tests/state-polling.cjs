const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/agent_documents_fixture.py'],{encoding:'utf8'}));
 const state=fixture.state;state.runtime={ready:false,model:false,gateway:true};
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let etag='"first"',unchanged=0,changed=0;
  await page.route('**/api/session',r=>r.fulfill({json:state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:state.runtime}));
  await page.route('**/api/state',r=>{
   if(r.request().headers()['if-none-match']===etag){unchanged++;return r.fulfill({status:304,headers:{ETag:etag},body:''});}
   changed++;return r.fulfill({json:state,headers:{ETag:etag}});
  });
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.waitForTimeout(3200);assert(unchanged>0);assert.equal(changed,1);
  await page.evaluate(()=>{window.pollMutations=0;new MutationObserver(records=>window.pollMutations+=records.length).observe(document.getElementById('studio-agent-name'),{childList:true,subtree:true,characterData:true});});
  await page.waitForTimeout(3200);assert.equal(await page.evaluate(()=>pollMutations),0);
  state.profile.name='Updated Scout';state.agents[0].name='Updated Scout';etag='"second"';
  await page.waitForFunction(()=>document.getElementById('studio-agent-name').textContent==='Updated Scout');
  assert.equal(changed,2);assert((await page.evaluate(()=>pollMutations))>0);
  assert.equal(await page.locator('#bac-playground').count(),0);
  await page.locator('#studio-agent-name').focus();await page.waitForTimeout(2000);assert(await page.locator('#studio-agent-name').evaluate(e=>e===document.activeElement));
  assert.deepEqual(errors,[]);
  console.log('PASS: unchanged state skips full payload and DOM rebuild, updates appear on next poll, keyboard focus survives, retired samples absent.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

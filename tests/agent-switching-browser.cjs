// Run against tests/fixture_heartbeat.py, never a real demo workspace.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
const deferred=()=>{let resolve;const promise=new Promise(done=>resolve=done);return {promise,resolve};};
async function seen(gate,label){
 let timer;
 try{await Promise.race([gate.promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Timed out waiting for '+label)),8000);})]);}
 finally{clearTimeout(timer);}
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:18087');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  const owners=await page.evaluate(async()=>{
   const session=await (await fetch('/api/session')).json();
   async function post(path,data){
    const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw Error(result.error);return result;
   }
   const profile=name=>({name,skills:['writer'],protection:'standard'});
   await post('onboard',profile('Switch A'));
   return [session.agentId,(await post('agents',profile('Switch B'))).agentId,(await post('agents',profile('Switch C'))).agentId];
  });
  const [a,b,c]=owners;
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().agents?.length===3);
  await page.evaluate(()=>BacStudio.setRoom('lounge'));
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const click=owner=>page.locator('[data-agent-key="'+owner+'"]').evaluate(node=>node.click());
  const selected=owner=>page.waitForFunction(key=>BacStudio.inspect().agentId===key,owner);
  for(const [owner,draft] of [[a,'A draft'],[b,'B draft'],[c,'C draft']]){
   await click(owner);await selected(owner);await page.locator('#studio-prompt').fill(draft);
  }
  await click(a);await selected(a);

  // Hold B's read while C opens, then deliver the older B response.
  let stateGate=deferred(),stateSeen=deferred(),heldState=false;
  await page.route('**/api/state',async route=>{
   if(!heldState&&route.request().headers()['x-bac-agent']===b){
    heldState=true;stateSeen.resolve();await stateGate.promise;
   }
   await route.continue();
  });
  await click(b);await seen(stateSeen,'first B state request');await click(c);await selected(c);
  assert.equal(await page.locator('#studio-prompt').inputValue(),'C draft');
  let lateResponse=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/state'&&response.request().headers()['x-bac-agent']===b);
  stateGate.resolve();await lateResponse;await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),c);
  assert.equal(await page.locator('#studio-prompt').inputValue(),'C draft');

  // Re-selecting the displayed agent cancels a pending selection.
  await click(a);await selected(a);heldState=false;stateGate=deferred();stateSeen=deferred();
  await click(b);await seen(stateSeen,'second B state request');await click(a);
  lateResponse=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/state'&&response.request().headers()['x-bac-agent']===b);
  stateGate.resolve();await lateResponse;await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),a);
  assert.equal(await page.locator('#studio-prompt').inputValue(),'A draft');
  await page.unroute('**/api/state');

  // Save A's message slowly. Retain the last click (B), then switch without
  // another click; the request and response still belong to A.
  const writeGate=deferred(),writeSeen=deferred();let writeOwner;
  await page.route('**/api/jobs',async route=>{
   if(route.request().method()==='POST'){
    writeOwner=route.request().headers()['x-bac-agent'];writeSeen.resolve();await writeGate.promise;
   }
   await route.continue();
  });
  await page.locator('#studio-prompt').fill('Switch ownership test');
  await page.evaluate(()=>document.querySelector('#studio-chat').requestSubmit());
  await seen(writeSeen,'chat save');await click(c);await click(b);await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().agentId),a);
  assert.equal(await page.locator('#studio-alert').isVisible(),false);
  assert.equal(writeOwner,a);writeGate.resolve();await selected(b);
  assert.equal(await page.locator('#studio-prompt').inputValue(),'B draft');
  assert.equal(await page.evaluate(()=>BacStudio.inspect().jobs.filter(job=>job.kind==='chat').length),0);
  await click(a);await selected(a);
  await page.waitForFunction(()=>BacStudio.inspect().jobs.some(job=>job.kind==='chat'&&job.status==='done'));
  const chats=await page.evaluate(()=>BacStudio.inspect().jobs.filter(job=>job.kind==='chat'));
  assert.equal(chats.length,1);assert.equal(chats[0].payload.prompt,'Switch ownership test');
  assert.equal(await page.locator('#studio-prompt').inputValue(),'');
  await click(c);await selected(c);
  assert.equal(await page.locator('#studio-prompt').inputValue(),'C draft');
  assert.equal(await page.locator('#studio-alert').isVisible(),false);
  assert.deepEqual(errors,[]);
  console.log('PASS: browser rapid switching, canceled selection, delayed save with automatic selection, isolated conversations and drafts. Model responses simulated.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

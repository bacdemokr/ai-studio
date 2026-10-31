// Disposable fixture_personal_models.py only; no real model or OpenShell calls.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:18336');
  await page.waitForFunction(()=>BacStudio.inspect().runtime.personalModels);
  const workshop=async name=>{
   await page.locator('.world-room-map [data-world-room=workshop]').click();
   await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-name').fill(name);await page.getByRole('button',{name:'Programmer',exact:true}).click();
  };
  await workshop('First');const start=Date.now();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='loading');
  await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='walking');
  await page.waitForFunction(()=>!BacCampus.inspect().arrival&&!document.querySelector('#studio-onboarding').inert,null,{timeout:18000});
  const normalArrivalMs=Date.now()-start;
  assert(normalArrivalMs>=6500,'Normal arrival must keep its full loading/walking animation');
  const first=await page.evaluate(()=>BacStudio.inspect().agentId);
  await workshop('Second');await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacCampus.inspect().arrival?.phase==='loading');
  const selectionStart=Date.now();
  await page.locator('[data-agent-key="'+first+'"]').evaluate(node=>node.click());
  await page.waitForFunction(key=>BacStudio.inspect().agentId===key&&!BacCampus.inspect().arrival&&!document.querySelector('#studio-onboarding').inert,first);
  const selectionMs=Date.now()-selectionStart;
  assert(selectionMs<1500,'Explicit selection must not wait for the remaining 7-second animation');
  assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,2);

  let running=true;const polls=[];
  await page.route('**/api/state',async route=>{
   polls.push(Date.now());const headers={...route.request().headers()};delete headers['if-none-match'];
   const response=await route.fetch({headers}),state=await response.json();
   state.jobs=[{id:'latency-fixture',kind:'chat',created:Date.now()/1000-5,due:0,status:running?'running':'done',payload:{prompt:'Fixture request'},events:[],result:running?{}:{answer:'Ready now'}}];
   await route.fulfill({response,json:state});
  });
  await page.evaluate(()=>BacStudio.refresh());polls.length=0;
  await page.waitForTimeout(3100);
  assert(polls.length>=3&&polls.length<=6,'Active work uses bounded fast polling');
  const activeIntervals=polls.slice(1).map((t,i)=>t-polls[i]);
  const completionStart=Date.now();running=false;
  await page.waitForFunction(()=>document.querySelector('#studio-conversation').textContent.includes('Ready now'));
  const completionMs=Date.now()-completionStart;assert(completionMs<1500);
  await page.waitForTimeout(8200); // Late policy evidence keeps the completion tail fast.
  polls.length=0;await page.waitForTimeout(7300);
  assert(polls.length>=2&&polls.length<=3,'Idle polling must slow down');
  const idleIntervals=polls.slice(1).map((t,i)=>t-polls[i]);
  await page.unroute('**/api/state');

  // Exercise the actual render loop with twelve seated visitors.
  await page.evaluate(async()=>{
   const session=await(await fetch('/api/session')).json();
   for(let i=2;i<12;i++){
    const r=await fetch('/api/agents',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify({name:'Fixture '+i,skills:['writer'],protection:'standard'})});
    if(!r.ok)throw Error('Fixture hire failed');
   }
   await BacStudio.refresh();
  });
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.waitForFunction(()=>BacCampus.inspect().visitorTravel.length===12&&BacCampus.inspect().visitorTravel.every(v=>v.phase==='seated'));
  await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForTimeout(300);
  await page.evaluate(()=>{
   window.labelMutations=0;window.labelObserver=new MutationObserver(ms=>{for(const m of ms)if(m.target.matches?.('.campus-agent-label small'))labelMutations++;});
   labelObserver.observe(document.querySelector('#campus-viewport'),{subtree:true,childList:true});
  });
  await page.waitForTimeout(5000);
  const labelMutations=await page.evaluate(()=>{labelObserver.disconnect();return window.labelMutations;});
  assert.equal(labelMutations,0,'Unchanged labels must not be rewritten each frame');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({fixture:true,normalArrivalMs,selectionMs,activeIntervals,idleIntervals,completionMs,labelMutations,errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

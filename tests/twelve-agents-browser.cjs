const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
 const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args:['--enable-unsafe-swiftshader']});
 try {
  const page = await browser.newPage({viewport:{width:1500,height:1100}}), errors=[];
  page.on('pageerror', error => errors.push(error.message));
  const writes=new Set();
  page.on('request',r=>{if(r.method()==='POST')writes.add(r);});
  page.on('requestfinished',r=>writes.delete(r));page.on('requestfailed',r=>writes.delete(r));
  async function waitForWrites(){
   const deadline=Date.now()+5000;
   while(writes.size&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20));
   assert.equal(writes.size,0,'Automatic preparation save should finish before selecting another agent');
  }
  await page.goto(process.env.BASE_URL || 'http://127.0.0.1:8092');
  await page.waitForFunction(() => window.BacStudio?.inspect().runtime.testFixture);
  const owners = await page.evaluate(async () => {
   const session = await (await fetch('/api/session')).json();
   async function post(path, data) {
    const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw new Error(result.error);return result;
   }
   const profile=i=>({name:'Capacity '+String(i+1).padStart(2,'0'), skills:['writer'], protection:i%2?'standard':'openshell'});
   await post('onboard',profile(0));
   const ids=[session.agentId];
   for(let i=1;i<12;i++)ids.push((await post('agents',profile(i))).agentId);
   return ids;
  });
  await page.reload();
  await page.waitForFunction(()=>BacStudio.inspect().agents?.length===12);
  await page.evaluate(()=>BacStudio.setRoom('lounge'));
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('[data-agent-key]').count(),12);
  assert.equal(await page.evaluate(()=>BacCampus.inspect().residents.length),12);
  // Exercise every rendered agent and its selected state over real HTTP.
  for(const owner of owners){
   await waitForWrites();
   await page.locator('[data-agent-key="'+owner+'"]').evaluate(node=>node.click());
   await page.waitForFunction(key=>BacStudio.inspect().agentId===key,owner);
  }
  await page.locator('#studio-prompt').fill('Say hello using your own name.');
  await page.evaluate(()=>document.querySelector('#studio-chat').requestSubmit(document.querySelector('#studio-send-all')));
  await page.waitForFunction(()=>document.querySelectorAll('[data-compare-row]').length===12);
  await page.waitForFunction(()=>[...document.querySelectorAll('.compare-status')].every(node=>['done','error'].includes(node.textContent)),null,{timeout:45000});
  const rows=await page.locator('[data-compare-row]').evaluateAll(nodes=>nodes.map(n=>({status:n.querySelector('.compare-status').textContent,answer:n.querySelector('.compare-answer').textContent})));
  assert.deepEqual(rows.map(r=>r.status),Array(12).fill('done'),'Ask all must eventually reach all twelve agents without quota failures');
  for(const [index,row] of rows.entries())assert(row.answer.includes(owners[index]),'No reply crosses agent identities');
  await page.screenshot({path:'/tmp/bac-twelve-agents-comparison.png',fullPage:true});
  // Selecting the first and last agents must show their own saved conversations.
  for(const owner of [owners[0],owners[11]]){
   await waitForWrites();
   await page.locator('[data-agent-key="'+owner+'"]').evaluate(node=>node.click());
   await page.waitForFunction(key=>BacStudio.inspect().agentId===key,owner);
   const state=await page.evaluate(()=>BacStudio.inspect());
   assert.equal(state.jobs.filter(j=>j.kind==='chat').length,1);
   assert(state.jobs[0].result.answer.includes(owner));
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: twelve real HTTP agent records, twelve rendered residents, agent switching, Ask all queue backpressure and isolated conversations. Native/model responses simulated.');
 } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});

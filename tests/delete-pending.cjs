const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',['-B','-c',`
import sys,json
sys.path[:0]=['scripts','tests']
from test_agent_deletion import DeletionTests
c=DeletionTests();c.setUp()
try:
 c.studio.enqueue(c.scout,{'kind':'reminder','prompt':'Later','delay':60})
 states=[c.studio.state(c.scout)]
 c.studio.executing_owners={c.scout}
 result=c.studio.delete_agent(c.scout,{'name':'Scout'})
 states.append(c.studio.state(c.scout))
 survivor=c.studio.state(c.owner)
 c.studio.executing_owners=set();c.studio.finish_pending_deletions()
 states.append(c.studio.state(c.owner))
 for s in states+[survivor]:s.update(csrf='test',runtime={'ready':False,'model':False,'gateway':True})
 print(json.dumps({'states':states,'survivor':survivor,'result':result}))
finally:c.tearDown()
`],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let phase=0,deletes=0,polls=0;
  await page.route('**/api/session',r=>r.fulfill({json:fixture.states[phase]}));
  await page.route('**/api/state',r=>{
   if(phase===1)polls++;
   const other=r.request().headers()['x-bac-agent']===fixture.survivor.agentId;
   return r.fulfill({json:phase===1&&other?fixture.survivor:fixture.states[phase]});
  });
  await page.route('**/api/runtime',r=>r.fulfill({json:fixture.states[0].runtime}));
  await page.route('**/api/delete-agent',r=>{deletes++;assert.equal(r.request().postDataJSON().name,'Scout');phase=1;return r.fulfill({json:fixture.result});});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-delete-agent').click();
  assert.equal(await page.getByText('Scout still has work in progress.',{exact:true}).count(),0);
  assert(await page.locator('#studio-delete-confirm').isVisible());
  await page.locator('#studio-delete-cancel').click();assert.equal(deletes,0);
  await page.locator('#studio-delete-agent').click();await page.locator('#studio-delete-confirm').click();
  await page.waitForFunction(()=>document.querySelector('.studio-delete-progress')?.textContent.includes('You can use another agent'));
  assert(await page.locator('#studio-delete-agent').isDisabled());
  await page.locator('[data-agent-key="'+fixture.survivor.agentId+'"]').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Jinny');
  assert.equal(phase,1,'navigation must work before cleanup finishes');
  assert.equal((await page.evaluate(()=>BacStudio.inspect().agents)).length,2,'pending deletion remains visible');
  phase=2;
  await page.waitForFunction(()=>document.querySelector('#studio-alert')?.textContent.includes('Scout was deleted'));
  assert.equal(await page.evaluate(()=>BacStudio.inspect().profile.name),'Jinny','completion must not change the user selection');
  assert.equal(deletes,1);assert(polls>=1);assert.equal(await page.locator('[data-resident="'+fixture.result.agentId+'"]').count(),0);
  assert.deepEqual(errors,[]);console.log('PASS: pending deletion preserves cancel, fences duplicate requests, releases navigation before cleanup, and preserves the selected survivor on completion.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

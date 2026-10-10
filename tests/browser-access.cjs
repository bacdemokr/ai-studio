// Only fixture_session_cleanup.py: isolated data and a fake model.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 const base=process.env.BAC_TEST_URL||'http://127.0.0.1:18089';
 const remote=process.env.BAC_TEST_LAN_URL||base;
 const contexts=await Promise.all([browser.newContext(),browser.newContext()]);
 const [first,second]=await Promise.all(contexts.map(c=>c.newPage()));
 const errors=[];
 const ready=page=>page.waitForFunction(()=>window.BacStudio?.inspect().agentId&&!document.querySelector('#agent-campus').dataset.boot);
 const blocked=page=>page.waitForFunction(()=>document.querySelector('#agent-campus')?.dataset.boot==='blocked');
 const counts=async()=>await (await contexts[1].request.get(base+'/api/fixture-counts')).json();
 try{
  for(const page of [first,second])page.on('pageerror',e=>errors.push(e.message));
  await first.goto(base);await ready(first);
  const owner=await first.evaluate(()=>BacStudio.inspect().agentId);
  await first.waitForTimeout(1500);
  const before=await counts();
  await second.goto(remote);await blocked(second);
  assert.match(await second.locator('.studio-boot-status').innerText(),/already open/);
  assert.equal(await second.evaluate(()=>BacStudio.inspect().agentId),'');
  assert.deepEqual(await counts(),before,'blocked browser must not create a participant or teams');
  await first.reload();await ready(first);
  assert.equal(await first.evaluate(()=>BacStudio.inspect().agentId),owner);
  const tab=await contexts[0].newPage();tab.on('pageerror',e=>errors.push(e.message));
  await tab.goto(base);await ready(tab);
  assert.equal(await tab.evaluate(()=>BacStudio.inspect().agentId),owner,'same browser must share the original agents');
  await first.goto('about:blank');
  await second.getByRole('button',{name:'Try again',exact:true}).click();await blocked(second);
  await tab.goto('about:blank');await tab.close();
  await second.getByRole('button',{name:'Try again',exact:true}).click();await ready(second);
  assert.notEqual(await second.evaluate(()=>BacStudio.inspect().agentId),owner);
  // Simulate a lost connection exceeding the admission grace without waiting
  // or changing the independent 60-minute data-retention window.
  await contexts[1].setOffline(true);
  await contexts[0].request.post(base+'/api/fixture-disconnect',{data:{}});
  await first.goto(base);await ready(first);
  assert.equal(await first.evaluate(()=>BacStudio.inspect().agentId),owner);
  await contexts[1].setOffline(false);await blocked(second);
  assert.deepEqual(errors,[]);
  await first.screenshot({path:process.env.BAC_TEST_READY_SCREENSHOT||'/tmp/bac-browser-admission-ready.png'});
  await second.screenshot({path:process.env.BAC_TEST_BLOCKED_SCREENSHOT||'/tmp/bac-browser-admission-blocked.png'});
  await first.goto('about:blank');
  console.log('PASS localhost/LAN exclusion, no duplicate teams, shared tabs, refresh, close, disconnect and stale-browser recovery');
 }finally{
  for(const context of contexts)await context.close();
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});

const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));let inferenceRequests=0;
  page.on('request',r=>{if(r.url().endsWith('/api/jobs')&&r.method()==='POST')inferenceRequests++;});
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('#studio-room-action').click();await page.locator('#studio-demo-preparation').waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('#studio-demo-preparation .demo-ready-row[data-status=ready]').length===4);
  await page.waitForFunction(()=>!document.querySelector('#studio-launch-event').disabled);
  assert.equal(inferenceRequests,0);assert.equal(await page.locator('.demo-ready-row[data-status=ready]').count(),4);
  assert.equal(await page.locator('[name=crewRole][value="0"]').isDisabled(),true);
  assert.ok((await page.locator('#studio-crew-form').innerText()).includes('Alex'));
  assert.ok(!/[↗]/.test(await page.locator('.studio-team-actions').innerText()));
  await page.screenshot({path:'/private/tmp/bac-demo-ready.png'});
  await page.close();
  const fixture=JSON.parse(execFileSync('python3',[__dirname+'/roundtable_fixture.py'],{encoding:'utf8'}));
  const state=fixture.state,job=state.jobs.find(j=>j.kind==='crew'),member=job.payload.roundtable.members[1];
  const unchanged=JSON.stringify(job.payload.outputs);job.payload.roundtable.replies[member.key]={status:'error',error:'Fixture runtime preparation failed.'};
  const reactions=await browser.newPage({viewport:{width:1600,height:1050}});reactions.on('pageerror',e=>errors.push(e.message));
  await reactions.route('**/api/session',r=>r.fulfill({json:state}));await reactions.route('**/api/state',r=>r.fulfill({json:state}));
  await reactions.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
  let retries=0;
  await reactions.route('**/api/retry-reaction',r=>{
   assert.deepEqual(r.request().postDataJSON(),{id:job.id,member:member.key});retries++;
   job.payload.roundtable.replies[member.key]={status:'done',answer:'My own short reaction after recovery.'};job.events.push({title:'Reaction retry finished'});
   return r.fulfill({json:{id:job.id,member:member.key}});
  });
  await reactions.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8083');await reactions.waitForFunction(()=>window.BacStudio);
  await reactions.locator('.world-room-map [data-world-room=mission]').click();await reactions.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const retry=reactions.locator('#studio-crew-conversation [data-retry-reaction]');await retry.waitFor();assert.equal(await retry.count(),1);await retry.click();
  await reactions.locator('#studio-crew-conversation').getByText('My own short reaction after recovery.',{exact:true}).waitFor();assert.equal(retries,1);assert.equal(await retry.count(),0);assert.equal(JSON.stringify(job.payload.outputs),unchanged);
  assert.deepEqual(errors,[]);console.log('PASS: actual preparation API, no inference during preparation, required Captain, readiness-gated launch, one failed reaction retry, other outputs preserved. Explicit fixture model.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

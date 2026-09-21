const assert=require('node:assert/strict'),{chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/roundtable_fixture.py'],{encoding:'utf8'}));
 const state=structuredClone(fixture.state),job=state.jobs.find(j=>j.kind==='crew'),completed=structuredClone(job);
 job.status='running';job.payload.outputs={};job.payload.activeStages=[0];job.payload.stage=0;job.payload.handoffs={};job.payload.roundtable.status='invited';job.payload.roundtable.replies={};
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/session',r=>r.fulfill({json:state}));await page.route('**/api/state',r=>r.fulfill({json:state}));
  await page.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.waitForFunction(()=>BacCampus.inspect().roundtable?.guests.length===4&&BacCampus.inspect().roundtable.guests.every(g=>g.seated),null,{timeout:20000});
  const inspect=()=>page.evaluate(()=>BacCampus.inspect().roundtable);
  let info=await inspect();
  assert.ok(info.tableWidth<8,'Four guests get a compact table');
  assert.deepEqual(info.guests.map(g=>g.key),fixture.keys);assert.equal(info.speaker,'');
  assert.equal(info.guests[1].appearance.body,'claw');assert.equal(info.guests[0].appearance.body,'round');
  assert.ok(info.guests.every(g=>g.facing===Math.PI));assert.equal(new Set(info.guests.map(g=>g.position[2].toFixed(4))).size,1);
  assert.ok((await page.evaluate(()=>BacCampus.inspect().residents)).every(r=>r.atRoundtable&&!r.visible));
  await page.waitForTimeout(6500);assert.equal(await page.locator('.roundtable-bubble:visible').count(),0,'No idle chatter');
  // A rerun while still seated must not recreate an entrance.
  const seats=info.guests.map(g=>[g.key,g.position,g.seat]);
  job.id='second-roundtable';job.status='queued';await page.evaluate(()=>BacStudio.refresh());
  info=await inspect();assert.deepEqual(info.guests.map(g=>[g.key,g.position,g.seat]),seats);assert.ok(info.guests.every(g=>g.seated));
  job.status='running';await page.evaluate(()=>BacStudio.refresh());
  // The table accommodates twelve on the SAME side, with matching screen-facing orientation.
  job.id='twelve-person-roundtable';const first=job.payload.roundtable.members[0];
  for(let i=4;i<12;i++)job.payload.roundtable.members.push({...first,key:'extra-'+i,name:'Guest '+i});
  await page.evaluate(()=>BacStudio.refresh());info=await inspect();assert.ok(info.guests.slice(0,4).every(g=>g.seated));
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.every(g=>g.seated),null,{timeout:20000});
  info=await inspect();assert.equal(info.guests.length,12);assert.ok(info.tableWidth>19,'Table expands for twelve guests');assert.equal(new Set(info.guests.map(g=>g.position[2].toFixed(4))).size,1);
  assert.ok(info.guests.every(g=>g.facing===Math.PI));
  for(const a of info.guests)for(const b of info.guests)if(a!==b)assert.ok(Math.abs(a.position[0]-b.position[0])>=1.74);
  await page.locator('#studio-focus').click();await page.waitForTimeout(500);await page.screenshot({path:'/private/tmp/bac-twelve-seat-table.png'});await page.keyboard.press('Escape');
  // Actual replies get a compact acknowledgement. Each exit finishes before the next starts.
  Object.assign(job,structuredClone(completed));job.id='four-person-finale';job.status='running';job.payload.roundtable.replies={};
  await page.evaluate(()=>BacStudio.refresh());
  assert.ok((await inspect()).tableWidth<8,'Table shrinks again for four guests');
  job.payload.roundtable=structuredClone(completed.payload.roundtable);job.status='done';await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>!!BacCampus.inspect().roundtable.speaker);
  const bubble=page.locator('.roundtable-guest[data-speaking=true]');
  assert.equal(await bubble.locator('.roundtable-bubble').innerText(),'Opinion submitted.');
  assert.ok((await bubble.boundingBox()).width<=180);assert.ok((await bubble.boundingBox()).height<90,JSON.stringify(await bubble.evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),font:getComputedStyle(e).font,html:e.outerHTML}))));
  // Clicking names opens history without replaying the full opinion on the scene.
  await bubble.click();await page.locator('#studio-crew-conversation [data-roundtable-reply]').first().waitFor();
  assert.equal(await page.locator('#studio-crew-conversation [data-roundtable-reply]').count(),4);
  await page.screenshot({path:'/private/tmp/bac-roundtable-normal.png'});
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.some(g=>g.phase==='returning'));
  info=await inspect();assert.equal(info.guests.filter(g=>g.phase==='returning').length,1);assert.equal(info.speaker,'');
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests[0].phase==='returned',null,{timeout:10000});
  assert.ok((await page.evaluate(()=>BacCampus.inspect().residents)).find(r=>r.key===fixture.keys[0]).visible);
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests[1].phase==='submitted');
  info=await inspect();assert.ok(info.guests.slice(2).every(g=>g.phase==='seated'));
  // Reduced motion still serializes acknowledgements, but skips the walks.
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.every(g=>g.phase==='returned'),null,{timeout:15000});
  assert.equal(await page.locator('.roundtable-guest:visible').count(),0);
  assert.ok((await page.evaluate(()=>BacCampus.inspect().residents)).every(r=>!r.atRoundtable&&r.visible));
  // Repeated polling and room changes do not bring the guests back or repeat their speeches.
  await page.evaluate(()=>BacStudio.refresh());
  await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('.world-resident:visible').count(),4);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.ok((await inspect()).guests.every(g=>g.phase==='returned'));
  // Completed reload is quiet and residents remain in the Lounge.
  await page.reload();await page.waitForFunction(()=>window.BacStudio);
  await page.waitForFunction(()=>BacCampus.inspect().roundtable?.guests.length===4);
  assert.ok((await inspect()).guests.every(g=>g.phase==='returned'));assert.equal((await inspect()).speaker,'');
  // A genuinely new mission invites them again. Failed/cancelled replies never say 'submitted'.
  job.id='cancelled-finale';job.status='running';job.payload.roundtable.replies={};await page.evaluate(()=>BacStudio.refresh());
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.every(g=>g.seated));
  job.status='cancelled';await page.evaluate(()=>BacStudio.refresh());
  await page.waitForFunction(()=>BacCampus.inspect().roundtable.guests.every(g=>g.phase==='returned'));
  assert.deepEqual((await inspect()).spoken,[]);assert.deepEqual(errors,[]);
  const artifact=await browser.newPage({viewport:{width:1280,height:1000}});await artifact.setContent(fixture.page);
  assert.equal(await artifact.locator('.reflection').count(),4);await artifact.setViewportSize({width:390,height:844});
  assert.equal(await artifact.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  console.log('PASS: no idle speeches; twelve screen-facing seats; compact acknowledgements; sequential return; history preserved; reruns, reload, cancellation and reduced motion.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});

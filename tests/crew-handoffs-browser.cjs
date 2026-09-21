const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const state=JSON.parse(require('node:child_process').execFileSync('python3',[require('node:path').join(__dirname,'crew_handoff_fixture.py')],{encoding:'utf8'}));
 const job=state.jobs.find(j=>j.kind==='crew');
 // Start with dispatch recorded but no specialist answer yet.
 const completed=structuredClone(job);
 job.status='running';delete job.payload.outputs['1'];delete job.payload.outputs['2'];delete job.payload.outputs['3'];delete job.payload.handoffs['3'];
 const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const p=await b.newPage({viewport:{width:1600,height:1050}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.route('**/api/session',r=>r.fulfill({json:state}));await p.route('**/api/state',r=>r.fulfill({json:state}));
  await p.goto('http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio);
  await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await p.locator('[data-campus-agent="0"]').click();
  const log=p.locator('#studio-crew-conversation');
  await log.locator('[data-assignment-to="1"]').waitFor();assert.match(await log.innerText(),/App workflow → Dylan · Task assigned/);
  assert.equal(await log.locator('[data-assignment-to="3"]').count(),0);
  await p.locator('[data-campus-agent="1"]').click();assert.match(await log.innerText(),/App workflow → Dylan · Task received/);assert.match(await log.innerText(),/Working on the assigned task/);
  await log.locator('.chat-handoff > details > summary').click();assert.match(await log.innerText(),/Design one concrete/);
  await p.screenshot({path:'/private/tmp/crew-handoff-ui.png'});
  Object.assign(job,completed);await p.waitForTimeout(2000);
  assert.match(await log.innerText(),/Fixture deliverable/);
  await p.reload();await p.waitForFunction(()=>window.BacStudio);await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await p.locator('[data-campus-agent="3"]').click();
  assert.match(await log.innerText(),/App workflow → Morgan · Task received/);
  assert.deepEqual(errors,[]);console.log('PASS: browser shows dispatch before result, received task and inputs, later dispatch only when recorded, and history after reload.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

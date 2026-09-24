const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/showcase_fixture.py'],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>window.setInterval=()=>0);
 await page.route('**/api/session',r=>r.fulfill({json:fixture.state}));await page.route('**/api/state',r=>r.fulfill({json:fixture.state}));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>window.BacStudio);
 await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.evaluate(()=>{
  window.agents=[{key:'weather',name:'Scout',persona:'guide',purpose:'Check weather.',skills:['weather'],pending:1,latestMission:{id:'weather-1',status:'running'}},{key:'writer',name:'Jinny',persona:'maker',purpose:'Write clearly.',skills:['writer'],pending:1,latestMission:{id:'writer-1',status:'running'}}];
  BacCampus.setCollection(agents,'writer');
 });
 assert.equal(await page.locator('[data-resident][data-speaking=true]').count(),0);
 // Selected / focused characters must still show their answer, even with motion disabled.
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.locator('[data-resident=writer]').focus();
 await page.evaluate(()=>{
  agents[1].pending=0;agents[1].latestMission={id:'writer-1',status:'done',answerPreview:'**Clear copy beats another meeting.** Here is your [revised headline](https://example.com): Build something useful.'};
  BacCampus.setCollection(agents,'writer');
 });
 await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.key==='writer'&&r.speech));
 let residents=await page.evaluate(()=>BacCampus.inspect().residents);
 assert.equal(residents.find(r=>r.key==='writer').speech,'Clear copy beats another meeting. Here is your revised headline: Build something useful.');
 assert.equal(residents.find(r=>r.key==='weather').speech,null);
 // Polling does not restart or replace the message.
 await page.evaluate(()=>BacCampus.setCollection(agents,'writer'));
 assert.equal((await page.evaluate(()=>BacCampus.inspect().residents)).find(r=>r.key==='writer').speech,residents.find(r=>r.key==='writer').speech);
 await page.screenshot({path:'/private/tmp/bac-lounge-reply.png'});
 // A new query silences the previous answer. Failure is not announced as success.
 await page.evaluate(()=>{agents[1].pending=1;agents[1].latestMission={id:'writer-2',status:'running'};BacCampus.setCollection(agents,'writer');});
 assert.equal(await page.locator('[data-resident][data-speaking=true]').count(),0);
 await page.evaluate(()=>{agents[1].pending=0;agents[1].latestMission={id:'writer-2',status:'error'};BacCampus.setCollection(agents,'writer');});
 await page.waitForTimeout(400);assert.equal(await page.locator('[data-resident][data-speaking=true]').count(),0);
 // Another agent's reply uses its own text; long Markdown stays bounded and safe.
 await page.evaluate(()=>{agents[0].pending=0;agents[0].latestMission={id:'weather-1',status:'done',answerPreview:'### Forecast\nIt is **14°C** in Zurich. Bring a light jacket. '+ 'A longer detail about the weather. '.repeat(30)+'<img src=x onerror=alert(1)>'};BacCampus.setCollection(agents,'writer');});
 await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.key==='weather'&&r.speech));
 const answer=(await page.evaluate(()=>BacCampus.inspect().residents)).find(r=>r.key==='weather').speech;
 assert.match(answer,/14°C.*Zurich.*jacket/);assert.ok(answer.length<=240);assert.equal(await page.locator('.world-resident-speech img').count(),0);
 await page.locator('#campus-viewport').focus();await page.mouse.move(1,1);
 await page.waitForFunction(()=>!BacCampus.inspect().residents.some(r=>r.speech),null,{timeout:20000});
 await page.evaluate(()=>BacCampus.setCollection(agents,'writer'));await page.waitForTimeout(500);
 assert.equal(await page.locator('[data-resident][data-speaking=true]').count(),0,'Completed replies are shown once, not replayed on polling');
 await page.evaluate(()=>{agents[0].pending=1;agents[0].activity={kind:'preparation',label:'Preparing demo'};BacCampus.setCollection(agents,'writer');});
 assert.equal(await page.locator('[data-resident=weather] small').innerText(),'Busy');
 await page.evaluate(()=>{agents[0].pending=0;agents[0].activity=null;BacCampus.setCollection(agents,'writer');});
 await page.waitForTimeout(3500);
 assert.equal(await page.locator('[data-resident][data-speaking=true]').count(),0,'Readiness finishing must not replay a previous answer');
 // Deletion immediately silences an existing reply, including a focused bubble.
 await page.evaluate(()=>{agents[1].latestMission={id:'writer-3',status:'done',answerPreview:'A final draft is ready.'};BacCampus.setCollection(agents,'writer');});
 await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.key==='writer'&&r.speech));
 await page.locator('[data-resident=writer]').focus();
 await page.evaluate(()=>{agents[1].deleting=true;agents[1].deletionWaiting=true;BacCampus.setCollection(agents,'writer');});
 assert.equal(await page.locator('[data-resident=writer]').getAttribute('data-speaking'),'false');
 assert.equal(await page.locator('[data-resident=writer] small').innerText(),'Deleting…');
 assert.equal((await page.evaluate(()=>BacCampus.inspect().residents)).find(r=>r.key==='writer').speech,null);
 // A late success arriving while deleting or paused cannot start speech again.
 await page.evaluate(()=>{agents[1].latestMission={id:'writer-4',status:'done',answerPreview:'This late answer must stay quiet.'};BacCampus.setCollection(agents,'writer');});
 await page.waitForTimeout(3500);
 assert.equal(await page.locator('[data-resident=writer]').getAttribute('data-speaking'),'false');
 await page.evaluate(()=>{agents[1].deletionWaiting=false;BacCampus.setCollection(agents,'writer');});
 assert.equal(await page.locator('[data-resident=writer] small').innerText(),'Cleanup paused');
 assert.equal(await page.locator('[data-resident=writer]').getAttribute('data-speaking'),'false');
 // Other residents still announce their own successful replies.
 await page.evaluate(()=>{agents[0].latestMission={id:'weather-2',status:'done',answerPreview:'Other agents can still speak.'};BacCampus.setCollection(agents,'writer');});
 await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.key==='weather'&&r.speech==='Other agents can still speak.'));
 assert.deepEqual(errors,[]);console.log('PASS: reply excerpts, quiet deletion/paused cleanup, suppression of late answers, and unaffected surviving speakers.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

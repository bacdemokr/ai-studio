const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8098');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  await page.evaluate(()=>{
   window.noraDispatches=0;let flying=false;
   function sample(){const d=BacCampus.inspect().captain.inFlight,next=d?.role===6&&d.kind==='assignment';if(next&&!flying)window.noraDispatches++;flying=next;requestAnimationFrame(sample);}requestAnimationFrame(sample);
  });
  await page.locator('#studio-crew-prompt').fill('/plan REVISION_QA Analyze the figures and independently review the total.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,6,4');
  await page.waitForFunction(()=>BacCampus.inspect().captain.assigned.includes(6),null,{timeout:35000});
  await page.waitForFunction(()=>document.querySelector('[data-plan-revision]')?.textContent.includes('Revising'),null,{timeout:25000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().selectedTeam),[0,6,4]);
  await page.waitForFunction(()=>window.noraDispatches===2&&BacCampus.inspect().captain.assigned.includes(6)&&BacCampus.inspect().activeRole===6,null,{timeout:8000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,4,6]);
  await page.locator('[data-surface="control"]').click();
  await page.locator('[data-revision-role="6"]').waitFor({state:'visible'});
  assert.match(await page.locator('[data-revision-role="6"]').innerText(),/Revising/);
  await page.waitForFunction(()=>document.querySelector('[data-after-revision]')?.textContent.includes('total is now correct'),null,{timeout:20000});
  const kinds=await page.locator('#studio-lanes [data-trace-kind]').evaluateAll(nodes=>nodes.map(n=>n.dataset.traceKind));
  assert.deepEqual(kinds,['user','plan','contribution','review','contribution','revision','revision-work','review','response']);
  await page.locator('[data-revision-role="6"] summary').click();
  assert.match(await page.locator('[data-revision-role="6"]').innerText(),/Ada corrected the total to 450/);
  await page.screenshot({path:'../../work/plan-revision-trace.png'});
  await page.locator('#studio-surface-close').click();
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  assert.match(await page.locator('[data-plan-revision]').innerText(),/One targeted revision/);
  await page.locator('[data-surface="control"]').click();
  assert.equal(await page.locator('[data-revision-request]').count(),1);
  assert.equal(await page.locator('[data-revision-role="6"]').count(),1);
  assert.deepEqual(errors,[]);
  console.log('PASS: existing Ada returns once, no newcomer, repeated paper dispatch, ordered trace and reload history.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

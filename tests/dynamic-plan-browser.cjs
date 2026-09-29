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
  assert.equal(await page.locator('[data-campus-agent]').count(),4);
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,1,2,3]);
  await page.locator('[data-campus-agent="0"]').click();
  const standby=page.locator('#studio-standby');
  await standby.locator('summary').click();
  assert.deepEqual(await standby.locator('[data-standby-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.standbyRole))),[4,5,6,7,8]);
  assert.equal(await page.locator('#studio-standby-count').innerText(),'5');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,1,2,3]);
  await page.screenshot({path:'../../work/standby-specialists-preview.png'});
  await page.locator('#studio-crew-prompt').fill('/plan CALCULATOR_QA Build and inspect a calculator.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('A combined proposal'),null,{timeout:30000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().selectedTeam),[0,2,5,4]);
  const homes=await page.evaluate(()=>BacCampus.inspect().crewHomes);
  assert.equal(homes[5][2],-3.5);
  await page.waitForFunction(()=>{const a=BacCampus.inspect().crewExchange;return a.every(r=>!r.phase)&&a.filter(r=>r.visible).map(r=>r.role).join()==='0,2,4,5';},null,{timeout:20000});
  assert.equal(await page.locator('[data-campus-agent]').count(),4);
  assert.deepEqual(await standby.locator('[data-standby-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.standbyRole))),[3,6,7,8]);
  assert.equal(await standby.getAttribute('open'),'');
  await standby.locator('summary').click();
  await page.locator('[data-surface="control"]').click();
  const control=page.locator('#studio-board');
  assert.deepEqual(await control.locator('[data-plan-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.planRole))),[0,2,5,4]);
  const programmerStep=control.locator('[data-plan-role="5"]');
  assert.match(await programmerStep.innerText(),/Casey’s assignment/);
  assert.match(await programmerStep.innerText(),/Expected result/);
  assert.match(await programmerStep.innerText(),/Deliver a usable calculator with clear controls/);
  await page.setViewportSize({width:1600,height:1300});
  await page.screenshot({path:'../../work/mission-control-preview.png'});
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.locator('#studio-surface').evaluate(node=>node.scrollWidth<=node.clientWidth+2));
  await page.locator('#studio-surface-close').click();
  await page.setViewportSize({width:1600,height:1050});
  await page.locator('[data-campus-agent="5"]').click();
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Programmer');
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Casey → Wade/);
  await page.locator('[data-preview-file]').first().click();
  await page.waitForFunction(()=>document.querySelector('#studio-app-frame')?.dataset.ready==='true');
  assert.match(await page.frameLocator('#studio-app-frame').locator('body').innerText(),/Calculator QA/);
  await page.keyboard.press('Escape');
  await page.locator('#studio-crew-prompt').fill('/plan COPY_QA Write and review a welcome paragraph.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>JSON.stringify(BacCampus.inspect().selectedTeam)==='[0,3,4]');
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.waitForFunction(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase),null,{timeout:20000});
  assert.equal((await page.evaluate(()=>BacCampus.inspect().crewExchange))[5].visible,false);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  // Loading saved conversations must never replay their team substitution.
  for(let poll=0;poll<8;poll++){
   const scene=await page.evaluate(()=>BacCampus.inspect());
   assert.deepEqual(scene.selectedTeam,[0,1,2,3]);
   assert.deepEqual(scene.crewExchange.filter(r=>r.visible).map(r=>r.role),[0,1,2,3]);
   assert.ok(scene.crewExchange.every(r=>!r.phase));
   await page.waitForTimeout(500);
  }
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  assert.equal(await page.locator('[data-campus-agent]').count(),4);
  assert.equal(await page.locator('#studio-crew-role').innerText(),'BaC Captain');
  await page.locator('[data-surface="control"]').click();
  assert.deepEqual(await control.locator('[data-plan-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.planRole))),[0,3,4]);
  await page.locator('#studio-board-shared').click();
  assert.equal(await page.locator('#studio-surface').isVisible(),false);
  await page.locator('#studio-crew-conversation summary').filter({hasText:'Riley · Contribution'}).last().click();
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Verified contribution from Riley/);
  await page.waitForFunction(()=>{const s=BacCampus.inspect();return s.crewExchange.every(r=>!r.phase)&&s.robots.every((p,i)=>!s.crewExchange[i].visible||Math.hypot(...p.map((v,j)=>v-s.crewHomes[i][j]))<.6);},null,{timeout:20000});
  await page.screenshot({path:'../../work/dynamic-plan-preview.png'});
  await page.locator('#studio-crew-prompt').fill('/plan DATA_UI_QA Compare this table and build a usable dashboard.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,6,7,5');
  await page.waitForFunction(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase),null,{timeout:20000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,5,6,7]);
  await page.locator('[data-campus-agent="6"]').click();
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Data analyst');
  // Reset and a new event return the original BaC team, with reserves offscreen.
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.evaluate(async()=>{const s=await(await fetch('/api/session')).json();await fetch('/api/bac-reset',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({scope:'bac'})});});
  await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().crewExchange?.filter(r=>r.visible).map(r=>r.role).join()==='0,1,2,3');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  await page.locator('#studio-crew-prompt').fill('/plan CALCULATOR_QA Build a calculator.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,2,5,4');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,2,4,5]);
  assert.ok(await page.evaluate(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase)));
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.locator('#studio-crew-prompt').fill('/plan RESEARCH_QA Compare public sources and review the findings.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,8,4');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,4,8]);
  await page.locator('[data-campus-agent="8"]').click();
  assert.equal(await page.locator('#studio-crew-name').innerText(),'Avery');
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Researcher');
  assert.equal(await page.locator('#studio-crew-policy').isVisible(),false);
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Verified contribution from Avery'));
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  for(const [task,team,notice] of [
   ['SOLO_QA Answer a simple question.',[0],'No additional agents needed'],
   ['UNSUPPORTED_QA Deploy to my private cloud.',[0],'Required expertise unavailable - no agents called'],
   ['SINGLE_QA Write a short greeting.',[0,3],'Enough to finish - no additional agents will be called'],
   ['EARLY_QA Research a simple topic.',[0,8],'Enough to finish - no additional agents will be called']
  ]){
   await page.locator('#studio-crew-prompt').fill('/plan '+task);
   await page.locator('#studio-crew-send').click();
   await page.waitForFunction(task=>{
    const turns=[...document.querySelectorAll('#studio-crew-conversation [data-collaboration-job]')];
    return turns.some(t=>t.textContent.includes(task))&&!document.querySelector('[data-crew-chat-stop]');
   },task);
   assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().selectedTeam),team);
   const turn=page.locator('#studio-crew-conversation [data-collaboration-job]').last();
   if(notice)assert.match(await turn.innerText(),new RegExp(notice));
   await page.locator('[data-surface="control"]').click();
   assert.equal(await control.locator('[data-plan-role]').count(),task.startsWith('EARLY_QA')?4:team.length);
   if(task.startsWith('EARLY_QA')){
    assert.match(await control.locator('[data-plan-role="3"]').innerText(),/Not called/);
    assert.match(await control.locator('[data-plan-role="4"]').innerText(),/Not called/);
   }
   if(task.startsWith('UNSUPPORTED_QA'))assert.match(await control.innerText(),/Capability unavailable/);
   await page.locator('#studio-surface-close').click();
   if(task.startsWith('EARLY_QA')){
    assert.equal(await turn.locator('summary').filter({hasText:'Contribution'}).count(),1);
    assert.match(await turn.innerText(),/Not called - no longer needed/);
    assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,8]);
   }
  }
  assert.deepEqual(errors,[]);
  console.log('Dynamic teams, desk movement, specialist history, preview and reload passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

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
  assert.equal(await page.locator('[data-campus-agent]').count(),1);
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0]);
  await page.locator('[data-campus-agent="0"]').click();
  assert.equal(await page.locator('#studio-crew-model').innerText(),'Nemotron 3 Ultra');
  assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/plan ');
  assert(await page.locator('#studio-crew-send').isDisabled());
  await page.locator('#studio-crew-prompt').fill('');await page.waitForTimeout(1200);
  assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'','cleared prefix must stay cleared');
  const standby=page.locator('#studio-standby');
  await standby.locator('summary').click();
  assert.deepEqual(await standby.locator('[data-standby-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.standbyRole))),[0,4,5,6,7,8]);
  assert.equal(await page.locator('#studio-standby-count').innerText(),'6');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0]);
  await page.screenshot({path:'/tmp/standby-specialists-preview.png'});
  await standby.locator('p').first().click();
  assert.equal(await standby.evaluate(node=>node.open),true);
  await page.locator('#studio-crew-prompt').click();
  assert.equal(await standby.evaluate(node=>node.open),false);
  await standby.locator('summary').click();
  await standby.locator('summary').press('Escape');
  assert.equal(await standby.evaluate(node=>node.open),false);
  await standby.locator('summary').click();
  await page.locator('[data-surface="control"]').click();
  assert.equal(await standby.evaluate(node=>node.open),false);
  assert.equal(await page.locator('#studio-surface').evaluate(node=>node.open),true);
  await page.locator('#studio-surface-close').click();

  await page.locator('#studio-crew-prompt').fill('/plan ASSEMBLY_QA Research AMD, build a webpage and review it.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,8,5,4');
  await page.waitForFunction(()=>{const s=BacCampus.inspect();return [8,5,4].every(i=>s.crewExchange[i].visible&&!s.crewExchange[i].phase);},null,{timeout:15000});
  await page.waitForFunction(()=>document.querySelector('.plan-live-activity')?.textContent.includes('example.com'));
  const progress=await page.locator('.plan-live-activity').innerText();
  assert(progress.includes('Scout')&&progress.includes('Completed')&&progress.includes('brief.md'));
  assert(!progress.includes('/private/')&&!progress.includes('private=hidden'));
  assert(progress.includes('Waiting for tool completion'));
  await page.waitForFunction(()=>[5,4].every(role=>document.querySelector('.campus-agent-label[data-crew-member=\"'+role+'\"] small')?.textContent.includes('Waiting for Casey')));
  const assembled=await page.evaluate(()=>BacCampus.inspect());
  assert.equal(assembled.activeRole,8);
  for(const role of [5,4]){
   assert(!assembled.captain.assigned.includes(role));
   assert(!assembled.captain.pending.some(d=>d.kind==='assignment'&&d.role===role));
   assert(Math.hypot(...assembled.robots[role].map((v,i)=>v-assembled.crewHomes[role][i]))<.12);
   assert.match(await page.locator('.campus-agent-label[data-crew-member="'+role+'"] small').innerText(),/Waiting for Casey/);
   assert.equal(await page.locator('.campus-agent-label[data-crew-member="'+role+'"] .crew-work-bubble').count(),0);
   assert.equal(await standby.locator('[data-standby-role="'+role+'"]').count(),1);
  }
  await page.screenshot({path:'/tmp/planned-team-waiting-preview.png'});
  await page.waitForFunction(()=>!document.querySelector('[data-crew-chat-stop]'),null,{timeout:30000});
  await page.locator('#studio-crew-prompt').fill('/plan CALCULATOR_QA Build and inspect a calculator.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>{const turn=[...document.querySelectorAll('#studio-crew-conversation [data-collaboration-job]')].at(-1);return turn?.textContent.includes('CALCULATOR_QA')&&turn.textContent.includes('A combined proposal')&&!document.querySelector('[data-crew-chat-stop]');},null,{timeout:30000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().selectedTeam),[0,6,5,4]);
  const homes=await page.evaluate(()=>BacCampus.inspect().crewHomes);
  assert.equal(homes[5][2],-3.5);
  await page.waitForFunction(()=>{const a=BacCampus.inspect().crewExchange;return a.every(r=>!r.phase)&&a.filter(r=>r.visible).map(r=>r.role).join()==='0,4,5,6';},null,{timeout:20000});
  assert.equal(await page.locator('[data-campus-agent]').count(),4);
  assert.deepEqual(await standby.locator('[data-standby-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.standbyRole))),[0,4,5,6,7,8]);
  assert.equal(await standby.getAttribute('open'),null);
  await standby.locator('summary').click();
  await page.locator('[data-surface="control"]').click();
  const control=page.locator('#studio-board');
  assert.deepEqual(await control.locator('[data-plan-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.planRole))),[0,6,5,4]);
  const programmerStep=control.locator('[data-plan-role="5"]');
  assert.match(await programmerStep.innerText(),/Casey’s assignment/);
  assert.match(await programmerStep.innerText(),/Expected result/);
  assert.match(await programmerStep.innerText(),/Deliver a usable calculator with clear controls/);
  const traceKinds=()=>control.locator('[data-trace-kind]').evaluateAll(nodes=>nodes.map(n=>n.dataset.traceKind));
  assert.deepEqual(await traceKinds(),['user','plan','contribution','review','contribution','review','contribution','review','response']);
  assert.equal(await control.locator('[data-trace-kind="user"] header small').innerText(),'00 · USER');
  assert.equal(await control.locator('[data-trace-kind="user"] .chat-prose').innerText(),'CALCULATOR_QA Build and inspect a calculator.');
  assert.equal(await control.locator('[data-trace-kind="plan"] header small').innerText(),'01 · PLAN');
  assert.equal(await control.locator('[data-trace-kind="plan"]').getByText('No additional agents will be called.',{exact:true}).count(),0);
  assert.deepEqual(await control.locator('[data-after-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.afterRole))),[6,5,4]);
  await programmerStep.locator('[data-trace-details] summary').click();
  assert.match(await programmerStep.innerText(),/Verified contribution from Cody/);
  await page.waitForTimeout(2200);
  assert.equal(await programmerStep.locator('[data-trace-details]').getAttribute('open'),'');
  await page.setViewportSize({width:1600,height:1300});
  await page.screenshot({path:'/tmp/mission-control-preview.png'});
  await page.locator('#studio-surface-close').click();
  await page.setViewportSize({width:1600,height:1050});
  await page.locator('[data-campus-agent="5"]').click();
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Programmer');
  assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'');
  assert.doesNotMatch(await page.locator('#studio-crew-prompt').getAttribute('placeholder'),/plan/);
  assert.equal(await page.locator('#studio-crew-prompt').getAttribute('data-plan-enabled'),'false');
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Casey → Cody/);
  await page.locator('[data-preview-file]').first().click();
  await page.waitForFunction(()=>document.querySelector('#studio-app-frame')?.dataset.ready==='true');
  assert.match(await page.frameLocator('#studio-app-frame').locator('body').innerText(),/Calculator QA/);
  await page.keyboard.press('Escape');
  await page.locator('[data-campus-agent="0"]').click();
  await page.locator('#studio-crew-prompt').fill('/plan COPY_QA Write and review a welcome paragraph.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>JSON.stringify(BacCampus.inspect().selectedTeam)==='[0,7,4]');
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.waitForFunction(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase),null,{timeout:20000});
  assert.equal((await page.evaluate(()=>BacCampus.inspect().crewExchange))[5].visible,false);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  // Restore the seated team without replaying entrance animation.
  for(let poll=0;poll<8;poll++){
   const scene=await page.evaluate(()=>BacCampus.inspect());
   assert.deepEqual(scene.selectedTeam,[0,7,4]);
   assert.deepEqual(scene.crewExchange.filter(r=>r.visible).map(r=>r.role),[0,4,7]);
   assert.ok(scene.crewExchange.every(r=>!r.phase));
   await page.waitForTimeout(500);
  }
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  assert.equal(await page.locator('[data-campus-agent]').count(),3);
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Team captain');
  await page.locator('[data-surface="control"]').click();
  assert.deepEqual(await control.locator('[data-plan-role]').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.planRole))),[0,7,4]);
  assert.deepEqual(await traceKinds(),['user','plan','contribution','review','contribution','review','response']);
  await page.locator('#studio-surface-close').click();
  assert.equal(await page.locator('#studio-surface').isVisible(),false);
  await page.locator('#studio-crew-conversation summary').filter({hasText:'Vera · Contribution'}).last().click();
  assert.match(await page.locator('#studio-crew-conversation').innerText(),/Verified contribution from Vera/);
  await page.waitForFunction(()=>{const s=BacCampus.inspect();return s.crewExchange.every(r=>!r.phase)&&s.robots.every((p,i)=>!s.crewExchange[i].visible||Math.hypot(...p.map((v,j)=>v-s.crewHomes[i][j]))<.6);},null,{timeout:20000});
  await page.screenshot({path:'/tmp/dynamic-plan-preview.png'});
  await page.locator('#studio-crew-prompt').fill('/plan DATA_UI_QA Compare this table and build a usable dashboard.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,6,7,5');
  await page.waitForFunction(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase),null,{timeout:20000});
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,5,6,7]);
  await page.locator('[data-campus-agent="6"]').click();
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Data analyst');
  // Reset clears the desks; only Casey remains.
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.evaluate(async()=>{const s=await(await fetch('/api/session')).json();await fetch('/api/bac-reset',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({scope:'bac'})});});
  await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().crewExchange?.filter(r=>r.visible).map(r=>r.role).join()==='0');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('.world-room-map [data-world-room=mission]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-campus-agent="0"]').click();
  await page.locator('#studio-crew-prompt').fill('/plan CALCULATOR_QA Build a calculator.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,6,5,4');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,4,5,6]);
  assert.ok(await page.evaluate(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase)));
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.locator('#studio-crew-prompt').fill('/plan RESEARCH_QA Compare public sources and review the findings.');
  await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>BacCampus.inspect().selectedTeam.join()==='0,8,4');
  assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,4,8]);
  await page.locator('[data-campus-agent="8"]').click();
  assert.equal(await page.locator('#studio-crew-name').innerText(),'Scout');
  assert.equal(await page.locator('#studio-crew-role').innerText(),'Web Researcher');
  assert.equal(await page.locator('#studio-crew-policy').isVisible(),false);
  await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Verified contribution from Scout'));
  await page.waitForFunction(()=>document.querySelectorAll('[data-crew-chat-stop]').length===0);
  await page.locator('[data-campus-agent="0"]').click();
  for(const [task,team,notice] of [
   ['SOLO_QA Answer a simple question.',[0],'No additional agents needed'],
   ['UNSUPPORTED_QA Deploy to my private cloud.',[0],'Required expertise unavailable - no agents called'],
   ['SINGLE_QA Write a short greeting.',[0,7],'Enough to finish - no additional agents will be called'],
   ['EARLY_QA Research a simple topic.',[0,8,7,4],'Enough to finish - no additional agents will be called'],
   ['PARTIAL_QA Build and deploy a dashboard.',[0,6,5,4],'Partial result - stopping here']
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
    assert.match(await control.locator('[data-plan-role="7"]').innerText(),/Not called/);
    assert.match(await control.locator('[data-plan-role="4"]').innerText(),/Not called/);
    assert.deepEqual(await traceKinds(),['user','plan','contribution','review','skipped','skipped','response']);
    assert.equal(await control.locator('[data-trace-kind="plan"]').getByText('The research answers the request; no additional agents are needed.',{exact:true}).count(),0);
    assert.equal(await control.locator('[data-trace-kind="review"]').count(),1);
    assert.match(await control.locator('[data-after-role="8"]').innerText(),/After Scout’s result/);
    await control.locator('[data-trace-details="output-8"] summary').click();
    assert.match(await control.locator('[data-plan-role="8"]').innerText(),/Verified contribution from Scout/);
    await page.screenshot({path:'/tmp/mission-control-trace-preview.png'});
   }
   if(task.startsWith('SOLO_QA')||task.startsWith('UNSUPPORTED_QA'))assert.deepEqual(await traceKinds(),['user','plan','response']);
   if(task.startsWith('UNSUPPORTED_QA'))assert.match(await control.innerText(),/Capability unavailable/);
   if(task.startsWith('PARTIAL_QA')){
    assert.match(await control.innerText(),/Partial result/);
    await control.locator('[data-trace-details="response"] summary').click();
    assert.match(await control.innerText(),/Public deployment/);
    assert.match(await turn.innerText(),/Partial result - what remains/);
    assert.match(await turn.innerText(),/Public deployment/);
    assert(await turn.locator('[data-preview-file]').count());
   }
   await page.locator('#studio-surface-close').click();
   if(task.startsWith('EARLY_QA')){
    assert.equal(await turn.locator('summary').filter({hasText:'Contribution'}).count(),1);
    assert.match(await turn.innerText(),/Not called - no longer needed/);
    const completion=turn.locator('.chat-agent [data-plan-completion]');
    assert.match(await completion.innerText(),/The research answers the request/);
    assert.match(await completion.innerText(),/Not called: Iris, Vera/);
    assert.match(await completion.innerText(),/Their planned work was not performed/);
    await page.waitForFunction(()=>BacCampus.inspect().crewExchange.every(r=>!r.phase));
    assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().crewExchange.filter(r=>r.visible).map(r=>r.role)),[0,4,7,8]);
    for(const role of [7,4]){
     assert.match(await page.locator('.campus-agent-label[data-crew-member="'+role+'"] small').innerText(),/Not started/);
     assert.equal(await page.locator('.campus-agent-label[data-crew-member="'+role+'"] .crew-work-bubble').count(),0);
    }
   }
  }
  assert.deepEqual(errors,[]);
  console.log('Dynamic teams, desk movement, specialist history, preview and reload passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

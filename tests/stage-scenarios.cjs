// Runs against an explicitly disposable fixture server, never the user's preview.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');await page.waitForFunction(()=>window.BacStudio&&window.BacCampus?.inspect().navigation?.overview);
 await page.locator('.world-campus-room[data-world-room=workshop]').click();await page.locator('#studio-name').fill('Scenario fixture guest');await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Scenario fixture guest'&&!BacCampus.inspect().arrival);
 await page.locator('.world-room-map [data-world-room=mission]').click();
 await page.locator('.world-scenario-label[data-world-scenario=plan]').waitFor({state:'visible'});
 const bounds=await page.locator('.world-scenario-label[data-world-scenario=plan]').boundingBox();assert(bounds.y+bounds.height<1000,'Floor labels must fit desktop viewport');assert.equal(await page.locator('#studio-scenarios').isVisible(),false);
 await page.screenshot({path:'/tmp/stage3-selector.png'});
 const choose=async id=>{await page.locator('.world-room-map [data-world-scenario="'+id+'"]').click();await page.locator('#studio-crew-passport').waitFor({state:'visible'});await page.waitForFunction(id=>BacCampus.inspect().navigation.activeScenario===id&&!BacCampus.inspect().navigation.travelling,id);};
 await choose('plan');assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/goal ');assert(await page.locator('#studio-bac-reset').isDisabled());
 await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>BacCampus.inspect().navigation.scenarioGallery&&!BacCampus.inspect().navigation.travelling);assert.equal(await page.locator('#studio-crew-passport').isVisible(),false);await choose('plan');
 await page.locator('#studio-crew-prompt').fill('plan hello');await page.locator('#studio-crew-send').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Fixture reply'));
 await page.locator('#studio-crew-prompt').fill('/plan keep this draft');
 await choose('event-brief');assert(await page.locator('#studio-bac-reset').isDisabled());assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'');assert(!await page.locator('#studio-crew-conversation').textContent().then(s=>s.includes('plan hello')));
 assert.equal(await page.locator('#studio-standby').isVisible(),false);
 await page.locator('#studio-crew-prompt').fill('event hello');await page.locator('#studio-crew-send').click();await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Fixture reply: event hello'));
 await page.locator('#studio-room-action').click();await page.waitForFunction(()=>document.querySelector('#studio-launch-event')&&!document.querySelector('#studio-launch-event').disabled);await page.locator('#studio-launch-event').click();
 await page.waitForFunction(()=>document.querySelector('#studio-crew-conversation').textContent.includes('Morgan'));
 await page.waitForFunction(()=>!document.querySelector('#studio-room-action').disabled,{},{timeout:30000});
 await page.locator('button[data-surface=deliverables]').click();await page.locator('#studio-event-package .event-showcase-preview').waitFor({state:'visible'});
  await page.screenshot({path:'/tmp/stage3-event-results.png'});await page.locator('#studio-surface-close').click();
 for(const role of [1,2,3,1]){
  await page.locator('button[data-surface=control]').click();
  await page.locator('#studio-lanes [data-role-output="'+role+'"]').click();
  await page.locator('#studio-event-package').waitFor({state:'visible'});
  await page.waitForFunction(role=>{
   const button=document.querySelector('#studio-event-package [data-contribution="'+role+'"]');
   const section=document.querySelector('#bac-result-'+role),body=document.querySelector('#studio-surface-body');
   const rect=section?.getBoundingClientRect(),bounds=body.getBoundingClientRect();
   return button?.getAttribute('aria-pressed')==='true'&&rect&&rect.top<bounds.bottom&&rect.bottom>bounds.top;
  },role);
  await page.locator('#studio-surface-close').click();
 }
 await page.locator('button[data-surface=usage]').click();
 assert.match(await page.locator('#studio-usage-time').innerText(),/Riley/);
 assert.match(await page.locator('#studio-usage-time').innerText(),/Morgan/);
 assert.match(await page.locator('#studio-usage-time').innerText(),/Agent time/);
 assert.match(await page.locator('#studio-usage-time').innerText(),/Turns/i);
 const usageBounds=await page.locator('#studio-surface').boundingBox();assert(usageBounds.x>=0&&usageBounds.y>=0&&usageBounds.x+usageBounds.width<=1500&&usageBounds.y+usageBounds.height<=1000);
 await page.screenshot({path:'/tmp/stage3-event-usage.png'});
 await page.locator('#studio-surface-close').click();
 await choose('plan');assert.equal(await page.locator('#studio-crew-prompt').inputValue(),'/plan keep this draft');assert((await page.locator('#studio-crew-conversation').textContent()).includes('plan hello'));assert(!(await page.locator('#studio-crew-conversation').textContent()).includes('event hello'));
 await choose('event-brief');assert((await page.locator('#studio-crew-conversation').textContent()).includes('event hello'));
 await page.locator('#studio-scenarios').evaluate(()=>{}); // Ensure switching didn't replace the selector node.
 await page.locator('button[data-world-room=lounge]').first().click();await page.locator('button[data-world-room=mission]').first().click();await page.locator('.world-scenario-label[data-world-scenario=plan]').waitFor({state:'visible'});
 assert.equal((await page.locator('.world-scenario-label[data-world-scenario=event-brief]').innerText()).replace(/\s+/g,' ').trim(),'03-1 Event Brief');
 await choose('event-brief');await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation?.overview);await page.locator('.world-room-map [data-world-room=mission]').click();await page.locator('.world-scenario-label[data-world-scenario=plan]').waitFor({state:'visible'});
 assert.equal((await page.locator('.world-scenario-label[data-world-scenario=event-brief]').innerText()).replace(/\s+/g,' ').trim(),'03-1 Event Brief');
 await choose('event-brief');assert((await page.locator('#studio-crew-conversation').textContent()).includes('event hello'));
 await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('[data-browse-file]').length>0);
 assert.equal(await page.locator('#studio-file-workspace').count(),0,'Files stay scoped to the selected agent');
 await page.locator('#studio-dialog').evaluate(d=>d.close());
 await page.locator('#studio-bac-reset').click();await page.locator('#studio-team-reset-confirm').click();
 await page.waitForFunction(()=>!document.querySelector('#studio-crew-conversation').textContent.includes('event hello'));
 await page.waitForFunction(()=>document.querySelector('#studio-bac-reset').disabled);
 await page.locator('#studio-config').click();await page.locator('[data-connection-tab=reset]').click();assert(await page.locator('#studio-settings-bac-reset').isDisabled());assert(!await page.locator('#studio-reset-all').isDisabled());await page.locator('#studio-dialog').evaluate(d=>d.close());
 await choose('plan');assert((await page.locator('#studio-crew-conversation').textContent()).includes('plan hello'));
 assert.deepEqual(errors,[]);console.log('PASS: separate 3D floors, map navigation, direct chat/history and draft isolation, complete Event Brief results, repeated entry, reload and scenario-only Reset.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

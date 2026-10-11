// Run against tests/fixture_studio.py; checks appearance/state, not LLM quality.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
 assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'workshop');
 assert.equal(await page.evaluate(()=>BacCampus.inspect().room),'workshop');
 const info=page.locator('[data-room-info=workshop]'),paper=page.locator('.world-room-paper:not(.world-term-paper)'),handle=paper.locator('.world-room-paper-drag'),resizer=paper.locator('.world-room-paper-resize');
 await info.click();assert(await paper.isVisible());assert(await resizer.isVisible());
 const before=await paper.boundingBox(),beforeFont=await paper.locator('.world-room-paper-intro').evaluate(node=>parseFloat(getComputedStyle(node).fontSize)),drag=await handle.boundingBox();
 await page.mouse.move(drag.x+drag.width/2,drag.y+drag.height/2);await page.mouse.down();await page.mouse.move(drag.x+drag.width/2-180,drag.y+drag.height/2+100,{steps:5});await page.mouse.up();
 const moved=await paper.boundingBox();assert(moved.x<before.x-100&&moved.y>before.y+50,'Quick guide must move by its heading');
 const resizeHandle=await resizer.boundingBox();await page.mouse.move(resizeHandle.x+resizeHandle.width/2,resizeHandle.y+resizeHandle.height/2);await page.mouse.down();await page.mouse.move(resizeHandle.x+resizeHandle.width/2+230,resizeHandle.y+resizeHandle.height/2+70,{steps:5});await page.mouse.up();await page.waitForTimeout(50);
 const resized=await paper.boundingBox(),viewport=await page.locator('#campus-viewport').boundingBox();
 assert(resized.width>moved.width+40&&resized.height>moved.height+30,'Quick guide must resize from its lower-right corner');
 assert(await paper.locator('.world-room-paper-intro').evaluate(node=>parseFloat(getComputedStyle(node).fontSize))>beforeFont,'Quick guide text must grow with the window');
 assert(resized.x>=viewport.x&&resized.y>=viewport.y&&resized.x+resized.width<=viewport.x+viewport.width&&resized.y+resized.height<=viewport.y+viewport.height,'Quick guide must remain inside the main view');
 await paper.locator('.world-room-paper-close').click();assert.equal(await paper.isVisible(),false);
 await page.locator('button[data-room=lounge]').click();assert.equal(await page.locator('[data-resident]').count(),0);assert(await page.locator('#studio-lounge-empty').isVisible());await page.locator('#studio-empty-create').click();
 const looks=[{body:'classic',color:'green',accessory:'antenna'},{body:'round',color:'cyan',accessory:'headset'},{body:'rover',color:'coral',accessory:'glasses'}],keys=[];
 for(let i=0;i<looks.length;i++){
   if(i)await page.locator('#studio-add-agent').click();
   const avatar=looks[i];await page.locator('#studio-body-picker [data-body='+avatar.body+']').click();await page.locator('#studio-name').fill(['Jinny','Orbit','Rover'][i]);
   await page.locator('[data-avatar-color='+avatar.color+']').click();await page.locator('#studio-accessory').selectOption(avatar.accessory);
   assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().draft.avatar),avatar);
   await page.locator('#studio-create').click();await page.waitForFunction(n=>BacStudio.inspect().agents.length===n,i+1);
   await page.waitForFunction(()=>BacStudio.inspect().room==='lounge');assert.deepEqual(await page.evaluate(()=>BacStudio.inspect().profile.avatar),avatar);
   assert.equal(await page.locator('[data-resident]').count(),i+1);assert.equal((await page.evaluate(()=>BacCampus.inspect().residents)).length,i+1);
   keys.push(await page.evaluate(()=>BacStudio.inspect().agentId));await page.locator('#studio-alert button').click();
 }
 await page.reload();await page.waitForFunction(()=>BacStudio.inspect().agents?.length===3);
 assert.equal(await page.evaluate(()=>BacStudio.inspect().room),'lounge');assert.deepEqual(await page.evaluate(()=>BacStudio.inspect().agents.map(a=>a.avatar)),looks);
 await page.locator('[data-resident="'+keys[0]+'"]').click();await page.waitForFunction(k=>BacStudio.inspect().agentId===k,keys[0]);
 await page.locator('#studio-edit-agent').click();await page.locator('[data-avatar-color=violet]').click();await page.locator('#studio-create').click();await page.waitForFunction(()=>BacStudio.inspect().profile.avatar.color==='violet');await page.locator('#studio-alert button').click();
 assert.equal((await page.evaluate(()=>BacCampus.inspect().residents))[0].avatar.color,'violet');
 // The whole collection grows; the mission room still has five role stations.
 await page.locator('button[data-room=mission]').click();assert.equal(await page.locator('[data-campus-agent]').count(),5);
 await page.locator('#studio-room-action').click();await page.locator('.event-crew-choice summary').click();await page.locator('[name=member1]').selectOption(keys[1]);await page.locator('[name=member2]').selectOption(keys[2]);await page.locator('#studio-launch-event').click();await page.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done');
 const roster=await page.evaluate(()=>BacStudio.inspect().jobs[0].payload.roster);
 assert.equal(roster[0].avatar.color,'violet');assert.deepEqual(roster[1].avatar,looks[1]);assert.deepEqual(roster[2].avatar,looks[2]);
 assert.deepEqual((await page.evaluate(()=>BacCampus.inspect().crewAvatars)).slice(0,3),roster.slice(0,3).map(m=>m.avatar));
 // Camera sizing and actual renderer survive native fullscreen in every room.
 for(const room of ['workshop','lounge','mission']){
   await page.locator('button[data-room='+room+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.waitForTimeout(180);
   const before=await page.locator('#campus-viewport').boundingBox();await page.locator('#campus-viewport').focus();await page.keyboard.press('Enter');await page.waitForFunction(()=>document.fullscreenElement?.id==='agent-campus');
   await page.waitForTimeout(150);const full=await page.locator('#campus-viewport').boundingBox();assert(full.width>=1599,'Fullscreen must fill width in '+room);
   await page.keyboard.press('Enter');await page.waitForFunction(()=>!document.fullscreenElement);await page.waitForTimeout(180);const after=await page.locator('#campus-viewport').boundingBox();assert(Math.abs(before.height-after.height)<1,room+' height drift');
 }
 await page.locator('button[data-room=workshop]').click();await page.locator('#studio-connection-setup').click();assert.match(await page.locator('#studio-dialog').innerText(),/OpenClaw/);await page.locator('#studio-dialog-close').click();
 for(const width of [736,390]){await page.setViewportSize({width,height:950});for(const room of ['workshop','lounge','mission']){await page.locator('button[data-room='+room+']').click();assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),room+' overflow');}}
 assert.deepEqual(errors,[]);console.log('PASS: three rooms, live avatar preview, growing 3D collection, persisted appearance, picking residents, edits, custom crew appearance, shared runtime status, and fullscreen restoration in each room.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

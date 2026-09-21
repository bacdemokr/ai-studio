const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
const p=await b.newPage({viewport:{width:1600,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:8082');await p.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await p.locator('#studio-focus').click();await p.locator('#studio-room-action').click();await p.locator('#studio-launch-event').click();
await p.waitForFunction(()=>BacCampus.inspect().captain.position[1]>.5);
assert.match(await p.locator('[data-crew-member="0"] .crew-work-bubble').innerText(),/Organizing/);
await p.screenshot({path:'../../work/captain-working.png'});
await p.waitForFunction(()=>BacStudio.inspect().jobs[0]?.payload.activeStages?.length===2);
assert.match(await p.locator('#campus-motion-status').innerText(),/Dylan \+ Alex.*parallel/);
for(const i of [1,2]){await p.locator('[data-crew-member="'+i+'"]').click();assert.equal(await p.locator('#studio-crew-status').innerText(),'WORKING ON THE BRIEF');}
assert.equal(await p.locator('.crew-work-bubble').count(),2);
assert.match(await p.locator('.crew-activity').innerText(),/Alex is working/);
assert.equal(await p.locator('.studio-work-group.is-parallel .studio-lane').count(),2);
await p.locator('[data-surface=control]').click();
assert.equal(await p.locator('#studio-surface #studio-event-package').count(),0);assert.equal(await p.locator('#studio-surface #studio-workspace').count(),0);
await p.screenshot({path:'../../work/parallel-board.png'});
await p.locator('#studio-surface-close').click();
await p.screenshot({path:'../../work/parallel-crew.png'});await p.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done',{},{timeout:30000});assert.equal(Object.keys((await p.evaluate(()=>BacStudio.inspect().jobs[0])).payload.outputs).length,6);await p.locator('[data-surface=deliverables]').click();assert.equal(await p.locator('#studio-surface-title').innerText(),'Results');assert.equal(await p.locator('#studio-surface #studio-board').count(),0);assert.equal(await p.locator('#studio-surface #studio-event-package').isVisible(),true);assert.equal(await p.locator('#studio-surface #studio-workspace').isVisible(),false);await p.locator('[data-package-tab=invitations]').click();assert.match(await p.locator('.event-invitation').innerText(),/Save .eml draft/);await p.locator('#studio-surface-close').click();assert.deepEqual(errors,[]);assert.equal(await p.locator('.crew-work-bubble').count(),0);await p.waitForFunction(()=>Math.abs(BacCampus.inspect().captain.position[1]-.05)<.1);console.log('PASS: both specialists shown working, two-character status, and six-role completion. Fixture inference.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

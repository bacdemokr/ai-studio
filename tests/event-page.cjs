const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
const p=await b.newPage({viewport:{width:1600,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('http://127.0.0.1:8082');await p.waitForFunction(()=>window.BacStudio&&BacStudio.inspect().runtime.testFixture);
await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await p.locator('#studio-focus').click();
assert.equal(await p.locator('[data-campus-agent]').count(),6);await p.locator('[data-crew-member="5"]').click();assert.equal(await p.locator('#studio-crew-name').innerText(),'Wade');assert.match(await p.locator('#studio-crew-skills').innerText(),/Event page studio/);
await p.screenshot({path:'../../work/wade-web-studio.png'});
await p.locator('#studio-room-action').click();await p.locator('#studio-launch-event').click();await p.waitForFunction(()=>BacStudio.inspect().jobs[0]?.status==='done',{},{timeout:30000});
const job=await p.evaluate(()=>BacStudio.inspect().jobs[0]);assert.equal(job.payload.roster.length,6);assert(job.payload.website.path.endsWith('-event-page.html'));assert.equal(Object.keys(job.payload.outputs).length,6);
await p.locator('[data-crew-member="5"]').click();await p.locator('[data-event-page-preview]').click();const f=p.frameLocator('#studio-app-frame');await f.locator('h1').waitFor();assert.equal(await f.locator('h1').innerText(),'Build something worth sharing.');assert.equal(await f.locator('.cards article').count(),3);await p.screenshot({path:'../../work/event-page-preview.png'});
assert.deepEqual(errors,[]);console.log('PASS: six-character scene, Wade selection, all handoffs, event page artifact and fullscreen HTML preview. Fixture LLM only.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

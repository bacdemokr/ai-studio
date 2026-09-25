const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(require('node:child_process').execFileSync('python3',[__dirname+'/showcase_fixture.py'],{encoding:'utf8'}));
 const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
 const p=await b.newPage({viewport:{width:1600,height:1050}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/api/session',r=>r.fulfill({json:fixture.state}));await p.route('**/api/state',r=>r.fulfill({json:fixture.state}));
 await p.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
 await p.goto('http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio);
 await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 console.log(await p.locator('[data-surface]').evaluateAll(es=>es.map(e=>[e.dataset.surface,e.textContent])));
 await p.locator('[data-surface=deliverables]').first().click();
 const frame=p.frameLocator('.event-showcase-preview');await frame.getByText('Your booth timetable',{exact:false}).waitFor();
 const capacity=fixture.state.jobs.find(j=>j.kind==='crew').payload.capacity;
 assert.ok(capacity.topics.length>0);
 assert.equal(await frame.locator('.demo').count(),capacity.topics.length);
 await frame.locator('td details summary').first().click();await frame.locator('td details[open]').first().waitFor();assert.match(await frame.locator('td details').first().innerText(),/attendees/);
 await p.screenshot({path:'/private/tmp/showcase-browser.png'});
 assert.deepEqual(errors,[]);console.log('PASS: live app renders showcase, demo cards, timetable details and downloads without JS errors.');
 const standalone=await b.newPage({viewport:{width:1280,height:1600}});await standalone.setContent(fixture.page);await standalone.screenshot({path:'/private/tmp/showcase-page.png',fullPage:true});
 await standalone.setViewportSize({width:390,height:844});await standalone.screenshot({path:'/private/tmp/showcase-mobile.png',fullPage:true});
 assert.equal(await standalone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.equal(await standalone.locator('.floor-booth').count(),fixture.state.jobs.find(j=>j.kind==='crew').payload.capacity.boothCount);
 console.log('PASS: mobile page fits viewport; booth map matches assignments.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

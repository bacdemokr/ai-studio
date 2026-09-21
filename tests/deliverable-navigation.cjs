const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const fixtures=process.env.BAC_RESULTS_FIXTURE?[process.env.BAC_RESULTS_FIXTURE]:['agent_led_fixture.py','researched_event_fixture.py','showcase_fixture.py'];
  for(const fixtureName of fixtures){
   const fixture=fixtureName.endsWith('.json')?JSON.parse(fs.readFileSync(fixtureName)):JSON.parse(execFileSync('python3',[__dirname+'/'+fixtureName],{encoding:'utf8'}));
   const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
   page.on('pageerror',error=>errors.push(error.message));
   for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
   await page.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
   await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
   await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('[data-surface=control]').first().click();
   await page.locator('[data-role-output="3"]').click();
   await page.locator('.event-showcase-preview[data-ready=true]').waitFor();
   await atSection('3');
   await page.locator('[data-contribution=all]').click();await atSection('all');
   const frame=page.frameLocator('.event-showcase-preview'),job=fixture.state.jobs.find(j=>j.kind==='crew');
   assert.equal(await page.locator('.result-overview').count(),0);
   assert.equal(await page.locator('.result-theme').count(),job.payload.capacity.topics.length);
   for(const t of job.payload.capacity.topics)assert((await page.locator('#bac-result-1').innerText()).includes(t.demo));
   async function atSection(id){
    await page.evaluate(()=>new Promise(resolve=>{const body=document.querySelector('#studio-surface-body');let last=-1,stable=0;function tick(){stable=body.scrollTop===last?stable+1:0;last=body.scrollTop;if(stable>=8)resolve();else requestAnimationFrame(tick);}requestAnimationFrame(tick);}));
    await page.waitForFunction(id=>{
     const body=document.querySelector('#studio-surface-body');if(id==='all')return body.scrollTop<2;
     const target=document.querySelector('#bac-result-'+id),nav=document.querySelector('.event-package-tabs');
     return target.getBoundingClientRect().top>=nav.getBoundingClientRect().bottom-2&&target.getBoundingClientRect().top<innerHeight-140;
    },id,{timeout:5000}).catch(async error=>{console.log('SECTION',id,await page.evaluate(id=>({scroll:document.querySelector('#studio-surface-body').scrollTop,nav:document.querySelector('.event-package-tabs').getBoundingClientRect().toJSON(),target:document.querySelector('#bac-result-'+id)?.getBoundingClientRect().toJSON()}),id));await page.screenshot({path:'/private/tmp/bac-results-failure.png'});throw error;});
   }
   for(const id of ['1','2','webpage','3','all']){
    await page.locator(`[data-contribution="${id}"]`).click();await atSection(id);
    assert.equal(await page.locator('.result-section').count(),4,'All contributions remain in the same page');
   }
   assert(!/[↑↓↗]/.test(await page.locator('#studio-event-package').innerText()));
   assert.equal(await frame.locator('script').count(),0);
   assert(!(await page.locator('.event-showcase-preview').getAttribute('sandbox')).includes('allow-scripts'));
   assert(await frame.locator('html').evaluate(e=>e.scrollHeight<=innerHeight+2),'No inner vertical scrolling');
   await frame.locator('html').evaluate(e=>e.dataset.retained='yes');
   await page.locator('[data-contribution="2"]').click();await atSection('2');
   // A newly arrived personal reaction must not reload the preview or jump the scroll.
   job.updated='reaction-update';job.payload.roundtable={...(job.payload.roundtable||{}),status:'done'};
   const before=await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop);
   await page.evaluate(()=>BacStudio.refresh());await atSection('2');
   assert.equal(await frame.locator('html').getAttribute('data-retained'),'yes');
   assert(Math.abs(await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop)-before)<3);
   // Wheel input over the webpage moves the outer Results panel.
   await page.locator('[data-contribution="webpage"]').click();await atSection('webpage');
   const box=await page.locator('.event-showcase-preview').boundingBox();await page.mouse.move(box.x+150,Math.max(260,box.y+160));
   const scrollBefore=await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop);await page.mouse.wheel(0,400);await page.waitForTimeout(350);
   assert(await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop)>scrollBefore+100,'Wheel must pass through the auto-height iframe');
   // The authored page's own anchor links use the same outer scroll.
   if(await frame.locator('a[href="#program"]').count()){
    await page.locator('[data-contribution="webpage"]').click();await atSection('webpage');
    await frame.locator('a[href="#program"]').first().click();await page.waitForTimeout(600);
    assert.equal(await frame.locator('html').evaluate(()=>scrollY),0);
   }
   const details=frame.locator('details').first();
   if(await details.count()){
    const was=await page.locator('.event-showcase-preview').evaluate(e=>e.clientHeight);
    await details.evaluate(e=>{e.open=!e.open;});await page.waitForTimeout(150);
    assert(await frame.locator('html').evaluate(e=>e.scrollHeight<=innerHeight+2));
    assert.notEqual(await page.locator('.event-showcase-preview').evaluate(e=>e.clientHeight),was,'Height follows expanded/collapsed details');
   }
   const download=page.waitForEvent('download');await page.locator('[data-package-download$="event-page.html"]').click();
   const saved=await download;assert.match(saved.suggestedFilename(),/event-page\.html$/);
   if(job.payload.website.authored)assert.equal(fs.readFileSync(await saved.path(),'utf8'),fixture.page,'Original HTML stays byte-for-byte intact');
   await page.locator('[data-contribution="1"]').click();await atSection('1');
   await page.screenshot({path:'/private/tmp/bac-results-contributions.png'});
   await page.setViewportSize({width:650,height:900});await page.waitForTimeout(150);
   assert(await frame.locator('html').evaluate(e=>e.scrollHeight<=innerHeight+2));
   assert(await page.locator('#studio-surface-body').evaluate(e=>e.scrollWidth<=e.clientWidth+2));
   await page.locator('[data-contribution="1"]').click();await atSection('1');
   await page.screenshot({path:'/private/tmp/bac-results-narrow.png'});
   await page.setViewportSize({width:1600,height:1050});
   await page.locator('#studio-surface-close').click();
   await page.locator('#studio-focus').click();
   await page.locator('[data-surface=control]').first().click();
   assert.equal(await page.locator('[data-role-output="0"]').count(),0);
   await page.locator('[data-role-output="2"]').click();await atSection('2');
   // Specialist results remain available if Morgan hasn't delivered a page yet.
   delete job.payload.website;delete job.payload.campaign;delete job.payload.outputs['3'];job.updated='page-pending';
   await page.evaluate(()=>BacStudio.refresh());
   await page.locator('[data-contribution="1"]').click();await atSection('1');
   assert.equal(await page.locator('.event-showcase-preview').count(),0);
   assert.equal(await page.locator('[data-contribution="2"]').count(),1);
   assert.equal(await page.locator('[data-contribution="3"]').count(),0);
   assert.deepEqual(errors,[]);await page.close();
   console.log('PASS: '+fixtureName+' — actual contributions, one vertical scroll, outer anchors/wheel, detail/resize height, polling stability, original download, pending page.');
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

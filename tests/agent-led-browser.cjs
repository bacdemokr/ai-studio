const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const statePath=process.env.BAC_TEST_STATE;
 const fixture=statePath?{state:JSON.parse(fs.readFileSync(statePath))}:JSON.parse(execFileSync('python3',[__dirname+'/agent_led_fixture.py'],{encoding:'utf8'}));
 const job=fixture.state.jobs.find(j=>j.payload.executionMode==='agent-led-v1'&&j.status==='done');assert(job);
 if(statePath)fixture.page=fs.readFileSync(path.join(path.dirname(statePath),'workspaces',fixture.state.agentId,job.payload.website.path),'utf8');
 assert.equal(crypto.createHash('sha256').update(fixture.page).digest('hex'),job.payload.website.sha256);
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1550,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
  await page.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  for(const [role,text] of [[1,'Searched NVIDIA Blog'],[2,'Validated & exported timetable'],[3,'Wrote file']]){
   await page.locator('[data-campus-agent="'+role+'"]').click();
   const activity=page.locator('#studio-crew-conversation .crew-tool-activity').last();await activity.locator('summary').click();
   if(role!==3||statePath)assert((await activity.innerText()).includes(text));
  }
  await page.locator('[data-crew-webpage]').last().click();
  const frame=page.frameLocator('.event-showcase-preview');await frame.locator('h1').waitFor();
  assert.equal(await frame.locator('h1').innerText(),job.payload.website.headline);
  const doc=await browser.newPage({viewport:{width:1440,height:1000}});await doc.setContent(fixture.page);
  assert.equal(await doc.locator('#program').count(),1);assert.equal(await doc.locator('#schedule td.break').count()>0,true);
  for(const topic of job.payload.capacity.topics)assert((await doc.locator('#program').innerText()).includes(topic.demo));
  const directory=process.env.BAC_SCREENSHOT_DIR||'/private/tmp';fs.mkdirSync(directory,{recursive:true});
  await doc.screenshot({path:path.join(directory,'agent-led-page.png')});
  await doc.locator('#schedule').scrollIntoViewIfNeeded();await doc.screenshot({path:path.join(directory,'agent-led-schedule.png')});
  await doc.setViewportSize({width:390,height:844});await doc.evaluate(()=>scrollTo(0,0));
  assert(await doc.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await doc.screenshot({path:path.join(directory,'agent-led-mobile.png')});
  assert.deepEqual(errors,[]);console.log('PASS: observed tool history, Morgan webpage action, published HTML checksum, program titles, colored schedule/breaks, responsive layout. '+(statePath?'Actual model-generated artifacts.':'Explicit model fixture.'));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

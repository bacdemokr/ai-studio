// Real WebGL and participant API, disposable fixture. Ambient life never calls the model.
const assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[],missions=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(jobs|mission|crew|decision)(?:\?|$)/.test(r.url()))missions.push(r.url());});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().runtime.testFixture);
  for(const [index,persona] of ['guide','maker','analyst'].entries()){
   if(index)await page.locator('#studio-add-agent').click();
   await page.locator('#studio-name').fill(['Jinny','Orbit','Scout'][index]);await page.locator('[data-persona='+persona+']').click();await page.locator('#studio-create').click();
   await page.waitForFunction(n=>BacStudio.inspect().agents?.length===n,index+1);await page.locator('#studio-alert button').click();
  }
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.mouse.move(1,1);
  await page.evaluate(()=>{
   window.loungeSamples=[];window.loungeSampler=setInterval(()=>loungeSamples.push(BacCampus.inspect().residents),150);
  });
  // Watch a full turn-taking cycle and real displacement, not just idle bobbing.
  await page.waitForFunction(()=>new Set(loungeSamples.flat().filter(r=>r.speech).map(r=>r.persona)).size===3,null,{timeout:90000});
  const samples=await page.evaluate(()=>{clearInterval(loungeSampler);return loungeSamples});
  for(const row of samples){
   assert(row.filter(r=>r.speech).length<=1,'Only one bubble should speak at a time');
   row.forEach((r,i)=>{
    assert(r.position[0]>=-7.11&&r.position[0]<=7.11&&r.position[2]>=-2.71&&r.position[2]<=4.41,'Resident leaves clear floor area');
    for(const other of row.slice(i+1))assert(Math.hypot(r.position[0]-other.position[0],r.position[2]-other.position[2])>=1.17,'Residents intersect');
   });
  }
  for(const r of samples[0])assert(samples.some(row=>{const n=row.find(n=>n.key===r.key);return Math.hypot(n.position[0]-r.position[0],n.position[2]-r.position[2])>.5}),r.persona+' should explore the lounge');
  const speech=Object.fromEntries(samples.flat().filter(r=>r.speech).map(r=>[r.persona,r.speech]));
  assert.match(speech.guide,/help|steps|simple|company|question|encouragement/i);assert.match(speech.maker,/build|making|different|idea|question|experiments/i);assert.match(speech.analyst,/closer|evidence|details|understand|perspective|careful/i);
  await page.locator('#campus-motion').click();
  const paused=await page.evaluate(()=>BacCampus.inspect().residents);await page.waitForTimeout(450);assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().residents),paused);
  // Reconciliation is a renderer contract: adding/editing/removing a neighbor preserves positions.
  const reconciled=await page.evaluate(()=>{
   const data=BacStudio.inspect(),old=BacCampus.inspect().residents,agents=structuredClone(data.agents);
   agents[0].avatar.color='violet';agents[0].persona='analyst';agents.push({...agents[0],key:'visual-newcomer',name:'Newcomer'});
   BacCampus.setCollection(agents,data.agentId);const added=BacCampus.inspect().residents;
   const active=added.find(r=>r.speech);if(active){agents.find(a=>a.key===active.key).pending=true;BacCampus.setCollection(agents,data.agentId);}
   const busy=BacCampus.inspect().residents;
   BacCampus.setCollection(data.agents,data.agentId);return {old,added,busy,restored:BacCampus.inspect().residents};
  });
  assert.equal(reconciled.added.length,4);assert.equal(reconciled.added[0].persona,'analyst');assert.equal(reconciled.added[0].avatar.color,'violet');
  for(const r of reconciled.old){assert.deepEqual(reconciled.added.find(n=>n.key===r.key).position,r.position);assert.deepEqual(reconciled.restored.find(n=>n.key===r.key).position,r.position);}
  assert(!reconciled.busy.some(r=>r.speech),'Busy residents stop ambient chatter');
  await page.locator('#campus-motion').click();
  const pick=page.locator('[data-resident]').first();await pick.focus();const frozen=(await page.evaluate(()=>BacCampus.inspect().residents))[0].position;await page.waitForTimeout(500);assert.deepEqual((await page.evaluate(()=>BacCampus.inspect().residents))[0].position,frozen,'Keyboard focus pins a moving agent');
  const identity=await pick.getAttribute('data-resident');await pick.click();await page.waitForFunction(key=>BacStudio.inspect().agentId===key,identity);await page.locator('#campus-viewport').focus();await page.mouse.move(1,1);
  await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.speech),null,{timeout:20000});
  await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement);await page.mouse.move(1,1);
  if(process.env.SCREENSHOT_DIR){fs.mkdirSync(process.env.SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,'lively-lounge.png')});}
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);
  await page.setViewportSize({width:390,height:950});await page.waitForTimeout(250);
  const viewport=await page.locator('#campus-viewport').boundingBox(),bubble=await page.locator('[data-resident][data-speaking=true]').boundingBox();
  assert(bubble&&bubble.x>=viewport.x&&bubble.x+bubble.width<=viewport.x+viewport.width&&bubble.y>=viewport.y&&bubble.y+bubble.height<viewport.y+viewport.height,'Mobile bubble stays in the scene');
  if(process.env.SCREENSHOT_DIR)await page.locator('#campus-viewport').screenshot({path:path.join(process.env.SCREENSHOT_DIR,'lively-lounge-mobile.png')});
  await page.emulateMedia({reducedMotion:'reduce'});const still=await page.evaluate(()=>BacCampus.inspect().residents);await page.waitForTimeout(450);assert.deepEqual(await page.evaluate(()=>BacCampus.inspect().residents),still);
  // Renderer-only capacity check. Offline page + explicit visual fixtures; no participant data.
  const crowd=await browser.newPage({viewport:{width:1280,height:950}});crowd.on('pageerror',e=>errors.push(e.message));
  await crowd.goto(pathToFileURL(path.resolve(__dirname,'../app/index.html')).href);await crowd.waitForFunction(()=>window.BacCampus?.inspect().room==='workshop');
  await crowd.locator('button[data-room=lounge]').click();await crowd.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await crowd.evaluate(()=>{
   const agents=Array.from({length:12},(_,i)=>({key:'crowd-'+i,name:i===0?'<img src=x onerror=alert(1)>':'Crowd '+i,persona:['guide','maker','analyst'][i%3],skills:['weather'],avatar:{body:['classic','round','rover'][i%3],color:['green','cyan','amber','coral','violet','ice'][i%6],accessory:['antenna','headset','glasses','cap'][i%4]}}));
   BacCampus.setCollection(agents,agents[0].key);window.crowdSamples=[];window.crowdSampler=setInterval(()=>crowdSamples.push(BacCampus.inspect().residents),150);
  });
  const started=await crowd.evaluate(()=>BacCampus.inspect().clock);await crowd.waitForFunction(start=>BacCampus.inspect().clock>start+8,started,{timeout:30000});
  const dense=await crowd.evaluate(()=>{clearInterval(crowdSampler);return crowdSamples});
  for(const row of dense){assert.equal(row.length,12);row.forEach((r,i)=>{for(const other of row.slice(i+1))assert(Math.hypot(r.position[0]-other.position[0],r.position[2]-other.position[2])>=1.17,'Crowded lounge intersects');});}
  assert.equal(await crowd.locator('.world-residents img').count(),0,'Names remain text');
  await crowd.close();
  assert.deepEqual(missions,[]);assert.deepEqual(errors,[]);
  console.log('PASS: free roaming, spacing/bounds including 12 residents, persona turn-taking, no model jobs, pause/reduced motion, stable reconciliation, busy suppression, safe names, keyboard/click selection, fullscreen and mobile bubbles.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

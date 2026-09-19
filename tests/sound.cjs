// Real Web Audio with an analyser tap; deterministic mission snapshots exercise cue routing.
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   const Native=window.AudioContext;window.soundProbe={contexts:0,peak:0};
   window.AudioContext=class extends Native{
    constructor(...args){super(...args);soundProbe.contexts++;this.tap=this.createAnalyser();this.tap.fftSize=512;this.tap.connect(this.destination);const buffer=new Float32Array(512);setInterval(()=>{this.tap.getFloatTimeDomainData(buffer);soundProbe.peak=Math.max(soundProbe.peak,...buffer.map(Math.abs));},8);}
    createGain(){const gain=super.createGain(),connect=gain.connect.bind(gain);gain.connect=(destination,...args)=>connect(destination===this.destination?this.tap:destination,...args);return gain;}
   };
  });
  await page.goto(pathToFileURL(path.resolve(__dirname,'../app/index.html')).href);await page.waitForFunction(()=>window.BacSound&&window.BacCampus);
  if(await page.locator('#studio-alert').isVisible())await page.locator('#studio-alert button').click();
  assert.equal(await page.evaluate(()=>soundProbe.contexts),0,'No context or autoplay before opt-in');
  assert.equal(await page.locator('#campus-sound-toggle').getAttribute('aria-pressed'),'false');
  await page.locator('button[data-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.evaluate(()=>BacCampus.setCollection([{key:'sound-guide',name:'Jinny',persona:'guide',skills:['weather'],avatar:{body:'classic',color:'green',accessory:'antenna'}}],'sound-guide'));
  await page.locator('#campus-viewport').scrollIntoViewIfNeeded();await page.mouse.move(1,1);
  await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.speech));assert.equal((await page.evaluate(()=>BacSound.inspect().history)).length,0,'Muted bubbles are silent');
  await page.locator('#campus-sound-toggle').click();await page.waitForFunction(()=>BacSound.inspect().ready);
  await page.waitForFunction(()=>soundProbe.peak>.001);assert((await page.evaluate(()=>soundProbe.peak))<.2,'Default gain stays gentle');
  await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement);await page.mouse.move(1,1);
  try{await page.waitForFunction(()=>BacSound.inspect().history.some(c=>c.kind==='guide'),null,{timeout:35000});}catch(error){console.error(await page.evaluate(()=>({audio:BacSound.inspect(),scene:BacCampus.inspect(),focus:document.activeElement.id})));throw error;}
  await page.locator('#campus-motion').click();assert.equal(await page.evaluate(()=>BacSound.inspect().activeVoices),0);
  for(const persona of ['maker','analyst']){await page.waitForTimeout(700);assert(await page.evaluate(p=>BacSound.speak(p),persona));}
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);
  await page.locator('button[data-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const state=async(status,stage=0)=>page.evaluate(({status,stage})=>BacSound.observeJobs('earcon-fixture',[{id:'crew-1',kind:'crew',status,payload:{stage}}]),{status,stage});
  await page.evaluate(()=>BacSound.observeJobs('earcon-fixture',[]));await state('queued');await page.waitForTimeout(700);await state('running');
  let last=await page.evaluate(()=>BacSound.inspect().history.at(-1).kind);assert.equal(last,'start');
  await page.waitForTimeout(700);await state('running',1);assert.equal(await page.evaluate(()=>BacSound.inspect().history.at(-1).kind),'handoff');
  const count=await page.evaluate(()=>BacSound.inspect().history.length);await page.waitForTimeout(700);await state('running',1);assert.equal(await page.evaluate(()=>BacSound.inspect().history.length),count,'Polling and renders do not repeat a cue');
  await state('waiting',3);assert.equal(await page.evaluate(()=>BacSound.inspect().history.at(-1).kind),'attention');
  await page.waitForTimeout(700);await state('done',5);assert.equal(await page.evaluate(()=>BacSound.inspect().history.at(-1).kind),'complete');
  await page.waitForTimeout(700);await page.evaluate(()=>BacSound.observeJobs('earcon-fixture',[{id:'crew-2',status:'error'}]));assert.equal(await page.evaluate(()=>BacSound.inspect().history.at(-1).kind),'error');
  // Mute immediately stops all voices, while state tracking continues without a replay queue.
  await page.locator('#campus-sound-toggle').click();assert.equal(await page.evaluate(()=>BacSound.inspect().activeVoices),0);
  const muted=await page.evaluate(()=>BacSound.inspect().history.length);await state('running');await state('done',5);assert.equal(await page.evaluate(()=>BacSound.inspect().history.length),muted);
  await page.locator('#campus-sound-toggle').click();await page.waitForFunction(()=>BacSound.inspect().history.at(-1).kind==='enable');
  const unmuted=await page.evaluate(()=>BacSound.inspect().history.length);await state('done',5);assert.equal(await page.evaluate(()=>BacSound.inspect().history.length),unmuted);
  await page.locator('.studio-sound-level summary').click();await page.locator('#campus-sound-volume').fill('0');await state('waiting',3);assert.equal(await page.evaluate(()=>BacSound.inspect().history.length),unmuted);await page.locator('#campus-sound-volume').fill('35');
  await page.locator('.studio-sound-level summary').click();
  // Audio stays controllable on the progress board, then inside native fullscreen.
  await page.locator('#studio-board-tab').click();assert(await page.locator('.studio-viewbar #campus-sound-toggle').isVisible());
  await page.waitForTimeout(700);await page.evaluate(()=>{soundProbe.peak=0;BacSound.observeJobs('board-fixture',[]);BacSound.observeJobs('board-fixture',[{id:'board-work',status:'running'}]);document.querySelector('.campus-layout').hidden=true;});await page.waitForFunction(()=>soundProbe.peak>.001,null,{timeout:2000});
  await page.locator('#campus-sound-toggle').click();assert.equal(await page.evaluate(()=>BacSound.inspect().enabled),false);await page.locator('#studio-campus-tab').click();
  await page.locator('#studio-focus').click();await page.waitForFunction(()=>document.fullscreenElement);assert(await page.locator('#campus-sound-toggle').isVisible());await page.locator('.studio-sound-level summary').click();assert(await page.locator('#campus-sound-volume').isVisible());await page.keyboard.press('Escape');assert(await page.evaluate(()=>!!document.fullscreenElement),'Escape closes volume before fullscreen');await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.fullscreenElement);
  for(const width of [1024,736,390]){
   await page.setViewportSize({width,height:950});await page.locator('button[data-room=workshop]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('.studio-sound-level summary').click();const panel=await page.locator('.studio-sound-panel').boundingBox();assert(panel.x>=0&&panel.x+panel.width<=width,'Volume panel fits '+width);assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'Sound controls do not widen '+width);await page.locator('.studio-sound-level summary').click();
  }
  await page.reload();await page.waitForFunction(()=>window.BacSound);assert.equal(await page.evaluate(()=>BacSound.inspect().volume),35);assert.equal(await page.evaluate(()=>BacSound.inspect().enabled),false);assert.equal(await page.evaluate(()=>soundProbe.contexts),0);
  await page.locator('button[data-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await page.locator('#campus-sound-toggle').click();await page.waitForFunction(()=>BacSound.inspect().ready);
  const beforeHidden=await page.evaluate(()=>BacSound.inspect().history.length);
  await page.evaluate(()=>{window.soundHidden=true;Object.defineProperty(document,'hidden',{configurable:true,get:()=>soundHidden});document.dispatchEvent(new Event('visibilitychange'));BacSound.observeJobs('hidden-fixture',[{id:'background',status:'running'}]);soundHidden=false;document.dispatchEvent(new Event('visibilitychange'));BacSound.observeJobs('hidden-fixture',[{id:'background',status:'done'}]);delete document.hidden;});
  assert.equal(await page.evaluate(()=>BacSound.inspect().history.length),beforeHidden,'Returning to the tab does not replay background work');
  const unsupported=await browser.newPage();await unsupported.addInitScript(()=>{window.AudioContext=undefined;window.webkitAudioContext=undefined;});await unsupported.goto(pathToFileURL(path.resolve(__dirname,'../app/index.html')).href);assert(await unsupported.locator('#campus-sound-toggle').isDisabled());await unsupported.close();
  assert.deepEqual(errors,[]);console.log('PASS: actual audible waveform, opt-in, persona earcons, task-state cues, deduplication, immediate mute, zero volume, saved settings, board/fullscreen/mobile controls, background suppression and unavailable-audio fallback.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

// Real browser/navigation and HTTP relay; isolated fixture, no external model calls.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18266),host=process.env.BAC_TEST_HOST||'127.0.0.1';let browser;
 const server=spawn('python3',['-B','tests/fixture_heartbeat.py'],{env:{...process.env,BAC_TEST_PORT:String(port),BAC_TEST_HOST:host},stdio:['ignore','pipe','pipe']});server.stderr.on('data',()=>{});
 try{
  await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);server.stdout.on('data',b=>{if(b.toString().includes('HEARTBEAT BROWSER FIXTURE')){clearTimeout(t);resolve();}});server.once('exit',c=>{clearTimeout(t);reject(Error('Fixture exited '+c));});});
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),errors=[],views=[],controls=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/api/heartbeat'))controls.push({agent:r.headers()['x-bac-agent'],...r.postDataJSON()});if(r.url().endsWith('/api/credential-session')&&r.method()==='POST')views.push(r.postDataJSON());});
  const navigate=async scenario=>{await page.locator('.world-room-map [data-world-scenario="'+scenario+'"]').click();await page.waitForFunction(s=>BacCampus.inspect().navigation.activeScenario===s&&!BacCampus.inspect().navigation.travelling,scenario);};
  const lounge=async()=>{await page.locator('.world-room-map [data-world-room="lounge"]').click();await page.waitForFunction(()=>BacStudio.inspect().room==='lounge'&&!BacCampus.inspect().navigation.travelling);};
  const state=key=>page.evaluate(async key=>fetch('/api/state',{headers:{'X-BaC-Agent':key}}).then(r=>r.json()),key);
  const waitState=(key,expected)=>page.waitForFunction(async({key,expected})=>{const s=await fetch('/api/state',{headers:{'X-BaC-Agent':key}}).then(r=>r.json());return s.techRadar?.state===expected;},{key,expected},{timeout:20000});
  const hire=async name=>{await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.locator('#studio-name').fill(name);await page.getByRole('button',{name:'Tech Radar',exact:true}).click();await page.locator('#studio-create').click();await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name&&BacStudio.inspect().agents.every(a=>!a.pending)&&!BacCampus.inspect().arrival,name);return page.evaluate(()=>BacStudio.inspect().agentId);};
  await page.goto('http://'+(host==='0.0.0.0'?(process.env.BAC_TEST_BROWSER_HOST||'127.0.0.1'):host)+':'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  const orbit=await hire('Orbit'),jinny=await hire('Jinny');
  await page.locator('#studio-radar-monitor button').click();await waitState(jinny,'paused');await waitState(orbit,'watching');
  await navigate('plan');await waitState(orbit,'paused in Open Task');assert.equal((await state(jinny)).techRadar.paused,true,JSON.stringify({orbit,jinny,controls,observed:(await state(jinny)).techRadar}));
  await page.locator('[data-visitor-agent="'+orbit+'"]').click();assert.match(await page.locator('#studio-crew-conversation').innerText(),/Heartbeat paused in Open Task/);
  const jobs=(await state(orbit)).jobs.length;await page.waitForTimeout(6500);assert.equal((await state(orbit)).jobs.length,jobs,'No new results while standing by without an assignment');
  assert.equal((await state(orbit)).techRadar.paused,false,'Room suspension must not write the manual Pause preference');
  await lounge();await waitState(orbit,'watching');assert.equal((await state(jinny)).techRadar.paused,true);
  await navigate('event-brief');await waitState(orbit,'watching');assert.equal(views.at(-1).openTask,false,'Event Brief does not suspend Heartbeat');
  await navigate('plan');await waitState(orbit,'paused in Open Task');
  await page.evaluate(()=>BacCampus.overview());await waitState(orbit,'watching');
  // The overview retains mission as its room; only the actual Open Task view suspends.
  await navigate('plan');await waitState(orbit,'paused in Open Task');
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile);await lounge();await waitState(orbit,'watching');
  assert.equal((await state(jinny)).techRadar.paused,true,'Reload preserves manual Pause');
  await navigate('plan');await waitState(orbit,'paused in Open Task');
  if(process.env.BAC_TEST_SCREENSHOT){await page.locator('[data-visitor-agent="'+orbit+'"]').click();await page.screenshot({path:process.env.BAC_TEST_SCREENSHOT});}
  assert.deepEqual(errors,[]);assert(views.some(v=>v.openTask===true));assert(views.some(v=>v.openTask===false));
  console.log(JSON.stringify({passed:true,host,checks:['two Tech Radar hires','idle Open Task suspension','saved results unchanged','manual Pause preserved','Lounge resume','Event Brief unaffected','overview resume','repeated navigation','reload','no browser errors']}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});

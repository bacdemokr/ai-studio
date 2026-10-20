// Render the built page offline: no live agents, model calls or policy changes.
const assert=require('node:assert/strict'),path=require('node:path');
const {pathToFileURL}=require('node:url'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')requests.push(r.url());});
  await page.goto(pathToFileURL(path.resolve(__dirname,'../app/index.html')).href);
  await page.waitForFunction(()=>window.BacCampus?.inspect().room==='workshop');
  await page.waitForFunction(()=>document.getElementById('agent-campus').dataset.boot==='error');
  await page.evaluate(()=>delete document.getElementById('agent-campus').dataset.boot);
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.mouse.move(1,1);
  await page.evaluate(()=>{
   BacCampus.setCollection([],null);
   window.idleAgents=[
    {key:'completed',name:'Jinny',persona:'guide',latestMission:{id:'previous',status:'done',answerPreview:'An old answer.'}},
    {key:'failed',name:'Orbit',persona:'maker',latestMission:{id:'failed-task',status:'error'}},
    {key:'busy',name:'Scout',persona:'analyst',activity:{kind:'mission'},latestMission:{id:'active-task',status:'running'}},
    {key:'deleting',name:'Smith',persona:'guide',deleting:true},
    {key:'heartbeat',name:'Radar',persona:'analyst',skills:['radar']},
    {key:'heartbeat-paused',name:'Paused Radar',persona:'analyst',skills:['radar'],techRadar:{paused:true}}
   ].map(a=>({skills:[],...a}));
   BacCampus.setCollection(idleAgents,null);
   window.idleStarted=BacCampus.inspect().clock;window.idleStarts=[];window.idleMaximum=0;let previous='';
   window.idleSampler=setInterval(()=>{
    const scene=BacCampus.inspect(),speakers=scene.residents.filter(r=>r.speech);
    idleMaximum=Math.max(idleMaximum,speakers.length);
    const current=speakers[0]?.key||'';
    if(current&&current!==previous)idleStarts.push({key:current,time:scene.clock,speech:speakers[0].speech});
    previous=current;
   },50);
  });
  await page.waitForFunction(()=>idleStarts.length>=2,null,{timeout:150000});
  const samples=await page.evaluate(()=>({start:idleStarted,speeches:idleStarts,maximum:idleMaximum}));
  assert(samples.speeches[0].time-samples.start>=29.9,'No idle chatter before 30 seconds');
  assert(samples.speeches[1].time-samples.speeches[0].time>=29.9,'One shared cadence, not a timer per agent');
  assert.deepEqual(new Set(samples.speeches.map(r=>r.key)),new Set(['completed','failed']),'Past success/failure does not silence idle agents; busy/deleting/heartbeat agents stay quiet, even when heartbeat is paused');
  assert.equal(samples.maximum,1);
  assert(samples.speeches.every(r=>r.speech!=='An old answer.'),'Old replies are not replayed as chatter');
  // A real new reply interrupts idle chatter immediately, without waiting 30s.
  await page.evaluate(()=>{
   const agent=idleAgents.find(a=>a.key==='heartbeat');
   agent.latestMission={id:'heartbeat-update',status:'done',answerPreview:'New work is ready.'};
   window.replyStarted=BacCampus.inspect().clock;BacCampus.setCollection(idleAgents,null);
  });
  await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.speech==='New work is ready.'));
  assert(await page.evaluate(()=>BacCampus.inspect().clock-replyStarted<3));
  // Newcomer greetings retain priority too.
  await page.evaluate(()=>BacCampus.welcomeAgent('heartbeat-paused'));
  await page.waitForFunction(()=>BacCampus.inspect().residents.some(r=>r.key==='heartbeat-paused'&&r.speech==='Hi, I’m Paused Radar.'));
  await page.evaluate(()=>clearInterval(idleSampler));
  // A heartbeat-only Lounge remains silent after a full idle interval.
  await page.evaluate(()=>{
   BacCampus.setCollection([],null);
   BacCampus.setCollection(idleAgents.filter(a=>a.key.startsWith('heartbeat')),null);
   window.heartbeatOnlyStart=BacCampus.inspect().clock;window.heartbeatChatter=false;
   window.heartbeatSampler=setInterval(()=>{heartbeatChatter||=BacCampus.inspect().residents.some(r=>r.speech);},50);
  });
  await page.waitForFunction(()=>BacCampus.inspect().clock-heartbeatOnlyStart>=31,null,{timeout:90000});
  assert.equal(await page.evaluate(()=>heartbeatChatter),false,'Heartbeat-only roster does not fall back to random chatter');
  await page.evaluate(()=>clearInterval(heartbeatSampler));
  assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
  console.log('PASS: 30-second global cadence, random non-repeating idle speakers with task history, busy/deleting/heartbeat suppression, heartbeat completion and welcome preserved, no model requests.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

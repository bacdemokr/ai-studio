// Explicit UI fixtures; no model calls or participant state changes.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/roundtable_fixture.py'],{encoding:'utf8'}));
 const state=fixture.state,crew=state.jobs.find(j=>j.kind==='crew');
 const read=(id,skill,label,status='completed')=>({id,tool:'read',status,target:'skills/'+skill+'/SKILL.md',customSkill:{id:skill,label}});
 const docs={available:true,calls:[read('a','bac-documents','Document Q&A'),read('b','bac-documents','Document Q&A'),read('c','weather','Built-in weather'),read('d','bac-writer','Failed skill','failed')]};
 const webpage={available:true,calls:[read('e','bac-nvidia-webpage','NVIDIA event page')]};
 const turn=(id,activity)=>({id,kind:'chat',status:'done',created:crew.created+10,payload:{prompt:'Summarize this document.'},events:[],result:{answer:'Three key points from the supplied document.',activity,files:[]}});
 state.jobs.push(turn('custom-skill-personal',docs),turn('ordinary-reply',{available:true,calls:[]}));
 crew.payload.activity={0:webpage};
 crew.payload.roundtable.replies[state.agentId].activity=docs;
 state.roundtableTurns[0].result.activity=docs;
 state.crewChats=[{...turn('custom-skill-direct',docs),kind:'crew-chat',payload:{crewRole:0,prompt:'Review my brief.'}}];
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1550,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:{ready:true,model:true,gateway:true}}));
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  const room=async name=>{await page.locator('.world-room-map [data-world-room='+name+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);};
  await room('lounge');
  const personal=page.locator('[data-chat-turn="custom-skill-personal"]');
  await personal.locator('.chat-custom-skill').waitFor();
  assert.equal(await personal.locator('.chat-custom-skill').count(),1);
  assert.match(await personal.innerText(),/Custom skill\s+Document Q&A/);
  assert.doesNotMatch(await personal.innerText(),/Built-in weather|Failed skill/);
  assert.equal(await page.locator('[data-chat-turn="ordinary-reply"] .chat-custom-skill').count(),0);
  const directory=path.resolve('../../work/custom-skill-visual');fs.mkdirSync(directory,{recursive:true});
  await personal.screenshot({path:path.join(directory,'lounge-skill.png')});
  await room('mission');await page.locator('[data-campus-agent="0"]').click();
  const log=page.locator('#studio-crew-conversation');
  assert.equal(await log.locator('.chat-custom-skill').count(),3); // event, direct chat, reaction
  assert.match(await log.innerText(),/Custom skill\s+NVIDIA event page/);
  assert.match(await log.innerText(),/Custom skill\s+Document Q&A/);
  await log.locator('.chat-turn').last().screenshot({path:path.join(directory,'crew-skill.png')});
  await page.reload();await page.waitForFunction(()=>window.BacStudio);await room('mission');await page.locator('[data-campus-agent="0"]').click();
  assert.equal(await log.locator('.chat-custom-skill').count(),3);
  assert.deepEqual(errors,[]);
  console.log('PASS: Lounge, crew event, direct crew chat and roundtable badges; deduplicated, built-in/failed reads excluded, ordinary replies unchanged, retained after reload.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

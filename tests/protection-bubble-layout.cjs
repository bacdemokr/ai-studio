// Real scene/layout with simulated native-policy evidence; no live model or policy changes.
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{mkdirSync}=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const port=Number(process.env.BAC_TEST_PORT||18348),server=spawn('python3',['-B','tests/fixture_personal_models.py'],{env:{...process.env,BAC_TEST_PORT:String(port)},stdio:['ignore','pipe','inherit']});let browser;
 try{
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout')),15000);server.stdout.on('data',b=>{if(b.toString().includes('PERSONAL MODEL FIXTURE READY')){clearTimeout(timer);resolve();}});server.once('exit',()=>reject(Error('Fixture exited')));});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
  const output=process.env.BAC_SCREENSHOTS||'/tmp/bac-protection-bubble';mkdirSync(output,{recursive:true});
  for(const [size,viewport] of Object.entries({desktop:{width:1600,height:1000},narrow:{width:390,height:844}})){
   const page=await browser.newPage({viewport,reducedMotion:size==='narrow'?'reduce':'no-preference'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   let owner,events=[],jobs=[],latestMission=null;
   const answer='naver.com에 접속을 시도했지만 OpenShell이 연결을 차단했어요. 사이트 접근을 허용하려면 OpenShell Policy에서 승인한 뒤 다시 요청해 주세요. '+ '날씨와 여행 정보를 확인해서 도움을 드릴 수 있어요. '.repeat(12);
   await page.route(/\/api\/(session|state)$/,async route=>{
    const response=await route.fetch({headers:{...route.request().headers(),'if-none-match':''}}),state=await response.json();owner=state.agentId;
    const profile={name:'Orbit',persona:'guide',tone:'kind',skills:['weather'],protection:'openshell',avatar:{body:'round',color:'cyan',accessory:'none'}};
    await route.fulfill({response,json:{...state,profile,agents:[{...profile,key:owner,pending:0,activity:null,latestMission}],jobs,protectionEvents:events}});
   });
   const event=(id,action='deny')=>({id,owner,role:null,time:Date.now()/1000,observedAt:Date.now()/1000,source:'OpenShell policy log',action,host:'naver.com'});
   await page.goto('http://127.0.0.1:'+port);await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Orbit');
   await page.evaluate(()=>BacStudio.setRoom('lounge'));await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   events.push(event('blocked'));await page.evaluate(()=>BacStudio.refresh());
   await page.waitForSelector('.world-protection-layer>.world-protection-hit:visible');
   jobs=[{id:'reply',kind:'chat',status:'done',created:Date.now()/1000-5,events:[],payload:{prompt:'search naver.com'},result:{answer}}];
   latestMission={id:'reply',status:'done',answerPreview:answer};await page.evaluate(()=>BacStudio.refresh());
   const bubble=page.locator('.world-resident[data-speaking=true][data-speech-kind=reply]'),notice=bubble.locator('.world-protection-hit[data-inline]');
   await notice.waitFor({state:'visible'});
   assert((await page.locator('#studio-conversation').innerText()).includes(answer.trim()),'Full reply must stay immediately available in chat');
   const checkLayout=async()=>{
    const bounds=await bubble.evaluate(node=>{const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom,height:r.height}};return{bubble:rect(node),notice:rect(node.querySelector('.world-protection-hit')),speech:rect(node.querySelector('.world-resident-speech')),viewport:rect(document.querySelector('#campus-viewport'))};});
    assert(bounds.notice.bottom<=bounds.speech.y,'Policy status must not cover the reply');
    assert(bounds.bubble.y>=bounds.viewport.y&&bounds.bubble.bottom<=bounds.viewport.bottom,'Bubble must fit inside the scene');
    assert(bounds.bubble.x>=bounds.viewport.x&&bounds.bubble.right<=bounds.viewport.right,'Bubble must fit the scene width');
    assert(bounds.notice.y>=bounds.bubble.y&&bounds.notice.bottom<=bounds.bubble.bottom,'Notice stays inside its owner bubble');
    for(const selector of ['.world-overview-button','.world-room-map']){
     const control=await page.locator(selector).boundingBox();
     if(control)assert(bounds.bubble.right<=control.x||bounds.bubble.x>=control.x+control.width||bounds.bubble.bottom<=control.y||bounds.bubble.y>=control.y+control.height,'Bubble must leave navigation controls clear');
    }
   };
   await checkLayout();assert.match(await notice.innerText(),/Request blocked.*naver.com/s);
   await page.locator('#campus-viewport').screenshot({path:output+'/'+size+'.png'});
   await page.waitForFunction(()=>!BacCampus.inspect().protectionHits.length);
   assert.equal(await page.locator('.world-protection-hit').count(),0,'Expired notice must leave no stale inline status');
   events.push(event('allowed','allow'));await page.evaluate(()=>BacStudio.refresh());
   await notice.waitFor({state:'visible'});await checkLayout();assert.match(await notice.innerText(),/Request allowed.*naver.com/s);
   // Navigation must hide even a notice reparented into a speech bubble.
   await page.evaluate(()=>BacStudio.setRoom('workshop'));await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   assert.equal(await page.locator('.world-protection-hit:visible').count(),0);
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS: desktop/narrow Korean reply, floating-to-inline denial, no overlap/clipping, full chat preserved, expiry, allow and navigation cleanup. Simulated policy evidence.');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));}}
})().catch(e=>{console.error(e);process.exitCode=1;});

// Disposable heartbeat fixture only. No live LLM, Telegram or attendee data.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(jobs|upload)$/.test(new URL(r.url()).pathname))writes.push({path:new URL(r.url()).pathname,owner:r.headers()['x-bac-agent'],body:r.postDataJSON()});});
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:18087');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
  await page.evaluate(async()=>{
   const s=await fetch('/api/session').then(r=>r.json());
   for(const [index,name,skills] of [[0,'Radar',['radar']],[1,'Helper',['documents']],[2,'Writer',['writer']]]){
    const response=await fetch(index?'/api/agents':'/api/onboard',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':s.csrf},body:JSON.stringify({name,skills,protection:'standard'})});
    if(!response.ok)throw Error(await response.text());
   }
  });
  await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Radar');
  await page.locator('.world-room-map [data-world-room=lounge]').click();
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  const agents=await page.evaluate(()=>BacStudio.inspect().agents),radar=agents.find(a=>a.name==='Radar');
  async function select(name){
   await page.locator('#studio-agent-list [data-agent-key="'+agents.find(a=>a.name===name).key+'"]').click();
   await page.waitForFunction(name=>BacStudio.inspect().profile?.name===name,name);
  }
  async function blocked(value){for(const id of ['prompt','send','attach','run-options','schedule'])assert.equal(await page.locator('#studio-'+id).isDisabled(),value,id);}
  await blocked(true);
  assert.match(await page.locator('#studio-chat-connection-text').innerText(),/Manual chat is disabled/);
  await page.waitForFunction(()=>BacStudio.inspect().jobs.some(j=>j.kind==='heartbeat'&&!j.result.systemNotice));
  const count=await page.evaluate(()=>BacStudio.inspect().jobs.filter(j=>j.kind==='heartbeat').length);
  await page.locator('#studio-radar-monitor button').click();
  await page.waitForFunction(()=>document.querySelector('#studio-radar-monitor').textContent.includes('Paused'));
  await blocked(true);
  await page.locator('#studio-radar-monitor button').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-radar-monitor').textContent.includes('Paused'));
  await page.evaluate(()=>{const form=document.querySelector('#studio-chat');document.querySelector('#studio-prompt').value='bypass attempt';form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));});
  assert.equal(writes.length,0);
  // Dropping files must obey the same disabled state as the attachment button.
  const dropped=page.waitForRequest(r=>r.method()==='POST'&&new URL(r.url()).pathname==='/api/upload',{timeout:1200}).then(()=>true,()=>false);
  await page.locator('#studio-companion').evaluate(node=>{const dataTransfer=new DataTransfer();dataTransfer.items.add(new File(['fixture'],'disabled-drop.txt',{type:'text/plain'}));node.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer}));});
  assert.equal(await dropped,false,'disabled Radar composer must reject document drops');
  await select('Helper');await blocked(false);
  await page.locator('#studio-prompt').fill('Keep this draft');await select('Radar');await blocked(true);
  await select('Helper');assert.equal(await page.locator('#studio-prompt').inputValue(),'Keep this draft');
  await page.locator('#studio-run-options').click();await page.locator('#studio-send-all').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-send').disabled);
  const sent=writes.filter(r=>r.path==='/api/jobs');assert.equal(sent.length,2);assert(sent.every(r=>r.owner!==radar.key));
  await select('Radar');await blocked(true);
  assert.equal(await page.evaluate(()=>BacStudio.inspect().jobs.filter(j=>j.kind==='heartbeat').length),count);
  // A second skill restores manual chat while Heartbeat remains active.
  await page.locator('#studio-edit-agent').click();await page.getByRole('button',{name:'Weather buddy',exact:true}).click();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.includes('weather'));await blocked(false);
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-skill-picker input[value="radar"]').check();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>['radar','weather'].every(skill=>BacStudio.inspect().profile?.skills.includes(skill)));await blocked(false);
  assert.equal(await page.locator('#studio-radar-monitor').isVisible(),true);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.skills.includes('radar'));await blocked(false);
  // Tech Radar by itself remains dedicated to Heartbeat updates.
  await page.locator('#studio-edit-agent').click();await page.locator('#studio-skill-picker input[value="weather"]').uncheck();await page.locator('#studio-create').click();
  await page.waitForFunction(()=>BacStudio.inspect().profile?.skills.length===1&&BacStudio.inspect().profile.skills[0]==='radar');await blocked(true);
  await page.reload();await page.waitForFunction(()=>window.BacStudio?.inspect().profile?.name==='Radar');await blocked(true);
  assert.deepEqual(errors,[]);
  console.log('PASS: Radar-only chat restriction, mixed-skill chat, forced submit, file drop, pause/resume, heartbeat delivery, profile edits, reload, drafts and group-chat exclusion.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

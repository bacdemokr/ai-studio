// Delayed API responses must not erase new drafts or take over a newer dialog.
const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
const state=JSON.parse(execFileSync('python3',['-B','-c',`import sys,tempfile,json
sys.path[:0]=['scripts','tests']
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as d:
 s=Studio(d,Adapter(),start_worker=False);o=s.session()[0]['id'];s.onboard(o,{'name':'Draft tester','persona':'guide','skills':['documents']});s.add_agent(o,{'name':'Second','persona':'guide','skills':['documents']});state=s.state(o);state.update(csrf='fixture',canConfigure=True,runtime={'ready':True,'gateway':True,'model':True,'installed':True});print(json.dumps(state))`],{encoding:'utf8'}));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});let failures=0;
 async function pasteImage(page,crew,name){
  await page.evaluate(async({crew,name})=>{
   const canvas=document.createElement('canvas');canvas.width=16;canvas.height=16;
   const blob=await new Promise(resolve=>canvas.toBlob(resolve)),clipboardData=new DataTransfer();
   clipboardData.items.add(new File([blob],name,{type:'image/png'}));
   document.querySelector(crew?'#studio-crew-prompt':'#studio-prompt').dispatchEvent(new ClipboardEvent('paste',{clipboardData,bubbles:true,cancelable:true}));
  },{crew,name});
 }
 async function scenario(name,run){
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route(/\/api\/(session|state)$/,r=>r.fulfill({json:state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:state.runtime}));
  await page.route('**/api/settings',r=>r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{local:{model:'original',contextWindow:32768}}}}));
  try{
   await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8082');await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Draft tester');
   await run(page);assert.deepEqual(errors,[]);console.log('PASS:',name);
  }catch(error){failures++;console.error('FAIL:',name,error.message);}
  finally{await page.close();}
 }
 try{
  for(const crew of [false,true])await scenario(crew?'crew draft survives delayed send and role switch':'personal draft survives delayed send',async page=>{
   let finish,calls=0;
   await page.route('**/api/jobs',async r=>{calls++;assert.equal(r.request().postDataJSON().images.length,1);await new Promise(resolve=>finish=resolve);await r.fulfill({json:{id:'sent-'+calls}});});
   await page.evaluate(room=>BacStudio.setRoom(room),crew?'mission':'lounge');await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   const input=page.locator(crew?'#studio-crew-prompt':'#studio-prompt');
   await pasteImage(page,crew,'first.png');
   const previews=page.locator(crew?'#studio-crew-image-drafts img':'#studio-image-drafts img');await previews.first().waitFor();
   await input.fill('First message');await input.press('Enter');await page.waitForFunction(crew=>document.querySelector(crew?'#studio-crew-send':'#studio-send').disabled,crew);
   assert.equal(calls,1);await input.fill('Next draft must remain');
   await pasteImage(page,crew,'next.png');await previews.nth(1).waitFor();
   if(crew){await page.locator('[data-crew-member="3"]').click();await input.fill('Morgan draft');}
   finish();await page.waitForFunction(crew=>!document.querySelector(crew?'#studio-crew-send':'#studio-send').disabled,crew);
   if(crew){assert.equal(await input.inputValue(),'Morgan draft');await page.locator('[data-crew-member="0"]').click();}
   assert.equal(await input.inputValue(),'Next draft must remain');
   assert.equal(await previews.count(),1);assert.equal(await previews.first().getAttribute('alt'),'next.png');
  });
  await scenario('failed send to all keeps the draft for retry',async page=>{
   let posts=0;await page.route('**/api/jobs',r=>{posts++;return r.fulfill({status:503,json:{error:'Temporary failure'}});});
   await page.evaluate(()=>BacStudio.setRoom('lounge'));await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-prompt').fill('Retry this message');
   await page.evaluate(()=>document.querySelector('#studio-chat').requestSubmit(document.querySelector('#studio-send-all')));
   await page.waitForFunction(()=>!document.querySelector('#studio-send-all').disabled);assert.equal(posts,2);
   assert.equal(await page.locator('#studio-prompt').inputValue(),'Retry this message');
  });
  await scenario('run all cannot also submit the same message to the selected agent',async page=>{
   let finish,posts=0;
   await page.route('**/api/jobs',async r=>{posts++;if(posts===1)await new Promise(resolve=>finish=resolve);return r.fulfill({json:{id:'send-'+posts}});});
   await page.evaluate(()=>BacStudio.setRoom('lounge'));await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
   await page.locator('#studio-prompt').fill('One message each');
   await page.evaluate(()=>document.querySelector('#studio-chat').requestSubmit(document.querySelector('#studio-send-all')));
   await page.waitForFunction(()=>document.querySelector('#studio-send-all').disabled);
   await page.evaluate(()=>document.querySelector('#studio-chat').requestSubmit(document.querySelector('#studio-send')));
   await page.waitForTimeout(100);const during=posts;finish();
   await page.waitForFunction(()=>!document.querySelector('#studio-send-all').disabled);
   assert.equal(during,1,'Single submit must wait for the group send');assert.equal(posts,2);
   await page.locator('#studio-compare-open').click();
   assert(await page.locator('#studio-compare').isVisible(),'Comparison must be accessible after Run all');
   assert.equal(await page.locator('.studio-compare-grid article').count(),2);
  });
  await scenario('old model connect cannot close or change a reopened settings form',async page=>{
   let finish,posts=0;
   await page.route('**/api/settings',async r=>{
    if(r.request().method()==='POST'){posts++;await new Promise(resolve=>finish=resolve);return r.fulfill({json:{}});}
    return r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{local:{model:'original',contextWindow:32768}}}});
   });
   await page.locator('#studio-config').click();await page.locator('#studio-model').fill('first-model');await page.locator('#studio-save-settings').click();
   await page.waitForFunction(()=>document.querySelector('#studio-save-settings').disabled);assert.equal(posts,1);
   await page.locator('#studio-dialog-close').click();await page.locator('#studio-config').click();await page.locator('#studio-model').fill('new-unsaved-draft');
   finish();await page.waitForTimeout(350);
   assert(await page.locator('#studio-dialog').evaluate(e=>e.open),'Old completion closed new dialog');
   assert.equal(await page.locator('#studio-model').inputValue(),'new-unsaved-draft');
  });
  await scenario('repeated submit starts only one model connection',async page=>{
   let finish,posts=0;
   await page.route('**/api/settings',async r=>{
    if(r.request().method()==='POST'){posts++;await new Promise(resolve=>finish=resolve);return r.fulfill({json:{}});}
    return r.fulfill({json:{provider:'local',providers:{local:{label:'Local',baseUrl:'http://localhost:8000/v1'}},profiles:{local:{model:'original',contextWindow:32768}}}});
   });
   await page.locator('#studio-config').click();await page.locator('#studio-model').fill('model');
   await page.evaluate(()=>{const f=document.querySelector('#studio-config-form');f.requestSubmit();f.requestSubmit();});
   await page.waitForTimeout(250);assert.equal(posts,1,'Duplicate connection request');finish();
   await page.waitForFunction(()=>!document.querySelector('#studio-dialog').open);
  });
 }finally{await browser.close();}
 if(failures)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});

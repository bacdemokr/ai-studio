const assert=require('node:assert/strict'),{chromium}=require('playwright'),{execFileSync}=require('node:child_process');
(async()=>{
 const state=JSON.parse(execFileSync('python3',['-c',`import sys,tempfile,json
sys.path[:0]=['scripts','tests']
from studio import Studio
from test_studio import Adapter
with tempfile.TemporaryDirectory() as d:
 s=Studio(d,Adapter(),start_worker=False);o=s.session()[0]['id'];s.onboard(o,{'name':'Deleting','skills':['weather']});s.crew_owner(o)
 with s.db() as db:db.execute('UPDATE agents SET deleting=1 WHERE id=?',(o,))
 v=s.state(o);v.update(csrf='test',canConfigure=True,runtime={'ready':True,'gateway':True,'model':True});print(json.dumps(v))`],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],sent=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/api/session'||path==='/api/state')return route.fulfill({json:state});
   if(path==='/api/runtime')return route.fulfill({json:state.runtime});
   if(path==='/api/jobs'){sent.push(route.request().postDataJSON());return route.fulfill({json:{id:'fixture'}});}
   if(path==='/api/crew-policy')return route.fulfill({json:{mode:'openshell',status:'applied',sandboxes:[{}],requested:[],catalog:{weather:{title:'Weather',hosts:['example.com']}},recentDenied:[]}});
   return route.fulfill({json:{}});
  });
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');
  await page.waitForFunction(()=>window.BacStudio?.inspect().agents.some(a=>a.deleting));
  await page.evaluate(()=>BacStudio.setRoom('mission'));
  await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-crew-prompt').isDisabled(),false);
  assert.equal(await page.locator('#studio-crew-chat-connection').isHidden(),true);
  await page.locator('#studio-crew-prompt').fill('Hello Casey');await page.locator('#studio-crew-send').click();
  await page.waitForFunction(()=>!document.querySelector('#studio-crew-send').disabled);
  assert.equal(sent.length,1);assert.equal(sent[0].kind,'crew-chat');
  await page.locator('[data-crew-member="1"]').click();await page.locator('#studio-crew-policy').click();
  await page.waitForFunction(()=>document.querySelector('#studio-policy-content').textContent.includes('Pre-approve'));
  assert.equal(await page.locator('#studio-policy-content button').first().isDisabled(),false);
  await page.locator('#studio-surface-close').click();
  await page.evaluate(()=>BacStudio.setRoom('lounge'));await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  assert.equal(await page.locator('#studio-prompt').isDisabled(),true);
  assert.deepEqual(errors,[]);
  console.log('PASS: Lounge deletion keeps personal chat blocked while Casey chat and Dylan policy stay usable. Mocked HTTP, no user agents changed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

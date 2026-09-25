const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async response=>{if(response.url().endsWith('/api/upload')&&response.status()!==200)console.error('Upload rejected',response.status(),(await response.json()).error||'ok');});
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8097');
 await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
 async function api(route,body,owner){return page.evaluate(async({route,body,owner})=>{
  const session=await (await fetch('/api/session')).json();
  const response=await fetch('/api/'+route,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,...(owner?{'X-BaC-Agent':owner}:{})},...(body?{body:JSON.stringify(body)}:{})});
  return {status:response.status,data:await response.json()};
 },{route,body,owner});}
 await page.route('**/api/agent-policy',route=>route.fulfill({json:{status:'applied',requested:[],catalog:{'host:one.test':{title:'one.test',hosts:['one.test']},'host:two.test':{title:'two.test',hosts:['two.test']}},pendingAccess:[{host:'one.test'},{host:'one.test'},{host:'two.test'}],sandboxes:['fixture']}}));
 const first=(await api('session')).data.agentId;
 assert.equal((await api('onboard',{name:'Upload A',skills:['documents']},first)).status,200);
 const second=(await api('agents',{name:'Upload B',skills:['documents'],protection:'openshell'},first)).data.agentId;
 await page.reload();await page.waitForSelector('[data-agent-key="'+second+'"]',{state:'attached'});
 await page.locator('.world-room-map [data-world-room=lounge]').click();
 await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.locator('[data-agent-key="'+second+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload B');
 await page.waitForFunction(()=>document.querySelector('#studio-agent-policy .policy-pending-badge')?.textContent==='2');
 assert.match(await page.locator('#studio-agent-policy').getAttribute('aria-label'),/2 websites awaiting approval/);
 await page.screenshot({path:'/tmp/bac-policy-badge.png'});
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload A');
 assert(await page.locator('#studio-agent-policy').isHidden());
 assert.deepEqual(errors,[]);
 console.log('PASS: Chrome displays two pending websites for the protected agent only');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

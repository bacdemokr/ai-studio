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
 let approved=false,release,fail=false;
 const gate=new Promise(resolve=>release=resolve);
 const presets={papers:{title:'arXiv papers',hosts:['export.arxiv.org','arxiv.org']},weather:{title:'Weather & city lookup',hosts:['api.open-meteo.com','geocoding-api.open-meteo.com','wttr.in']},zurich:{title:'Zurich visitor guide',hosts:['www.zuerich.com']},wiki:{title:'Wikipedia search',hosts:['en.wikipedia.org']},github:{title:'Public GitHub API',hosts:['api.github.com']}};
 let submitted;
 const policy=()=>({status:'applied',requested:approved?Object.keys(presets):[],catalog:{...presets,'host:one.test':{title:'one.test',hosts:['one.test']}},pendingAccess:[{host:'one.test'}],sandboxes:['fixture']});
 await page.route('**/api/agent-policy',async route=>{
  if(route.request().method()==='POST'){submitted=route.request().postDataJSON();await gate;approved=true;}
  return route.fulfill({json:policy()});
 });
 const first=(await api('session')).data.agentId;
 assert.equal((await api('onboard',{name:'Upload A',skills:['documents']},first)).status,200);
 const second=(await api('agents',{name:'Upload B',skills:['documents'],protection:'openshell'},first)).data.agentId;
 await page.reload();await page.waitForSelector('[data-agent-key="'+second+'"]',{state:'attached'});
 await page.locator('.world-room-map [data-world-room=lounge]').click();
 await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.locator('[data-agent-key="'+second+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload B');
 await page.waitForFunction(()=>document.querySelector('#studio-agent-policy .policy-pending-badge')?.textContent==='1');
 assert.match(await page.locator('#studio-agent-policy').getAttribute('aria-label'),/1 website awaiting approval/);
 await page.locator('#studio-agent-policy').click();
 const section=page.locator('[data-policy-section="preset"]');
 await section.locator('.policy-access-card').first().waitFor();
 assert.equal(await section.locator('.policy-access-card').count(),5);
 const boxes=await section.locator('.policy-access-card').evaluateAll(nodes=>nodes.map(n=>({x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,height:n.getBoundingClientRect().height})));
 assert(boxes.every(b=>b.x===boxes[0].x&&b.height<100));
 await page.screenshot({path:'/tmp/bac-preset-list.png'});
 await section.locator('[data-policy-approve-all]').click();
 await page.locator('.policy-loading').waitFor({state:'visible'});
 assert.equal(submitted.scope,'presets');assert.deepEqual(submitted.permissions,Object.keys(presets));
 release();await page.waitForFunction(()=>!document.querySelector('.policy-loading'));
 assert.equal(await section.locator('.policy-access-card').count(),0);
 assert.equal(await page.locator('[data-policy-section="blocked"] .policy-access-card').count(),1);
 assert.deepEqual(errors,[]);
 console.log('PASS: compact five-row presets and scoped Approve all preserve pending requests');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

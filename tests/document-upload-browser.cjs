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
 const first=(await api('session')).data.agentId;
 assert.equal((await api('onboard',{name:'Upload A',skills:['documents']},first)).status,200);
 const second=(await api('agents',{name:'Upload B',skills:['documents'],protection:'openshell'},first)).data.agentId;
 await page.reload();await page.waitForSelector('[data-agent-key="'+second+'"]',{state:'attached'});
 await page.locator('.world-room-map [data-world-room=lounge]').click();
 await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.locator('#studio-upload').setInputFiles([
  {name:'notes.md',mimeType:'text/markdown',buffer:Buffer.from('Only agent A notes.')},
  {name:'large.csv',mimeType:'text/csv',buffer:Buffer.alloc(2*1024*1024,120)}]);
 try{await page.waitForFunction(()=>[...document.querySelectorAll('#studio-documents li')].some(n=>n.title==='large.csv')&&!document.querySelector('#studio-attach').disabled);}catch(error){console.error(JSON.stringify({errors,files:(await api('state',undefined,first)).data.files,selected:await page.evaluate(()=>BacStudio.inspect().profile?.name),panel:await page.locator('#studio-documents').innerHTML(),dialog:await page.locator('#studio-dialog-body').innerText()}));throw error;}
 assert(!await page.locator('.studio-alert').isVisible());
 assert.deepEqual(await page.locator('#studio-documents li').evaluateAll(nodes=>nodes.map(n=>n.title)),['large.csv','notes.md']);
 assert.match(await page.locator('#studio-documents').innerText(),/notes.md/);
 assert((await page.locator('#studio-documents').boundingBox()).y<(await page.locator('#studio-conversation').boundingBox()).y);
 await page.locator('[data-agent-key="'+second+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload B');
 assert(await page.locator('#studio-documents').isHidden());
 const denied=await api('file?path=inbox/notes.md',undefined,second);assert.equal(denied.status,404);
 await page.waitForFunction(()=>!document.querySelector('#studio-attach').disabled);
 const transfer=await page.evaluateHandle(()=>{const dt=new DataTransfer();dt.items.add(new File(['Only B upload.'],'protected.txt',{type:'text/plain'}));return dt;});
 await page.locator('#studio-prompt').dispatchEvent('dragover',{dataTransfer:transfer});
 assert(await page.locator('#studio-companion').evaluate(n=>n.classList.contains('document-drag-over')));
 await page.locator('#studio-prompt').dispatchEvent('drop',{dataTransfer:transfer});
 await page.waitForFunction(()=>[...document.querySelectorAll('#studio-documents li')].some(n=>n.title==='protected.txt')&&!document.querySelector('#studio-attach').disabled);
 assert(!(await page.locator('#studio-documents').innerText()).includes('notes.md'));
 assert.equal((await api('file?path=inbox/protected.txt',undefined,second)).data.content,'Only B upload.');
 await page.locator('#studio-upload').setInputFiles({name:'too-big.txt',mimeType:'text/plain',buffer:Buffer.alloc(10*1024*1024+1,120)});
 await page.waitForFunction(()=>document.querySelector('#studio-dialog').open);
 assert.match(await page.locator('#studio-dialog-body').innerText(),/10 MB/);
 assert.equal((await api('file?path=inbox/too-big.txt',undefined,second)).status,404);
 await page.locator('#studio-dialog').evaluate(n=>n.close());
 await page.reload();await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload B');
 await page.waitForFunction(()=>[...document.querySelectorAll('#studio-documents li')].some(n=>n.title==='protected.txt')&&!document.querySelector('#studio-attach').disabled);
 await page.locator('.world-room-map [data-world-room=lounge]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 await page.locator('[data-agent-key="'+first+'"]').click();
 await page.waitForFunction(()=>BacStudio.inspect().profile?.name==='Upload A');
 assert.match(await page.locator('#studio-documents').innerText(),/notes.md/);
 assert(!(await page.locator('#studio-documents').innerText()).includes('protected.txt'));
 await page.screenshot({path:'/tmp/bac-agent-document-list.png'});
 assert.deepEqual(errors,[]);
 console.log('PASS: multi-file picker, >1MB text, agent-local list above chat, no success alert, cross-agent 404, protected-agent drop, 10MB rejection and reload persistence.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1440,height:1050}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(process.env.BASE_URL||'http://127.0.0.1:8098');await p.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
 await p.locator('.world-room-map [data-world-room=mission]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await p.locator('[data-campus-agent="0"]').click();
 await p.locator('#studio-crew-document-input').setInputFiles([{name:'plan-notes.md',mimeType:'text/markdown',buffer:Buffer.from('Orion budget 4200; spent 1700.')},{name:'private (1).txt',mimeType:'text/plain',buffer:Buffer.from('Not selected.') }]);
 await p.waitForFunction(()=>document.querySelectorAll('#studio-crew-documents input').length===2&&!document.querySelector('#studio-crew-document-add').disabled);
 await p.locator('[data-crew-document="inbox/private (1).txt"]').uncheck();
 await p.locator('#studio-crew-chat').evaluate(e=>{const d=new DataTransfer();d.items.add(new File(['Drop test evidence'],'chat-notes.txt',{type:'text/plain'}));e.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:d}));});
 await p.waitForFunction(()=>document.querySelectorAll('#studio-crew-documents input').length===3&&!document.querySelector('#studio-crew-document-add').disabled);
 let sent;await p.route('**/api/jobs',r=>{sent=r.request().postDataJSON();return r.fulfill({json:{id:'fixture-captured',collaboration:false}})});
 await p.locator('#studio-crew-prompt').fill('/plan summarize the selected documents');await p.locator('#studio-crew-send').click();await p.waitForFunction(()=>document.querySelector('#studio-crew-prompt').value==='');assert(sent.prompt.includes('plan-notes.md'));assert(sent.prompt.includes('chat-notes.txt'));assert(!sent.prompt.includes('private (1).txt'));assert.equal(sent.crewRole,0);
 await p.locator('#studio-crew-document-input').setInputFiles({name:'oversize.txt',mimeType:'text/plain',buffer:Buffer.alloc(10*1024*1024+1,65)});await p.getByText('oversize.txt: Choose a file of 10 MB or smaller.',{exact:true}).waitFor();assert(await p.locator('#studio-crew-prompt').isEnabled());assert.deepEqual(errors,[]);
 console.log('PASS: Casey uploads, plan-/chat- names, drag/drop, selected-only inputs, draft clearing and oversized-file recovery.');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/agent_documents_fixture.py'],{encoding:'utf8'}));
 fixture.state.runtime={ready:false,model:false,gateway:true};
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 let release;
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedDefinition=text;}}}));
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
  await page.route('**/api/runtime',r=>r.fulfill({json:{ready:false,model:false,gateway:true}}));
  let delay=false;
  await page.route('**/api/agent-documents*',async r=>{
   const role=new URL(r.request().url()).searchParams.get('role')||'personal';
   if(role==='personal'&&delay)await new Promise(resolve=>{release=resolve;});
   await r.fulfill({json:fixture.documents[role]});
  });
  await page.goto('http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  const room=async name=>{await page.locator('.world-room-map [data-world-room='+name+']').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);};
  await room('lounge');await page.locator('#studio-agent-name').focus();await page.keyboard.press('Enter');
  const source=page.locator('#studio-identity-source'),modal=page.locator('#studio-dialog');
  await source.waitFor();assert.equal(await source.innerText(),fixture.documents.personal.documents[0].content);
  assert.equal(await page.evaluate(()=>window.identityInjected),undefined);
  await modal.getByRole('button',{name:'MEMORY.md Saved memory'}).click();assert.match(await source.innerText(),/Prefers concise answers/);
  await modal.getByRole('button',{name:'Three Takeaways SKILL.md'}).click();assert.match(await source.innerText(),/name: bac-documents/);
  await page.locator('#studio-identity-copy').click();assert.equal(await page.evaluate(()=>window.copiedDefinition),await source.innerText());
  await modal.getByRole('button',{name:'USER.md User preferences'}).click();assert.match(await page.locator('#studio-identity-unavailable').innerText(),/has not been created/);assert(await page.locator('#studio-identity-copy').isDisabled());assert(await source.isHidden());
  await modal.getByRole('button',{name:'SOUL.md Personality & role'}).click();
  const directory=path.resolve('../../work/agent-documents-visual');fs.mkdirSync(directory,{recursive:true});
  await modal.screenshot({path:path.join(directory,'personal-files.png')});
  await page.keyboard.press('Escape');assert(!(await modal.isVisible()));
  // A late response from the closed personal viewer cannot replace the crew file.
  delay=true;await page.locator('#studio-portrait').click();await page.waitForTimeout(100);await page.locator('#studio-dialog-close').click();
  await room('mission');await page.locator('[data-campus-agent="0"]').click();await page.locator('#studio-crew-name').click();
  await source.waitFor();assert.match(await source.innerText(),/Casey has these distinct/);
  release?.();delay=false;await page.waitForTimeout(100);assert.match(await source.innerText(),/Casey has these distinct/);
  await page.keyboard.press('Escape');await page.locator('[data-campus-agent="1"]').click();
  await page.locator('#studio-focus').click();await page.locator('#studio-crew-portrait').click();await source.waitFor();
  assert.match(await source.innerText(),/Dylan has these distinct/);assert(await modal.isVisible());
  await modal.screenshot({path:path.join(directory,'crew-files.png')});
  await page.setViewportSize({width:430,height:900});
  assert(await modal.evaluate(e=>e.scrollWidth<=e.clientWidth+1));assert(await source.isVisible());
  await modal.screenshot({path:path.join(directory,'mobile-files.png')});
  assert.deepEqual(errors,[]);
  console.log('PASS: name/portrait and keyboard opening, exact saved source, skill files, missing files, safe rendering/copy, stale-response isolation, crew selection, fullscreen and narrow layout.');
 }finally{release?.();await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

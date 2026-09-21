const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/agent_led_fixture.py'],{encoding:'utf8'}));
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],downloads=[];page.on('pageerror',e=>errors.push(e.message));page.on('download',d=>downloads.push(d));
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{window.copiedJSON=value;}}}));
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
  let bad=false,delayed=false,release;const proposal=Object.keys(fixture.files).find(p=>p.endsWith('-themes.json'));
  await page.route('**/api/file?*',async r=>{
   const path=new URL(r.request().url()).searchParams.get('path');
   if(path===proposal&&delayed)await new Promise(resolve=>{release=resolve});
   await r.fulfill({json:path===proposal&&bad?{content:'{broken json'}:fixture.files[path]||{content:fixture.page,mime:'text/html'}});
  });
  await page.goto('http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-surface=control]').first().click();await page.locator('[data-role-output="1"]').click();
  await page.locator('.event-showcase-preview[data-ready=true]').waitFor();
  const dialog=page.locator('#studio-dialog');
  for(const [suffix,label,title] of [['-themes.json','View proposal','Dylan · Proposal'],['-theme-research.json','View sources','Dylan · Sources'],['-schedule-plan.json','View plan','Alex · Schedule plan']]){
   const button=page.locator(`[data-result-json$="${suffix}"]`);assert.equal(await button.innerText(),label);await button.scrollIntoViewIfNeeded();
   const before=await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop);
   await button.click();await page.locator('#studio-json-browse').waitFor();assert.equal(await page.locator('#studio-dialog-kicker').innerText(),title);
   assert(await page.locator('.result-json-branch').count()>0);assert(await dialog.evaluate(e=>e.scrollHeight<=e.clientHeight+1),'The modal body must not add a second scroll');
   const expected=JSON.stringify(JSON.parse(fixture.files[Object.keys(fixture.files).find(p=>p.endsWith(suffix))].content),null,2);
   await page.locator('[data-json-view=raw]').click();assert.equal(await page.locator('#studio-json-raw').innerText(),expected);
   await page.locator('#studio-json-copy').click();assert.equal(await page.evaluate(()=>window.copiedJSON),expected);
   await page.locator('[data-json-view=raw]').press('ArrowLeft');assert.equal(await page.locator('[data-json-view=browse]').getAttribute('aria-selected'),'true');
   if(suffix==='-themes.json'){await page.locator('.result-json-branch .result-json-branch>summary').first().click();await page.locator('.result-json-branch .result-json-row').first().waitFor();fs.mkdirSync('../../work/result-json',{recursive:true});await page.screenshot({path:'../../work/result-json/proposal.png'});}
   await page.keyboard.press('Escape');assert(!(await dialog.isVisible()));
   assert(Math.abs(await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop)-before)<2,'Closing must preserve Results position');
  }
  assert.equal(downloads.length,0,'JSON actions must not download');
  assert.equal(await page.locator('[data-package-download$="-presenter-rota.xlsx"]').innerText(),'Download Excel');
  const saved=page.waitForEvent('download');await page.locator('[data-package-download$="-presenter-rota.xlsx"]').click();const excel=await saved;
  const expectedExcel=Object.entries(fixture.files).find(([p])=>p.endsWith('-presenter-rota.xlsx'));
  assert.equal(excel.suggestedFilename(),expectedExcel[0].split('/').pop());assert.deepEqual(fs.readFileSync(await excel.path()),Buffer.from(expectedExcel[1].content,'base64'));
  // Render user/model text as text, never executable HTML or unsafe links.
  fixture.files[proposal].content=JSON.stringify({demos:[{title:'<img src=x onerror="window.jsonInjected=1">',source:'javascript:alert(1)',notes:'<script>window.jsonInjected=1</script>',url:'https://example.com/evidence'}]});
  await page.locator('[data-result-json$="-themes.json"]').click();await page.locator('#studio-json-browse').waitFor();await page.locator('.result-json-branch .result-json-branch>summary').click();
  assert.equal(await page.locator('#studio-json-viewer script,#studio-json-viewer img,#studio-json-viewer a[href^="javascript:"]').count(),0);assert.equal(await page.evaluate(()=>window.jsonInjected),undefined);
  assert.equal(await page.locator('#studio-json-viewer a').getAttribute('rel'),'noopener noreferrer');
  fs.mkdirSync('../../work/result-json',{recursive:true});await page.screenshot({path:'../../work/result-json/desktop.png'});
  await page.setViewportSize({width:430,height:900});await page.screenshot({path:'../../work/result-json/mobile.png'});
  assert(await page.locator('#studio-json-viewer').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
  await page.keyboard.press('Escape');await page.setViewportSize({width:1500,height:1050});
  // Failure offers retry, rather than silently downloading or inventing a preview.
  bad=true;await page.locator('[data-result-json$="-themes.json"]').click();await page.locator('#studio-json-viewer [role=alert]').waitFor();assert.match(await page.locator('#studio-json-viewer').innerText(),/invalid JSON/);
  bad=false;await dialog.getByRole('button',{name:'Retry',exact:true}).click();await page.locator('#studio-json-browse').waitFor();await page.keyboard.press('Escape');
  // A late response from a closed preview cannot replace a newer file.
  delayed=true;await page.locator('[data-result-json$="-themes.json"]').click();await page.waitForFunction(()=>document.querySelector('#studio-json-viewer')?.textContent==='Loading file');
  while(!release)await page.waitForTimeout(20);await page.keyboard.press('Escape');await page.locator('[data-result-json$="-schedule-plan.json"]').click();await page.locator('#studio-json-browse').waitFor();release();await page.waitForTimeout(150);assert.equal(await page.locator('#studio-dialog-kicker').innerText(),'Alex · Schedule plan');
  assert.deepEqual(errors,[]);console.log('PASS: named JSON previews, saved content, structured/raw views, copy, no JSON downloads, exact Excel bytes, preserved scroll, keyboard/narrow layout, escaping, retry and stale-response isolation.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

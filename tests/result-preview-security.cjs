const assert=require('node:assert/strict'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
(async()=>{
 const fixture=JSON.parse(execFileSync('python3',[__dirname+'/agent_led_fixture.py'],{encoding:'utf8'}));
 fixture.page=fixture.page.replace('</head>',`<meta http-equiv="refresh" content="0;url=https://untrusted.invalid/refresh"><style>@import url('https://untrusted.invalid/style');</style></head>`).replace('</body>',`<script>parent.document.body.dataset.compromised='yes';fetch('/api/state')</script><iframe src="/api/state"></iframe><img src="https://untrusted.invalid/image" onerror="parent.document.body.dataset.compromised='image'"><a href="javascript:parent.document.body.dataset.compromised='link'">Unsafe link</a><svg onload="parent.document.body.dataset.compromised='svg'"></svg><form action="/api/reset"><input name="confirm" value="true"></form></body>`);
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1450,height:1000}}),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('untrusted.invalid'))requests.push(r.url());});
  for(const endpoint of ['session','state'])await page.route('**/api/'+endpoint,r=>r.fulfill({json:fixture.state}));
  await page.route('**/api/file?*',r=>r.fulfill({json:{content:fixture.page,mime:'text/html'}}));
  await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:8080');await page.waitForFunction(()=>window.BacStudio);
  await page.locator('.world-room-map [data-world-room=mission]').click();await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
  await page.locator('[data-surface=deliverables]').first().click();await page.locator('.event-showcase-preview[data-ready=true]').waitFor();
  const frame=page.frameLocator('.event-showcase-preview');
  assert.equal(await frame.locator('script,iframe,svg,form,meta[http-equiv=refresh]').count(),0);
  assert.equal(await frame.locator('[onerror],[onload],[src]').count(),0);
  assert.equal(await frame.getByText('Unsafe link').getAttribute('href'),null);
  assert.equal(await page.locator('body').getAttribute('data-compromised'),null);
  assert.match(await frame.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content'),/script-src 'none'/);
  assert(!(await page.locator('.event-showcase-preview').getAttribute('sandbox')).includes('allow-scripts'));
  const link=frame.locator('a[href^="https://"]').first();assert.equal(await link.getAttribute('target'),'_blank');assert.match(await link.getAttribute('rel'),/noopener/);
  assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
  console.log('PASS: preview scripts, handlers, forms, nested frames, unsafe links, refresh and external resources stay blocked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

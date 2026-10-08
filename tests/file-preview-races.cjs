// Run only against the disposable scenario fixture, never the user's preview.
const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});
 try {
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');
  await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
  await page.evaluate(async()=>{
   const session=await fetch('/api/session').then(r=>r.json());
   for(const name of ['first.txt','second.txt']){
    const response=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':'plan'},body:JSON.stringify({crewRole:0,name,content:name})});
    if(!response.ok)throw Error('Fixture upload failed');
   }
  });
  await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation.overview);
  await page.locator('.world-room-map [data-world-scenario=plan]').click();
  await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();
  const pending=[];
  await page.route('**/api/file?**',route=>new Promise(resolve=>pending.push(async(fail=false)=>{await route.fulfill(fail?{status:500,json:{error:'Stale file error'}}:{json:{content:new URL(route.request().url()).searchParams.get('path'),encoding:'utf-8',mime:'text/plain'}});resolve();})));
  await page.locator('[data-browse-file="inbox/first.txt"]').click();
  await page.locator('[data-browse-file="inbox/second.txt"]').click();
  await assert.doesNotReject(async()=>{for(let i=0;pending.length<2&&i<100;i++)await page.waitForTimeout(20);assert.equal(pending.length,2);});
  await pending[0]();await page.waitForTimeout(150);
  assert.equal(await page.locator('[data-browse-file="inbox/second.txt"]').count(),1,'First response must not replace the newer file selection');
  await pending[1]();await page.locator('#studio-dialog-body pre').waitFor();
  assert.equal(await page.locator('#studio-dialog-body pre').innerText(),'inbox/second.txt');
  await page.locator('#studio-dialog-close').click();
  await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();
  await page.locator('[data-browse-file="inbox/first.txt"]').click();
  for(let i=0;pending.length<3&&i<100;i++)await page.waitForTimeout(20);
  assert.equal(pending.length,3);
  await page.locator('#studio-dialog-close').click();
  await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();
  await pending[2](true);await page.waitForTimeout(150);
  assert.equal(await page.locator('#studio-alert').isVisible(),false,'Stale file errors must not interrupt a newer dialog');
  assert.equal(await page.locator('#studio-model-connections').count(),1);
  await page.locator('#studio-dialog-close').click();
  await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();
  await page.locator('[data-browse-file="inbox/first.txt"]').click();
  for(let i=0;pending.length<4&&i<100;i++)await page.waitForTimeout(20);
  assert.equal(pending.length,4);await pending[3](true);
  await page.locator('#studio-alert:not([hidden])').waitFor();
  assert.match(await page.locator('#studio-alert').innerText(),/Stale file error/,'Current request failures remain visible');
  assert.deepEqual(errors,[]);
  console.log('PASS: latest file selection wins and stale file errors do not interrupt Settings.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

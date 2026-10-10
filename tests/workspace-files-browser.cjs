// Disposable fixture_scenarios.py only. Uses a fresh browser account.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args:['--enable-unsafe-swiftshader']});
  const page = await browser.newPage({viewport:{width:1500,height:1000}}), errors=[];
  page.on('pageerror', e=>errors.push(e.message));
  async function api(scenario, path, payload) {
    return page.evaluate(async ({scenario,path,payload})=>{
      const session=await fetch('/api/session').then(r=>r.json());
      const response=await fetch('/api/'+path,{method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-BaC-CSRF':session.csrf,'X-BaC-Scenario':scenario},...(payload?{body:JSON.stringify(payload)}:{})});
      if(!response.ok)throw Error(await response.text());
      return response.json();
    },{scenario,path,payload});
  }
  async function choose(scenario){
    await page.locator('.world-room-map [data-world-scenario="'+scenario+'"]').click();
    await page.waitForFunction(s=>BacCampus.inspect().navigation.activeScenario===s&&!BacCampus.inspect().navigation.travelling,scenario);
    await page.locator('#studio-crew-passport').waitFor({state:'visible'});
  }
  const close=()=>page.locator('#studio-dialog-close').click();
  async function files(){await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).click();}
  try {
    await page.goto(process.env.BASE_URL||'http://127.0.0.1:8083');
    await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.version==='SCENARIO TEST FIXTURE');
    await choose('plan');
    assert.equal(await page.locator('.studio-team-utilities').getByRole('button',{name:'Files',exact:true}).isVisible(),false);
    await api('plan','onboard',{name:'File QA',skills:['documents']});
    await api('plan','upload',{name:'personal.md',content:'Personal notes stay personal.'});
    for(const scenario of ['plan','event-brief'])await api(scenario,'upload',{crewRole:0,name:'notes.md',content:scenario+' content'});
    await page.reload();await page.waitForFunction(()=>window.BacCampus?.inspect().navigation.overview);
    for(const scenario of ['plan','event-brief']){
      await choose(scenario);await files();
      assert.equal(await page.locator('#studio-file-workspace').count(),0,'No agent selector in file dialog');
      await page.locator('[data-browse-file="inbox/notes.md"]').click();
      assert.equal(await page.locator('#studio-dialog-body pre').innerText(),scenario+' content');
      const download=page.waitForEvent('download');await page.locator('#studio-download').click();
      const saved=await download;assert.equal(saved.suggestedFilename(),'notes.md');
      assert.equal(await fs.readFile(await saved.path(),'utf8'),scenario+' content');
      await close();await files();
      assert(!await page.locator('[data-browse-file="inbox/personal.md"]').count());
      await close();
    }
    await page.locator('.world-room-map [data-world-room="lounge"]').click();
    await page.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
    await page.locator('#studio-personal-files').click();
    await page.locator('[data-browse-file="inbox/personal.md"]').click();
    assert.equal(await page.locator('#studio-dialog-body pre').innerText(),'Personal notes stay personal.');
    await close();await choose('plan');
    let release,started=false;
    await page.route('**/api/workspace-files?**',async route=>{started=true;await new Promise(resolve=>release=resolve);await route.fulfill({json:{files:[]}});});
    await files();await page.waitForFunction(()=>document.querySelector('#studio-file-status')?.textContent.includes('Loading'));
    while(!started)await new Promise(r=>setTimeout(r,10));
    await close();await page.locator('#studio-config').click();await page.locator('#studio-model-connections').waitFor();
    release();await page.waitForTimeout(300);
    assert.equal(await page.locator('#studio-model-connections').count(),1,'Late file listing cannot replace Settings');
    assert.deepEqual(errors,[]);
    console.log('PASS: personal/team file isolation, same-name scenario downloads, hidden empty button, no agent selector, and late listing after dialog closure.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

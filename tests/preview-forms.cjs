const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--enable-unsafe-swiftshader']});
try{const page=await browser.newPage({viewport:{width:1500,height:1000}}),external=[];
await page.route('https://example.invalid/**',r=>{external.push(r.request().url());return r.abort();});
await page.route('**/api/file?**',r=>r.fulfill({json:{content:`<!doctype html><html><body><form id="local"><label>Name<input id="name" required></label><button>Submit</button></form><p id="result"></p><form id="external" action="https://example.invalid/collect"><button>External submit</button></form><p id="isolation"></p><script>
document.querySelector('#local').addEventListener('submit',event=>{event.preventDefault();document.querySelector('#result').textContent='Hello '+document.querySelector('#name').value;});
let parentBlocked=false,storageBlocked=false;try{void parent.document.body;}catch{parentBlocked=true;}try{localStorage.setItem('qa','1');}catch{storageBlocked=true;}
fetch('https://example.invalid/fetch').then(()=>{document.querySelector('#isolation').textContent='network escaped';}).catch(()=>{document.querySelector('#isolation').textContent=JSON.stringify({parentBlocked,storageBlocked,networkBlocked:true});});
</script></body></html>`}}));
await page.goto(process.env.BAC_TEST_URL||'http://127.0.0.1:18088');await page.waitForFunction(()=>window.BacStudio?.inspect().runtime.testFixture);
await page.evaluate(()=>{const b=document.createElement('button');b.dataset.studioFile='artifacts/form.html';document.querySelector('#agent-campus').append(b);b.click();});
await page.locator('#studio-app-frame[data-ready=true]').waitFor({timeout:5000}).catch(async e=>{console.log(await page.evaluate(()=>({alert:document.querySelector('#studio-alert')?.textContent,dialog:document.querySelector('#studio-dialog')?.outerHTML.slice(0,1300)})));throw e;});const f=page.frameLocator('#studio-app-frame');
await f.getByRole('button',{name:'Submit',exact:true}).click();assert.equal(await f.locator('#result').innerText(),'');
await f.getByLabel('Name').fill('Sam');await f.getByLabel('Name').press('Enter');assert.equal(await f.locator('#result').innerText(),'Hello Sam','Local form submission must run its JavaScript handler');
assert.deepEqual(JSON.parse(await f.locator('#isolation').innerText()),{parentBlocked:true,storageBlocked:true,networkBlocked:true});
await f.getByRole('button',{name:'External submit',exact:true}).click();await page.waitForTimeout(300);
assert.deepEqual(external,[],'CSP must block both fetch and form navigation');assert.equal(new URL(page.url()).origin,new URL(process.env.BAC_TEST_URL||'http://127.0.0.1:18088').origin);
assert.equal(await page.locator('#studio-app-frame').getAttribute('sandbox'),'allow-scripts allow-forms');
console.log('PASS: local form validation/Enter submission work; external fetch/form navigation, parent access and storage stay blocked.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

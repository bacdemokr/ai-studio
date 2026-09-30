const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const source=fs.readFileSync('src/studio-crew.js','utf8');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const page=await browser.newPage();await page.setContent('<div id="lanes"></div>');
  await page.addScriptTag({content:source.slice(source.indexOf('function updateMissionControlTrace('),source.indexOf('function renderMissionControl('))});
  const row=(key,text)=>'<article data-trace-key="'+key+'">'+text+'</article>';
  const result=row('avery','<h4>Delivered</h4><details data-trace-details="output-8"><summary>Avery’s result</summary><p>Preserve this selected evidence.</p><button data-preview-file="test.html">Preview</button></details>');
  const pending=row('review','Reviewing…'),planned=row('riley','Planned');
  const patch=(html,id='first-job')=>page.evaluate(({html,id})=>updateMissionControlTrace(document.getElementById('lanes'),id,html),{html,id});
  await patch(result+pending+planned);await page.locator('summary').click();await page.locator('button').focus();
  await page.evaluate(()=>{window.savedButton=document.activeElement;const range=document.createRange();range.selectNodeContents(document.querySelector('p'));getSelection().removeAllRanges();getSelection().addRange(range);});
  await patch(result+row('review','More work needed')+row('riley','Working'));
  assert.equal(await page.evaluate(()=>document.activeElement===window.savedButton),true);
  assert.equal(await page.evaluate(()=>getSelection().toString()),'Preserve this selected evidence.');
  assert.equal(await page.locator('details').getAttribute('open'),'');
  assert.deepEqual(await page.locator('article').evaluateAll(nodes=>nodes.map(n=>n.dataset.traceKey)),['avery','review','riley']);
  assert.equal(await page.locator('[data-trace-key="riley"]').innerText(),'Working');
  // Updating an earlier card must not detach/refocus a later result either.
  await patch(pending+result+planned);
  await page.locator('button').focus();
  await page.evaluate(()=>{window.savedButton=document.activeElement;});
  await patch(row('review','Review complete')+result+planned);
  assert.equal(await page.evaluate(()=>document.activeElement===window.savedButton),true);
  // Updated cards preserve their expanded result, without accumulating old rows.
  await patch(result.replace('Delivered','Delivered with files')+row('review','Enough to finish')+row('final','Response ready'));
  assert.equal(await page.locator('details').getAttribute('open'),'');
  assert.equal(await page.locator('article').count(),3);
  assert.equal(await page.locator('[data-trace-key="riley"]').count(),0);
  // A new job must not inherit expanded results, cached markup or previous rows.
  await patch(result,'second-job');assert.equal(await page.locator('details').getAttribute('open'),null);
  assert.equal(await page.locator('article').count(),1);
  await patch('','second-job');assert.equal(await page.locator('article').count(),0);
  console.log('PASS: live trace patch preserves focus, selection and expanded results; updates/removes rows and isolates new jobs.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

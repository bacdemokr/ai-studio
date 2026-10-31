// Exercise real Mission Control rendering, async reasoning and modal styles.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const source=fs.readFileSync('src/studio-crew.js','utf8');
const board=fs.readFileSync('src/studio.html','utf8').split('\n').find(line=>line.startsWith('<div id="studio-board"'));
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 for(const height of [900,650]){
  const page=await browser.newPage({viewport:{width:1100,height},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<main id="agent-campus"><dialog id="studio-surface"><header><h2>Mission Control</h2></header><div id="studio-surface-body">'+board+'</div></dialog></main>');
  for(const file of ['src/studio.css','src/studio-rooms.css','src/studio-controls.css'])await page.addStyleTag({content:fs.readFileSync(file,'utf8')});
  await page.addScriptTag({content:`
   const el=id=>document.getElementById('studio-'+id);
   const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
   const messageMarkup=value=>'<p>'+escape(value)+'</p>';
   const planNames=()=>({0:'Casey'}),declinedAssignmentsMarkup=()=>'',webpageButtons=()=>'',collaborationRoleOrder=()=>[];
   const collaborationAnswer=job=>job.result?.answer||'',collaborationTime=()=>'';
   const missionControlPlan=()=>window.job;
   const api=()=>new Promise(resolve=>{window.deliverReasoning=resolve;});
   window.job={id:'fixture',status:'running',payload:{collaboration:{task:'Build a desktop page. '.repeat(90),summary:'Build the page.',tasks:[],checks:[]}}};
  `+source.slice(source.indexOf('function modelReasoningMarkup('),source.indexOf('function collaborationRevisionBody('))});
  await page.evaluate(()=>{el('board').hidden=false;el('surface').showModal();renderMissionControl();});
  const notice=page.locator('#studio-mission-updates'),button=notice.locator('button');
  const visibleInModal=async()=>{
   assert(await button.isVisible(),'Unread update should be announced');
   assert(await button.evaluate(b=>{const r=b.getBoundingClientRect(),v=document.getElementById('studio-surface-body').getBoundingClientRect();return r.top>=v.top&&r.bottom<=v.bottom&&b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),'Update button must be visible and clickable inside the modal');
  };
  // Final output stays unread through later idle polls, with no scroll jump.
  await page.evaluate(()=>{window.job.status='done';window.job.result={answer:'The page is ready.'};renderMissionControl();});
  await visibleInModal();
  await page.evaluate(()=>{renderMissionControl();renderMissionControl();});
  await visibleInModal();
  assert.equal(await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop),0);
  await button.click();assert(await notice.isHidden());
  // Open advanced on the completed task. Provider text arrives afterwards.
  await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop=0);
  await page.locator('#studio-mission-reasoning').click();assert(await notice.isHidden(),'Opening a view alone is not a new update');
  await page.evaluate(()=>window.deliverReasoning({active:false,recorded:true,calls:[{id:'planning',role:0,phase:'Planning',status:'finished',turns:[{index:1,model:'fixture-model',sections:[{kind:'summary',text:'Provider-published text\n'.repeat(60)}]}]}]}));
  await visibleInModal();
  await page.evaluate(()=>{renderMissionControl();renderMissionControl();});await visibleInModal();
  assert.equal(await page.locator('#studio-surface-body').evaluate(e=>e.scrollTop),0);
  await button.focus();await page.keyboard.press('Enter');assert(await notice.isHidden());
  assert.equal(await page.locator('[data-reasoning-scroll]').evaluate(e=>Math.round(e.scrollHeight-e.clientHeight-e.scrollTop)),0);
  // Cached view toggles must not manufacture new updates.
  await page.locator('#studio-mission-reasoning').click();
  await page.locator('#studio-mission-reasoning').click();assert(await notice.isHidden());
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log('PASS: final updates survive idle polls; late reasoning on completed tasks is announced; no automatic scroll; modal button is clickable at both heights; cached toggles stay quiet.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const b=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-unsafe-swiftshader']});try{const p=await b.newPage({viewport:{width:1500,height:1000}}),errors=[],sent=[];p.on('pageerror',e=>(errors.push(e.message),console.error(e.message)));await p.addInitScript(()=>window.setInterval=()=>0);
await p.route(/\/api\/(session|state)$/,async r=>{const response=await r.fetch(),json=await response.json();const profile={name:'Vision',persona:'guide',tone:'kind',verbosity:'balanced',skills:['documents'],protection:'standard',avatar:{body:'classic',color:'green',accessory:'antenna'}};Object.assign(json,{profile,agents:[{...profile,key:json.agentId,pending:false}],jobs:[],runtime:{...json.runtime,ready:true,model:true}});await r.fulfill({response,json})});await p.route('**/api/jobs',r=>{sent.push(r.request().postDataJSON());return r.fulfill({json:{id:'image-test'}})});
await p.goto('http://127.0.0.1:8080');await p.waitForFunction(()=>window.BacStudio?.inspect().profile);
async function assertOverview(){
 for(const id of ['passport','crew-passport','workshop'])assert(await p.locator('#studio-'+id).isHidden(),id+' leaked into overview');
 const dims=await p.locator('.campus-layout').evaluate(e=>({height:e.clientHeight,stage:e.querySelector('.campus-stage').clientHeight}));
 assert(dims.height<=dims.stage+2,JSON.stringify(dims));
}
await assertOverview();
await p.locator('#studio-focus').click();await assertOverview();await p.locator('#studio-focus').click();await assertOverview();
for(const room of ['lounge','mission']){
 await p.locator('.world-room-map [data-world-room='+room+']').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);
 for(const full of [false,true]){
  if(full)await p.locator('#studio-focus').click();await p.waitForTimeout(500);
  const dims=await p.evaluate(room=>{const panel=document.querySelector(room==='lounge'?'#studio-passport':'#studio-crew-passport'),chat=document.querySelector(room==='lounge'?'#studio-conversation':'#studio-crew-conversation'),canvas=document.querySelector('#campus-viewport canvas');return{panel:panel.clientWidth,chat:chat.clientHeight,canvas:canvas.clientHeight,map:getComputedStyle(document.querySelector('.world-room-map')).position,overflow:document.documentElement.scrollWidth>innerWidth}},room);
  assert(dims.panel>=300,JSON.stringify(dims));assert(dims.chat>=100,JSON.stringify(dims));assert(dims.canvas>=300,JSON.stringify(dims));assert.equal(dims.map,'absolute');assert.equal(dims.overflow,false);
  await p.screenshot({path:'../../work/repaired-'+room+'-'+(full?'full':'normal')+'.png'});
 }
 await p.locator('#studio-focus').click();
 await p.locator('button[data-world-overview]').click();await p.waitForFunction(()=>!BacCampus.inspect().navigation.travelling);await assertOverview();
 await p.screenshot({path:'../../work/overview-after-'+room+'.png',fullPage:true});
}
assert.deepEqual(errors,[]);console.log('PASS: room map navigation, 3D canvas, lounge/crew panel and conversation dimensions in normal/fullscreen, no page errors or horizontal overflow.');}finally{await b.close()}})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio.js','utf8');
function fixture(){
 const calls=[],timers=new Set(),alerts=[],opened=[];
 const context={Map,AbortController,JSON,agentId:'a',selectedScenario:'plan',credentialSession:'fixture',csrf:'fixture',
  changingAgent:false,pendingWrites:0,refreshVersion:0,busy:false,removingAgent:false,hiringArrival:false,scenarioSwitching:false,
  setTimeout(fn,ms){const timer={fn,ms};timers.add(timer);return timer;},clearTimeout(timer){timers.delete(timer);},
  alert:message=>alerts.push(message),render(){},
  openAgentState(state){context.agentId=state.agentId;opened.push(state.agentId);},
  fetch(url,options){return new Promise((resolve,reject)=>calls.push({url,options,resolve,reject}));}};
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('const stateCache='),source.indexOf('  function rememberSelection()'))+
  source.slice(source.indexOf('  async function switchAgent('),source.indexOf('  function renderCollection()')),context);
 const reply=(call,body={})=>call.resolve({ok:true,status:200,json:async()=>body,headers:{get:()=>null}});
 const tick=async()=>{for(const timer of [...timers])if(timer.ms===50){timers.delete(timer);timer.fn();}await new Promise(setImmediate);};
 return {context,calls,alerts,opened,reply,tick};
}
(async()=>{
 // Late successes and failures cannot overwrite the last selected workspace.
 for(const staleFails of [false,true]){
  const {context:c,calls,alerts,opened,reply}=fixture();
  const first=c.switchAgent('b'),last=c.switchAgent('c');
  reply(calls[1],{agentId:'c'});await last;
  if(staleFails)calls[0].reject(Error('stale request failed'));else reply(calls[0],{agentId:'b'});
  await first;assert.equal(c.agentId,'c');assert.deepEqual(opened,['c']);assert.deepEqual(alerts,[]);assert.equal(c.changingAgent,false);
 }
 // Returning to the currently displayed agent cancels an unfinished switch.
 {
  const {context:c,calls,opened,reply}=fixture();
  const first=c.switchAgent('b');await c.switchAgent('a');
  reply(calls[0],{agentId:'b'});await first;
  assert.equal(c.agentId,'a');assert.deepEqual(opened,[]);assert.equal(c.changingAgent,false);
 }
 // Preparation belongs to its captured owner and must never block navigation.
 {
  const {context:c,calls,alerts,reply}=fixture();
  const preparation=c.api('prepare-demo',{background:true});
  assert.equal(c.pendingWrites,1);
  const selection=c.switchAgent('b');assert.equal(calls.length,2);
  assert.equal(calls[0].options.headers['X-BaC-Agent'],'a');
  assert.equal(calls[1].options.headers['X-BaC-Agent'],'b');
  reply(calls[1],{agentId:'b'});await selection;
  reply(calls[0],{agentId:'a'});await preparation;
  assert.equal(c.agentId,'b');assert.equal(c.pendingWrites,0);assert.deepEqual(alerts,[]);
 }
 // The final click is retained while a foreground write finishes or fails.
 for(const writeFails of [false,true]){
  const {context:c,calls,alerts,opened,reply,tick}=fixture();
  const save=c.api('jobs',{prompt:'belongs to a'}).catch(()=>{});
  const first=c.switchAgent('b'),last=c.switchAgent('c');
  await tick();assert.equal(calls.length,1);assert.deepEqual(alerts,[]);
  assert.equal(calls[0].options.headers['X-BaC-Agent'],'a');
  if(writeFails)calls[0].reject(Error('save failed'));else reply(calls[0]);
  await save;await tick();assert.equal(calls.length,2);
  assert.equal(calls[1].options.headers['X-BaC-Agent'],'c');
  reply(calls[1],{agentId:'c'});await Promise.all([first,last]);
  assert.deepEqual(opened,['c']);assert.equal(c.pendingWrites,0);assert.equal(c.changingAgent,false);
 }
 // Uploads and multi-step owner/scenario operations keep their workspace until done.
 for(const blocker of ['pendingWrites','removingAgent','hiringArrival','scenarioSwitching']){
  const {context:c,calls,reply,tick}=fixture();c[blocker]=1;
  const selection=c.switchAgent('b');await tick();assert.equal(calls.length,0);
  c[blocker]=0;await tick();assert.equal(calls.length,1);
  reply(calls[0],{agentId:'b'});await selection;assert.equal(c.agentId,'b');
 }
 // Cancel a queued click without creating a delayed, surprising navigation.
 {
  const {context:c,calls,tick}=fixture();c.pendingWrites=1;
  const selection=c.switchAgent('b');await c.switchAgent('a');c.pendingWrites=0;
  await tick();await selection;assert.equal(calls.length,0);assert.equal(c.agentId,'a');
 }
 // New writes stay fenced during state loading; tab presence and owner-scoped
 // background preparation remain safe, including a failed preparation request.
 {
  const {context:c,calls,reply,tick}=fixture();
  const selection=c.switchAgent('b');
  await assert.rejects(c.api('jobs',{}),/workspace/);
  const presence=c.api('credential-session',{});reply(calls[1]);await presence;
  const preparation=c.api('prepare-demo',{background:true}).catch(()=>{});
  assert.equal(c.pendingWrites,1);calls[2].reject(Error('preparation failed'));await preparation;
  assert.equal(c.pendingWrites,0);
  reply(calls[0],{agentId:'b'});await selection;
  const save=c.api('jobs',{}),next=c.switchAgent('c');await tick();assert.equal(calls.length,4);
  reply(calls[3]);await save;await tick();reply(calls[4],{agentId:'c'});await next;
  assert.equal(c.agentId,'c');
 }
 console.log('PASS: latest selection wins, stale responses ignored, background preparation permits navigation, foreground writes retain owner and queued selection.');
})().catch(error=>{console.error(error);process.exitCode=1;});

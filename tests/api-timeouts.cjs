const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const calls=[],timers=[];
const context={Map,AbortController,JSON,agentId:'test',selectedScenario:'plan',credentialSession:'fixture',csrf:'fixture',changingAgent:false,pendingWrites:0,
 setTimeout(fn,ms){const timer={fn,ms};timers.push(timer);return timer;},clearTimeout(timer){if(timer)timer.cleared=true;},
 fetch(url,options){return new Promise((resolve,reject)=>{calls.push({url,options,resolve});options.signal?.addEventListener('abort',()=>reject(Error('aborted')));})}};
vm.createContext(context);
const source=fs.readFileSync('src/studio.js','utf8');
vm.runInContext(source.slice(source.indexOf('const stateCache='),source.indexOf('  function rememberSelection()')),context);
(async()=>{
 for(const [path,delay] of [['session',30000],['state',30000],['agent-policy',45000],['crew-policy?role=1',45000]]){
  const request=context.api(path);assert.equal(timers.at(-1).ms,delay);
  timers.at(-1).fn();await assert.rejects(request,/took too long/);assert(timers.at(-1).cleared);
 }
 const count=timers.length,write=context.api('agent-policy',{permission:'weather',allow:true});
 assert.equal(context.pendingWrites,1);assert.equal(calls.at(-1).options.signal,undefined);assert.equal(timers.length,count);
 calls.at(-1).resolve({ok:true,status:200,json:async()=>({applied:true})});
 assert.equal((await write).applied,true);assert.equal(context.pendingWrites,0);
 console.log('PASS: stalled startup/state/policy reads recover; policy writes are never aborted by read timeouts');
})().catch(error=>{console.error(error);process.exitCode=1;});

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const chat=fs.readFileSync('src/studio-chat.js','utf8'),studio=fs.readFileSync('src/studio.js','utf8');
const input={value:'A draft'},ctx=vm.createContext({input,el:()=>input,agentId:'a'});
vm.runInContext(chat.slice(chat.indexOf('const personalDrafts='),chat.indexOf('const imageKey=')),ctx);
const select=(next,agents=['a','b'])=>vm.runInContext(`restorePersonalDraft(${JSON.stringify(next)},${JSON.stringify(agents.map(key=>({key})))});agentId=${JSON.stringify(next)}`,ctx);
select('b');assert.equal(input.value,'');input.value='B draft';select('a');assert.equal(input.value,'A draft');select('b');assert.equal(input.value,'B draft');
input.value='';select('a');select('b');assert.equal(input.value,''); // sent draft stays cleared
input.value='deleted secret';select('a',['a']);select('b');assert.equal(input.value,''); // deleted owner is forgotten
const apiSource=studio.slice(studio.indexOf('  async function api('),studio.indexOf('  function rememberSelection'));
let resolveFetch;Object.assign(ctx,{credentialSession:'test',csrf:'test',pendingWrites:0,changingAgent:false,stateCache:new Map(),fetch:()=>new Promise(resolve=>resolveFetch=resolve)});
vm.runInContext(apiSource,ctx);
const reply=()=>resolveFetch({ok:true,status:200,json:async()=>({}),headers:{get:()=>null}});
(async()=>{
 let request=vm.runInContext("api('credential-session',{})",ctx);assert.equal(ctx.pendingWrites,0);reply();await request;
 ctx.changingAgent=true;request=vm.runInContext("api('credential-session',{})",ctx);reply();await request;
 await assert.rejects(vm.runInContext("api('jobs',{})",ctx),/workspace/);
 ctx.changingAgent=false;request=vm.runInContext("api('jobs',{})",ctx);assert.equal(ctx.pendingWrites,1);reply();await request;assert.equal(ctx.pendingWrites,0);
 console.log('PASS: per-agent drafts, sent/deleted draft cleanup, presence without navigation lock, real writes remain fenced');
})().catch(e=>{console.error(e);process.exitCode=1});

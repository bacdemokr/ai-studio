import assert from 'node:assert/strict';
import {beforeTool,persistResult} from '../runtime/research-guard/index.mjs';
const agentId='bac-'+'a'.repeat(24);
function context(role, job){return {agentId,sessionKey:`agent:${agentId}:openai-user:bac-plan-${String(job).padStart(24,'0')}-${role}-working`};}
for(const role of [4,5,6,7,8]){
 const ctx=context(role,role);
 const search={toolName:'web_search',params:{query:'public sources',count:100}};
 assert.equal(beforeTool(search,ctx).params.count,3);
 assert.equal(beforeTool(search,ctx).params.count,3);
 assert.equal(beforeTool(search,ctx).block,true);
 assert.equal(beforeTool(search,{...ctx,sessionKey:ctx.sessionKey+'-output-retry'}).block,true);
}
const review=context(4,40);
for(let i=0;i<8;i++)assert.equal(beforeTool({toolName:'read',params:{path:'inbox/source.html',offset:i*120+1,limit:9999}},review).params.limit,120);
assert.equal(beforeTool({toolName:'read',params:{path:'inbox/source.html',offset:1000}},review).block,true);
const coding=context(5,50);
const result=persistResult({toolName:'read',message:{role:'toolResult',content:[{type:'text',text:'x'.repeat(100000)}]}},coding);
assert(result.message.content[0].text.length<7000);
assert.equal(beforeTool({toolName:'write',params:{path:'artifacts/app.html',content:'complete app'}},coding),undefined);
const protectedResearch=context(8,80);
for(let i=0;i<5;i++){
 const params=beforeTool({toolName:'exec',params:{command:'curl approved-host',timeoutSeconds:100,host:'sandbox'}},protectedResearch).params;
 assert.equal(params.timeoutSeconds,40);
 assert.equal(Object.hasOwn(params,'timeout'),false);
 assert.equal(params.host,'sandbox');
}
assert.equal(beforeTool({toolName:'exec',params:{command:'curl approved-host'}},protectedResearch).block,true);
// Reproduce valid/missing timeout arguments and legacy callers; never reinsert
// the unsupported key, disable the cap with zero, or override a shorter request.
const timeouts=[[{},40],[{timeout:100},40],[{timeoutSeconds:25},25],[{timeout:100,timeoutSeconds:12},12],[{timeoutSeconds:0},40],[{timeoutSeconds:NaN},40]];
for(const [i,[input,expected]] of timeouts.entries()){
 const params=beforeTool({toolName:'exec',params:{command:'curl approved-host',...input}},context(8,90+i)).params;
 assert.equal(params.timeoutSeconds,expected);assert.equal(Object.hasOwn(params,'timeout'),false);
}
assert.equal(beforeTool({toolName:'exec',params:{command:'fixture'}},{agentId,sessionKey:'ordinary-personal-chat'}),undefined);
console.log('PASS: hired-agent search/exec budgets, retry sharing, file/review bounds, writes and unrelated session isolation.');

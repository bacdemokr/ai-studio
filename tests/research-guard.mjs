import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {beforeTool,persistResult} from '../runtime/research-guard/index.mjs';
assert.equal(JSON.parse(readFileSync(new URL('../runtime/research-guard/openclaw.plugin.json',import.meta.url))).activation.onStartup,true);
const agentId='bac-'+'a'.repeat(24)+'-r8';let n=0;
const ctx=()=>({agentId,sessionKey:'agent:'+agentId+':openai-user:bac-plan-'+String(++n).padStart(24,'0')+'-8-working'});
const search=(count=3)=>({toolName:'web_search',params:{query:'public facts',count}});
const fetch={toolName:'web_fetch',params:{url:'https://example.com',maxChars:99999}};
let c=ctx();assert.equal(beforeTool(search(99),c).params.count,3);assert.equal(beforeTool(search(),c).params.count,3);assert.equal(beforeTool(search(),c).block,true);assert.equal(beforeTool(fetch,c).block,true);
c=ctx();for(let i=0;i<5;i++)assert.equal(beforeTool(fetch,c).params.maxChars,4000);assert.equal(beforeTool(fetch,c).block,true);
assert.equal(beforeTool({toolName:'write',params:{path:'artifacts/brief.md'}},c),undefined);
assert.equal(beforeTool(fetch,{...c,agentId:'bac-'+'a'.repeat(24)+'-r5'}),undefined);
assert.equal(beforeTool(fetch,{...c,sessionKey:'agent:'+agentId+':ordinary-chat'}),undefined);
c=ctx();const same={...search(),toolCallId:'once'};beforeTool(same,c);beforeTool(same,c);assert.equal(beforeTool(search(),c).block,undefined);assert.equal(beforeTool(search(),c).block,true);
c=ctx();beforeTool(search(),c);beforeTool(search(),c);assert.equal(beforeTool(search(),{...c,sessionKey:c.sessionKey+'-output-retry'}).block,true);
const wrapped='\n<<<EXTERNAL_UNTRUSTED_CONTENT id="a">>>\nSource: Web Search\n---\n'+'facts '.repeat(3000)+'\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id="a">>>';
const msg={role:'toolResult',toolName:'web_search',toolCallId:'tool-1',content:[{type:'text',text:JSON.stringify({provider:'parallel-free',results:Array.from({length:5},(_,i)=>({url:'https://example.com/'+i,title:'Title',snippet:wrapped}))})}]};
const result=persistResult({toolName:'web_search',message:msg},c).message;
assert.equal(result.toolCallId,'tool-1');const body=JSON.parse(result.content[0].text);assert.equal(body.results.length,3);assert.equal(body.results[0].url,'https://example.com/0');assert(body.results[0].snippet.endsWith('<<<END_EXTERNAL_UNTRUSTED_CONTENT id="a">>>'));assert(result.content[0].text.length<6500);assert(body.truncated);
assert.equal(persistResult({toolName:'web_search',message:{...msg,isError:true}},c),undefined);
assert.equal(persistResult({toolName:'read',message:msg},c).message.details.coverageLimited,true);
assert.equal(persistResult({toolName:'web_search',message:msg},{...c,agentId:'unrelated'}),undefined);
// A failed search provider must not prevent the very first official-source read.
const failedSearch=(id,text="Parallel MCP error: You've hit the free-tier rate limit")=>({toolName:'web_search',message:{role:'toolResult',toolName:'web_search',toolCallId:id,isError:true,content:[{type:'text',text}]}});
c=ctx();beforeTool({...search(),toolCallId:'limited'},c);
assert.equal(beforeTool(fetch,c).block,true); // No result yet.
assert.equal(persistResult(failedSearch('limited'),c),undefined); // Keep the original error.
persistResult(failedSearch('limited'),c); // Repeated persistence cannot refund another search.
persistResult(failedSearch('unknown-call'),c);
for(let i=0;i<5;i++)assert.equal(beforeTool({...fetch,toolCallId:'fallback-'+i},c).params.maxChars,4000);
assert.equal(beforeTool(fetch,{...c,sessionKey:c.sessionKey+'-output-retry'}).block,true);
assert.match(beforeTool(fetch,c).blockReason,/not an OpenShell policy denial/);
assert.equal(beforeTool({toolName:'write',params:{path:'artifacts/brief.md'}},c),undefined);
beforeTool({...search(),toolCallId:'second'},c);
assert.equal(beforeTool(fetch,c).block,true);
persistResult(failedSearch('second'),c);
assert.equal(beforeTool(search(),c).block,true); // Failed attempts still count toward the search limit.
for(const [isError,text] of [[false,'rate limit'],[true,'OpenShell policy denial: rate limit'],[true,'Unspecified error']]) {
  c=ctx();beforeTool({...search(),toolCallId:'check'},c);
  const event=failedSearch('check',text);event.message.isError=isError;
  persistResult(event,c);assert.equal(beforeTool(fetch,c).block,true);
}
c=ctx();beforeTool({...search(),toolCallId:'limited'},c);persistResult(failedSearch('limited'),c);
beforeTool({...search(),toolCallId:'success'},c);
persistResult({toolName:'web_search',message:{...msg,toolCallId:'success'}},c);
assert.equal(beforeTool(fetch,c).block,true); // A successful second search restores the stop rule.
const other=ctx();beforeTool({...search(),toolCallId:'limited'},other);
assert.equal(beforeTool(fetch,other).block,true); // Another run cannot inherit a fallback allowance.
console.log('Research bounds: call budgets, retry scope, isolation, excerpt limits and source markers passed.');

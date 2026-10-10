import assert from 'node:assert/strict';
import {beforeTool,persistResult} from '../runtime/research-guard/index.mjs';
const agentId='bac-'+'b'.repeat(24)+'-r1', sessionKey='agent:'+agentId+':openai-user:bac-crew-'+'c'.repeat(24)+'-1';
const ctx={agentId,sessionKey};
const read=path=>({toolName:'read',params:{path}});
const exec=command=>({toolName:'exec',params:{command}});
const cli='python3 skills/bac-event-tools/scripts/event_agent_tools.py ';
for(const event of [read('/sandbox/artifacts/abc-research.json'),read('/sandbox/skills/bac-event-tools/scripts/event_theme_content.py'),exec('cat /sandbox/artifacts/abc-research.json'),exec(cli+'read S1; cat file'),exec('python3 -c "print(1)"')])assert.equal(beforeTool(event,ctx).block,true);
assert.equal(beforeTool(read('/sandbox/inbox/agent-task.json'),ctx).block,undefined);
assert.equal(beforeTool(read('/var/lib/bac/work/inbox/agent-task.json'),ctx).block,true);
for(let i=0;i<2;i++)assert.equal(beforeTool(exec(cli+'read S1 S2'),ctx).params.host,'sandbox');
assert.equal(beforeTool(exec(cli+'read S1'),ctx).block,true);
assert.equal(beforeTool(exec(cli+'evidence S1'),ctx).block,undefined);
assert.equal(beforeTool(exec(cli+'validate-themes'),ctx).block,undefined);
assert.equal(beforeTool({toolName:'write',params:{path:'artifacts/themes.json'}},ctx),undefined);
assert.equal(beforeTool(exec('cat file'),{...ctx,sessionKey:'ordinary-chat'}),undefined);
const recovery={...ctx,sessionKey:sessionKey+'-context-recovery'};
assert.equal(beforeTool(read('/sandbox/inbox/agent-task.json'),recovery).block,undefined);
const msg={toolName:'read',message:{toolCallId:'huge',content:[{type:'text',text:'a'.repeat(30000)}]}};
const result=persistResult(msg,recovery);
assert(result.message.content[0].text.length<6300);
assert.match(result.message.content[0].text,/some content omitted/);
assert.deepEqual(persistResult(msg,recovery),result);
for(let i=0;i<2;i++)persistResult({...msg,message:{...msg.message,toolCallId:'huge'+i}},recovery);
assert.equal(beforeTool(exec(cli+'evidence'),recovery).block,true);
assert.equal(beforeTool(exec(cli+'validate-themes'),recovery).block,undefined);
console.log('PASS: Dylan bulk-read/exec guards, deduplication, command and retained-output bounds, recovery scope and validation access');
let stressCases=0;
for(const suffix of ['', '-context-recovery','-output-recovery']) {
 for(const size of [1,5999,6000,6001,1000000]) {
  const job=String(100+stressCases++).padStart(24,'0');
  const c={agentId,sessionKey:`agent:${agentId}:openai-user:bac-crew-${job}-1${suffix}`};
  let retained=0;
  for(let i=0;i<8;i++) {
   const command=cli+(i%2?'read S1 S2':'search agent');
   const pre=beforeTool({toolName:'exec',toolCallId:'cmd'+i,params:{command}},c);
   if(i>=4)assert.equal(pre.block,true);
   const event={toolName:'exec',message:{toolCallId:'res'+i,content:[{type:'text',text:'X'.repeat(size)},{type:'text',text:'Y'.repeat(size)}]}};
   const out=persistResult(event,c);
   retained+=out.message.content.reduce((n,b)=>n+b.text.split('\n[Event excerpt')[0].length,0);
   assert.deepEqual(persistResult(event,c),out);
  }
  assert(retained<=18000);
  const validation={toolName:'exec',toolCallId:'validate',params:{command:cli+'validate-themes'}};
  assert.equal(beforeTool(validation,c).block,undefined);
  assert(persistResult({toolName:'exec',message:{toolCallId:'validate',content:[{type:'text',text:'Valid themes'}]}},c).message.content[0].text.includes('Valid themes'));
 }
}
console.log(`PASS: ${stressCases} event stress cases across both recovery modes, megabyte multi-block results and validation after budget exhaustion.`);

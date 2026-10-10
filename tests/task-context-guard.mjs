import assert from 'node:assert/strict';
import {beforeTool,persistResult} from '../runtime/research-guard/index.mjs';
let serial=1000, cases=0;
function context(role,kind='plan',phase='working') {
 const agentId='bac-'+'d'.repeat(24)+'-r'+role;
 return {agentId,sessionKey:`agent:${agentId}:openai-user:bac-${kind}-${String(++serial).padStart(24,'0')}-${role}${kind==='plan'?'-'+phase:''}`};
}
const read=(path='inbox/large.txt',limit=999999)=>({toolName:'read',params:{path,limit}});
for (const [kind,roles] of [['plan',[0,1,2,3,5,6,7,8]],['crew',[0,2,3]]]) {
 for (const role of roles) for (const size of [0,100,6000,6001,100000,1000000]) {
  const ctx=context(role,kind);
  const first={...read(),toolCallId:'first'};
  assert.equal(beforeTool(first,ctx).params.limit,120);
  assert.deepEqual(beforeTool(first,ctx),beforeTool(first,ctx));
  let retained=0;
  for(let i=0;i<6;i++) {
   const message={toolCallId:'output-'+i,content:[{type:'text',text:'A'.repeat(size)},{type:'text',text:'B'.repeat(size)}],details:{raw:'X'.repeat(size)}};
   const event={toolName:i%2?'exec':'read',message};
   const result=persistResult(event,ctx);
   assert.deepEqual(persistResult(event,ctx),result,'persistence is idempotent');
   const saved=result?.message || message;
   retained+=saved.content.reduce((n,b)=>n+b.text.split('\n[Task excerpt')[0].length,0);
   if(result) {assert.equal(saved.details.coverageLimited,true);assert(!saved.details.raw);}
  }
  assert(retained<=24000,`${kind} role ${role}: ${retained}`);
  if(retained===24000) assert.equal(beforeTool(read(),ctx).block,true);
  assert.equal(beforeTool({toolName:'write',params:{path:'artifacts/result.html'}},ctx),undefined);
  assert.equal(beforeTool({toolName:'edit',params:{}},ctx),undefined);
  assert.equal(beforeTool(read('/tmp/openclaw-web-fetch-aabb.log'),ctx).block,true);
  cases++;
 }
}
for(const phase of ['planning','working','checking-5','reviewing','revising','finalizing','working-output-retry']) {
 const ctx=context(5,'plan',phase);
 for(let i=0;i<16;i++)assert.equal(beforeTool(read('inbox/file'+i),ctx).block,undefined);
 assert.equal(beforeTool(read(),ctx).block,true);
 assert.equal(beforeTool(read(),context(5)).block,undefined,'new job gets a fresh budget');
 cases++;
}
const ctx=context(5);
assert.equal(beforeTool(read(),{...ctx,sessionKey:'ordinary-chat'}),undefined);
assert.equal(beforeTool(read(),{...ctx,agentId:'unrelated'}),undefined);
assert.equal(beforeTool(read(),{...ctx,agentId:ctx.agentId.replace('-r5','-r6')}),undefined);
console.log(`PASS: ${cases} task-context stress cases; multi-block megabyte outputs, all applicable roles/phases, total limits, idempotence, writes/edits and session isolation.`);
for(const text of ['한글 내용 '.repeat(10000),'日本語の資料'.repeat(10000),'🙂'.repeat(30000)]) {
 for(const [kind,role] of [['plan',5],['plan',4],['crew',1]]) {
  const ctx=context(role,kind), result=persistResult({toolName:'read',message:{toolCallId:'unicode',content:[{type:'text',text}]}},ctx);
  const excerpt=result.message.content[0].text.split('\n[')[0];
  assert(Buffer.byteLength(excerpt)<=6000);assert(!excerpt.includes('\uFFFD'));
 }
}
console.log('PASS: 9 multilingual/emoji output-bound cases without broken Unicode.');

for(const suffix of ['-social','-page-repair-1','-page-repair-3','-page-repair-1-output-recovery']) {
 const ctx=context(3,'crew');ctx.sessionKey+=suffix;
 assert.equal(beforeTool(read(),ctx).params.limit,120);
 const result=persistResult({toolName:'read',message:{content:[{type:'text',text:'X'.repeat(100000)}]}},ctx);
 assert.equal(result.message.details.coverageLimited,true);
}
console.log('PASS: 4 Morgan social/page-repair session variants remain bounded.');

for(const [kind,role] of [['plan',5],['plan',4],['crew',1]]) {
 const ctx=context(role,kind);
 const result=persistResult({toolName:'read',message:{content:Array.from({length:10000},()=>({type:'text',text:'X'.repeat(1000)}))}},ctx);
 assert(result.message.content.reduce((n,b)=>n+Buffer.byteLength(b.text),0)<6300,'omission notices cannot multiply past the budget');
}
console.log('PASS: 3 ten-thousand-block stress cases keep omission notices bounded.');

for(const [kind,role] of [['plan',5],['plan',4],['crew',1]]) {
 const ctx=context(role,kind),result=persistResult({toolName:'read',message:{isError:true,content:[{type:'text',text:'Failed: '+('X'.repeat(1000000))}]}},ctx);
 assert.equal(result.message.isError,true);
 assert(result.message.content[0].text.length<6300);
}
console.log('PASS: 3 megabyte-sized failure results preserve error status within the budget.');
for(const [kind,role] of [['plan',4],['plan',5],['crew',1],['crew',3]]) {
 for(const toolName of ['read','write','edit']) for(const key of ['path','file_path']) {
  const ctx=context(role,kind),prefix='var/lib/bac/studio/workspaces/'+'d'.repeat(24)+'-'+role+'/';
  const params={[key]:prefix+'artifacts/result.md',content:'Preserve authored text',oldText:'before',newText:'after'};
  const result=beforeTool({toolName,params},ctx);
  assert.equal(result.params[key],'artifacts/result.md');
  assert.equal(result.params.content,'Preserve authored text');
  const other=context(role,kind);
  const foreign={toolName,params:{[key]:prefix.replace('d'.repeat(24),'e'.repeat(24))+'artifacts/result.md'}};
  const untouched=beforeTool(foreign,other);
  assert(!untouched || untouched.params?.[key]===foreign.params[key]);
 }
}
console.log('PASS: 24 owned-workspace path corrections preserve content and never map another owner.');

for(const [kind,role] of [['plan',5],['plan',4],['crew',1]]) {
 const ctx=context(role,kind),result=persistResult({toolName:'read',message:{isError:true,content:[{type:'text',text:'E'.repeat(100000)}],details:{status:'error',exitCode:1,durationMs:42,raw:'X'.repeat(100000)}}},ctx);
 assert.equal(result.message.details.exitCode,1);assert.equal(result.message.details.status,'error');assert.equal(result.message.details.durationMs,42);assert.equal(result.message.details.raw,undefined);
}
console.log('PASS: 3 bounded error responses preserve failure/exit metadata without retaining raw output.');

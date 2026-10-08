// Exercise the shipped dispatcher with deterministic queue and transport failures.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio-compare.js','utf8');
const implementation=source.slice(source.indexOf('let comparisonRead='));
async function scenario(mode){
 let pending=0,maximum=0,acked=0,waits=0;
 const accepted=new Map(),attempts=new Map(),jobs=new Map();
 const context=vm.createContext({comparison:null,comparisonTimer:null,comparisonSending:false,
  runtime:{ready:true},data:{agents:Array.from({length:12},(_,i)=>({key:'agent-'+i,name:'Agent '+i}))},
  el:()=>({value:'Hello'}),syncComposer(){},drawComparison(){},pendingImages:()=>[],
  captureChatDraft:()=>({images:[]}),acknowledgeChatDraft(){acked++;},refresh:async()=>{},clearTimeout,
  setTimeout(callback){waits++;if(mode==='cancel')context.comparison=null;return setTimeout(callback,0);},
  api:async(path,payload,key)=>{
   if(path==='state'){
    const job=jobs.get(key);if(job?.status==='queued'){job.status='done';pending--;}
    return {jobs:job?[job]:[]};
   }
   attempts.set(key,(attempts.get(key)||0)+1);
   if(mode==='network'&&key==='agent-0')throw new Error('Response lost; acceptance unknown');
   if(mode==='foreign-full'||pending>=3)throw Object.assign(new Error('Queue full'),{status:429});
   assert(!accepted.has(key),'No duplicate accepted job for '+key);
   const job={id:key+'-job',status:'queued',result:{answer:key}};
   jobs.set(key,job);accepted.set(key,job);pending++;maximum=Math.max(maximum,pending);return job;
  }});
 const chat=fs.readFileSync('src/studio-chat.js','utf8');
 vm.runInContext(chat.slice(chat.indexOf('const isPlanCommand='),chat.indexOf('function syncComposer('))+implementation,context);
 await context.askAllAgents();
 await context.pollComparison(false);
 assert.equal(context.comparisonSending,false);
 assert(maximum<=3,'Preserve the server concurrency limit');
 if(mode==='cancel'){
  assert.equal(accepted.size,3,'Reset stops dispatch of the remaining nine agents');
  assert.equal(context.comparison,null);assert.equal(acked,0);
 }else if(mode==='foreign-full'){
  assert.equal(accepted.size,0);assert.equal(waits,0,'No endless retry behind unrelated work');
  assert(context.comparison.rows.every(r=>r.status==='error'));assert.equal(acked,0);
 }else{
  assert.equal(accepted.size,mode==='network'?11:12);
  assert.equal(acked,1);
  for(const row of context.comparison.rows)assert.equal(row.status,mode==='network'&&row.key==='agent-0'?'error':'done');
  if(mode==='network')assert.equal(attempts.get('agent-0'),1,'Never replay an uncertain POST');
 }
}
(async()=>{for(const mode of ['normal','cancel','network','foreign-full'])await scenario(mode);console.log('PASS: 12-agent queue, reset while waiting, no network retry, and visible rejection when unrelated work fills every slot.');})().catch(error=>{console.error(error);process.exitCode=1;});

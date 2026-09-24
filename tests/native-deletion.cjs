// Exercise the real helper's routing/failure handling against a synthetic pinned runtime.
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'bac-delete-helper-')),id='bac-'+'a'.repeat(24),helper=path.resolve('scripts/delete_native_agent.mjs');
const pkg=path.join(root,'package/node_modules/openclaw'),dist=path.join(pkg,'dist'),workspace=path.join(root,'workspace'),config=path.join(root,'config.json'),trace=path.join(root,'trace');
try{
 fs.mkdirSync(dist,{recursive:true});fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'2026.9.4'}));
 fs.writeFileSync(path.join(dist,'call-fixture.mjs'),`
 import fs from 'node:fs/promises';
 async function callGateway(options){
  await fs.appendFile(process.env.TEST_TRACE,'rpc\\n');
  if(options.method==='sessions.list'){
   if(options.params.agentId!=='${id}'||!options.params.activeOnly)throw Error('Unscoped session query');
   const trace=await fs.readFile(process.env.TEST_TRACE,'utf8');
   return {sessions:trace.includes('abort\\n')?[]:[{key:'agent:${id}:heartbeat-radar:heartbeat'}]};
  }
  if(options.method==='sessions.abort'){
   if(options.params.agentId!=='${id}'||options.params.key!=='agent:${id}:heartbeat-radar:heartbeat'||!options.params.clearQueued)throw Error('Unscoped abort');
   await fs.appendFile(process.env.TEST_TRACE,'abort\\n');return {ok:true};
  }
  if(options.method==='agents.list'){if(options.requiredMethods[0]!=='agents.list')throw Error('Missing list requirement'); return {agents:[]};}
  if(options.method!=='agents.delete'||options.params.deleteFiles!==true||options.clientName!=='cli'||options.requiredMethods[0]!=='agents.delete')throw Error('Unexpected request');
  if(options.timeoutMs!==60000)throw Error('Deletion must explicitly outwait native cleanup');
  const mode=process.env.TEST_MODE;
  if(mode==='slow-success')await new Promise(resolve=>setTimeout(resolve,11000));
  if(['lost-reply-completed','fallback-completed','late-completed'].includes(mode)){
   if(mode==='lost-reply-completed')await fs.rm(process.env.TEST_WORKSPACE,{recursive:true,force:true});
   if(mode==='lost-reply-completed')await fs.writeFile(process.env.OPENCLAW_CONFIG_PATH,JSON.stringify({agents:{entries:{}}}));
   throw Object.assign(Error('closed'),{transport:true,kind:'closed'});
  }
  if(['timeout','closed','closed-after-connect','auth','denied'].includes(mode))throw Object.assign(Error(mode),{transport:mode!=='auth'&&mode!=='denied',kind:mode==='timeout'?'timeout':'closed',code:mode==='closed-after-connect'?1006:undefined,auth:mode==='auth'});
  if(!['retained','partial'].includes(mode))await fs.rm(process.env.TEST_WORKSPACE,{recursive:true,force:true});
  if(mode==='malformed')return {ok:true,agentId:options.params.agentId};
  return {ok:true,agentId:mode==='wrong-id'?'another-agent':options.params.agentId,failed:mode==='partial'?[{reason:'storage error'}]:[]};
 }
 function isGatewayCredentialsRequiredError(error){return error.auth===true;}
 export {callGateway as c,isGatewayCredentialsRequiredError as a};
 `);
 fs.writeFileSync(path.join(dist,'agent-deletion-journal-fixture.mjs'),`
 function readAgentDeletionJournal(agentId){
  if(!['lost-reply-completed','fallback-completed','late-completed','already-completed','incomplete-journal','retained-completed','metadata-only'].includes(process.env.TEST_MODE))return;
  return {agentId,cleanupCompleted:process.env.TEST_MODE!=='incomplete-journal',deleteFiles:process.env.TEST_MODE!=='metadata-only',workspaceDir:process.env.TEST_WORKSPACE,agentDir:process.env.TEST_WORKSPACE+'/agent',sessionsDir:process.env.TEST_WORKSPACE+'/sessions'};
 }
 export {readAgentDeletionJournal as r};
 `);
 fs.writeFileSync(path.join(dist,'transport-error-fixture.mjs'),`function isGatewayTransportError(error){return error.transport===true;} export {isGatewayTransportError as t};`);
 fs.writeFileSync(path.join(dist,'runtime-fixture.mjs'),`function createNonExitingRuntime(){return {exit(){throw Error('Native CLI exit');}};} export {createNonExitingRuntime as n};`);
 fs.writeFileSync(path.join(dist,'agents.commands.delete-fixture.mjs'),`
 import fs from 'node:fs/promises';
 await fs.appendFile(process.env.TEST_TRACE,'load-local\\n');
 if(process.env.TEST_MODE==='fallback-completed'){
  await fs.rm(process.env.TEST_WORKSPACE,{recursive:true,force:true});
  await fs.writeFile(process.env.OPENCLAW_CONFIG_PATH,JSON.stringify({agents:{entries:{}}}));
 }

 export async function agentsDeleteCommand(options,runtime){
  await fs.appendFile(process.env.TEST_TRACE,'local\\n');
  if(process.env.TEST_MODE==='late-completed'){
   await fs.rm(process.env.TEST_WORKSPACE,{recursive:true,force:true});
   await fs.writeFile(process.env.OPENCLAW_CONFIG_PATH,JSON.stringify({agents:{entries:{}}}));
   runtime.writeJson({ok:false,error:{type:'cli_error',message:'Already deleted'}});runtime.exit(1);
  }
  if(['retained-completed','metadata-only'].includes(process.env.TEST_MODE))throw Error('Completed native journal cannot delete retained paths');
  await fs.rm(process.env.TEST_WORKSPACE,{recursive:true,force:true});
  runtime.writeJson({agentId:options.id,failed:[]});
 }
 `);
 for(const mode of ['success','slow-success','closed','auth','journal','timeout','closed-after-connect','denied','wrong-id','malformed','retained','partial','lost-reply-completed','fallback-completed','late-completed','already-completed','incomplete-journal','retained-completed','metadata-only']){
  fs.mkdirSync(workspace,{recursive:true});fs.writeFileSync(path.join(workspace,'memory.txt'),'synthetic');fs.writeFileSync(trace,'');
  fs.writeFileSync(config,JSON.stringify({agents:{entries:['journal','already-completed','incomplete-journal','retained-completed','metadata-only'].includes(mode)?{}:{[id]:{workspace}}}}));
  if(['already-completed','incomplete-journal','metadata-only'].includes(mode))fs.rmSync(workspace,{recursive:true});
  const result=spawnSync(process.execPath,[helper,root,id],{encoding:'utf8',timeout:mode==='slow-success'?15000:8000,env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_MODE:mode,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
  const calls=fs.readFileSync(trace,'utf8').trim().split('\n');
  if(['retained-completed','metadata-only'].includes(mode)){
   assert.notEqual(result.status,0);assert.deepEqual(calls,['load-local','local']);
   assert.equal(fs.existsSync(workspace),mode==='retained-completed');
  }else if(['timeout','closed-after-connect','denied','wrong-id','malformed'].includes(mode)){
   assert.notEqual(result.status,0,mode);assert.deepEqual(calls,['rpc'],'Uncertain or denied deletion must not run a second cleanup');
  }else{
   assert.equal(result.status,0,result.stderr);const report=JSON.parse(result.stdout);assert.equal(report.agentId,id);
   if(['closed','auth','journal','retained-completed','metadata-only'].includes(mode))assert.deepEqual(calls,['journal','incomplete-journal','retained-completed','metadata-only'].includes(mode)?['load-local','local']:['rpc','load-local','local']);
   else if(mode==='fallback-completed')assert.deepEqual(calls,['rpc','load-local'],'Recheck completion after loading the fallback');
   else if(mode==='late-completed')assert.deepEqual(calls,['rpc','load-local','local'],'Late CLI exit must reconcile one JSON result');
   else if(mode==='already-completed')assert.deepEqual(calls,[''],'Completed deletion must not run again');
   else assert.deepEqual(calls,['rpc'],'Running gateway must not load the full cleanup command');
   if(['already-completed','lost-reply-completed','fallback-completed','late-completed'].includes(mode))assert.equal(report.transport,'completed-journal');
   assert.equal(!!report.workspaceRetained,['retained','partial'].includes(mode));
   assert.equal(!!report.failed.length,mode==='partial');
   assert.equal(fs.existsSync(path.join(workspace,'memory.txt')),['retained','partial'].includes(mode));
  }
 }
 for(const mode of ['already-completed','incomplete-journal','retained-completed']){
  fs.rmSync(workspace,{recursive:true,force:true});
  if(mode==='retained-completed')fs.mkdirSync(workspace,{recursive:true});
  fs.writeFileSync(config,JSON.stringify({agents:{entries:{}}}));fs.writeFileSync(trace,'');
  const check=spawnSync(process.execPath,[helper,root,id,'--confirm-deleted'],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_MODE:mode,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
  assert.equal(check.status,mode==='already-completed'?0:2,check.stderr);
  assert.equal(fs.readFileSync(trace,'utf8'),'','Confirmation must never call either deletion path');
  if(check.status===0)assert.equal(JSON.parse(check.stdout).alreadyDeleted,true);
 }
 fs.mkdirSync(workspace,{recursive:true});fs.writeFileSync(path.join(workspace,'memory.txt'),'keep');fs.writeFileSync(trace,'');
 const listed=spawnSync(process.execPath,[helper,root,'--list'],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
 assert.equal(listed.status,0,listed.stderr);assert.deepEqual(JSON.parse(listed.stdout),{agents:[]});
 assert.equal(fs.readFileSync(path.join(workspace,'memory.txt'),'utf8'),'keep');assert.equal(fs.readFileSync(trace,'utf8'),'rpc\n');
 fs.writeFileSync(trace,'');
 const quiet=spawnSync(process.execPath,[helper,root,id,'--quiesce'],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
 assert.equal(quiet.status,0,quiet.stderr);assert.equal(JSON.parse(quiet.stdout).quiescent,true);
 assert.deepEqual(fs.readFileSync(trace,'utf8').trim().split('\n'),['rpc','rpc','abort','rpc']);
 assert.equal(fs.readFileSync(path.join(workspace,'memory.txt'),'utf8'),'keep','Draining must not delete files');
 fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'unexpected'}));fs.writeFileSync(trace,'');
 const rejected=spawnSync(process.execPath,[helper,root,id],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace}});
 assert.notEqual(rejected.status,0);assert.equal(fs.readFileSync(trace,'utf8'),'');
 console.log('PASS: gateway fast path; completed-journal recovery after lost replies and during fallback load; idempotent retry; incomplete/retained journals not accepted; no uncertain cleanup replay; version gate. Synthetic runtime only.');
}finally{fs.rmSync(root,{recursive:true,force:true});}

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
  if(options.method==='agents.list'){if(options.requiredMethods[0]!=='agents.list')throw Error('Missing list requirement'); return {agents:[]};}
  if(options.method!=='agents.delete'||options.params.deleteFiles!==true||options.clientName!=='cli'||options.requiredMethods[0]!=='agents.delete')throw Error('Unexpected request');
  const mode=process.env.TEST_MODE;
  if(['timeout','closed','closed-after-connect','auth','denied'].includes(mode))throw Object.assign(Error(mode),{transport:mode!=='auth'&&mode!=='denied',kind:mode==='timeout'?'timeout':'closed',code:mode==='closed-after-connect'?1006:undefined,auth:mode==='auth'});
  if(!['retained','partial'].includes(mode))await fs.rm(process.env.TEST_WORKSPACE,{recursive:true});
  if(mode==='malformed')return {ok:true,agentId:options.params.agentId};
  return {ok:true,agentId:mode==='wrong-id'?'another-agent':options.params.agentId,failed:mode==='partial'?[{reason:'storage error'}]:[]};
 }
 function isGatewayCredentialsRequiredError(error){return error.auth===true;}
 export {callGateway as c,isGatewayCredentialsRequiredError as a};
 `);
 fs.writeFileSync(path.join(dist,'transport-error-fixture.mjs'),`function isGatewayTransportError(error){return error.transport===true;} export {isGatewayTransportError as t};`);
 fs.writeFileSync(path.join(dist,'agents.commands.delete-fixture.mjs'),`
 import fs from 'node:fs/promises';
 await fs.appendFile(process.env.TEST_TRACE,'load-local\\n');
 export async function agentsDeleteCommand(options){
  await fs.appendFile(process.env.TEST_TRACE,'local\\n');
  await fs.rm(process.env.TEST_WORKSPACE,{recursive:true});
  console.log(JSON.stringify({agentId:options.id,failed:[]}));
 }
 `);
 for(const mode of ['success','closed','auth','journal','timeout','closed-after-connect','denied','wrong-id','malformed','retained','partial']){
  fs.mkdirSync(workspace,{recursive:true});fs.writeFileSync(path.join(workspace,'memory.txt'),'synthetic');fs.writeFileSync(trace,'');
  fs.writeFileSync(config,JSON.stringify({agents:{entries:mode==='journal'?{}:{[id]:{workspace}}}}));
  const result=spawnSync(process.execPath,[helper,root,id],{encoding:'utf8',timeout:8000,env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_MODE:mode,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
  const calls=fs.readFileSync(trace,'utf8').trim().split('\n');
  if(['timeout','closed-after-connect','denied','wrong-id','malformed'].includes(mode)){
   assert.notEqual(result.status,0,mode);assert.deepEqual(calls,['rpc'],'Uncertain or denied deletion must not run a second cleanup');
  }else{
   assert.equal(result.status,0,result.stderr);const report=JSON.parse(result.stdout);assert.equal(report.agentId,id);
   if(['closed','auth','journal'].includes(mode))assert.deepEqual(calls,mode==='journal'?['load-local','local']:['rpc','load-local','local']);
   else assert.deepEqual(calls,['rpc'],'Running gateway must not load the full cleanup command');
   assert.equal(!!report.workspaceRetained,['retained','partial'].includes(mode));
   assert.equal(!!report.failed.length,mode==='partial');
   assert.equal(fs.existsSync(path.join(workspace,'memory.txt')),['retained','partial'].includes(mode));
  }
 }
 fs.mkdirSync(workspace,{recursive:true});fs.writeFileSync(path.join(workspace,'memory.txt'),'keep');fs.writeFileSync(trace,'');
 const listed=spawnSync(process.execPath,[helper,root,'--list'],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace,TEST_WORKSPACE:workspace}});
 assert.equal(listed.status,0,listed.stderr);assert.deepEqual(JSON.parse(listed.stdout),{agents:[]});
 assert.equal(fs.readFileSync(path.join(workspace,'memory.txt'),'utf8'),'keep');assert.equal(fs.readFileSync(trace,'utf8'),'rpc\n');
 fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'unexpected'}));fs.writeFileSync(trace,'');
 const rejected=spawnSync(process.execPath,[helper,root,id],{encoding:'utf8',env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace}});
 assert.notEqual(rejected.status,0);assert.equal(fs.readFileSync(trace,'utf8'),'');
 console.log('PASS: gateway fast path; offline/journal fallback; no timeout, denial or ambiguous-disconnect retries; partial/shared storage retained; version gate. Synthetic runtime only.');
}finally{fs.rmSync(root,{recursive:true,force:true});}

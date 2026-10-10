// Real helper with a disposable pinned runtime. No credentials or live writes.
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'bac-config-helper-')),pkg=path.join(root,'package/node_modules/openclaw'),dist=path.join(pkg,'dist'),trace=path.join(root,'trace');
try {
 fs.mkdirSync(dist,{recursive:true});fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'2026.9.4'}));
 fs.writeFileSync(path.join(dist,'call-fixture.mjs'),`
 import fs from 'node:fs';
 async function callGateway(o) {
  const seen=fs.existsSync(process.env.TEST_TRACE)?fs.readFileSync(process.env.TEST_TRACE,'utf8'):'';
  fs.appendFileSync(process.env.TEST_TRACE,o.method+'\\n');
  if(o.mode!=='cli'||o.clientName!=='cli'||o.requiredMethods[0]!==o.method||o.timeoutMs<30000)throw Error('Invalid options');
  const mode=process.env.TEST_MODE;
  if(o.method==='config.get') {
   if(mode==='denied')throw Error('private-credential');
   if(mode==='read-retry'&&!seen)throw Object.assign(Error('private-credential'),{transport:true});
   return mode==='missing-hash'?{}:{hash:'revision'};
  }
  if(o.method!=='config.patch'||o.params.baseHash!=='revision'||o.params.replacePaths[0]!=='agents.entries'||JSON.parse(o.params.raw).private!=='private-credential')throw Error('Bad write');
  if(mode==='lost-reply')throw Object.assign(Error('private-credential'),{transport:true});
  return mode==='rejected'?{ok:false}:mode==='malformed'?{}:{ok:true,config:{private:'private-credential'}};
 }
 export {callGateway as c};
 `);
 fs.writeFileSync(path.join(dist,'transport-error-fixture.mjs'),`function isGatewayTransportError(e){return e.transport===true;} export {isGatewayTransportError as t};`);
 for(const mode of ['success','read-retry','denied','missing-hash','lost-reply','rejected','malformed','wrong-version']) {
  fs.rmSync(trace,{force:true});
  if(mode==='wrong-version')fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'other'}));
  const result=spawnSync(process.execPath,['scripts/native_config_patch.mjs',root],{input:JSON.stringify({patch:{private:'private-credential'},replacePaths:['agents.entries']}),encoding:'utf8',env:{...process.env,TEST_MODE:mode,TEST_TRACE:trace},timeout:5000});
  const calls=fs.existsSync(trace)?fs.readFileSync(trace,'utf8').trim().split('\n'):[];
  assert(!String(result.stdout+result.stderr).includes('private-credential'),mode+' leaks credential');
  if(['success','read-retry'].includes(mode)){assert.equal(result.status,0);assert.deepEqual(JSON.parse(result.stdout),{ok:true});}
  else assert.equal(result.status,1,mode);
  assert.equal(calls.filter(m=>m==='config.patch').length,['denied','missing-hash','wrong-version'].includes(mode)?0:1,mode+' replays write');
  if(mode==='read-retry')assert.deepEqual(calls,['config.get','config.get','config.patch']);
 }
 console.log('PASS: acknowledged revision-checked patch, read recovery, no uncertain write replay, version guard and sanitized output.');
} finally {fs.rmSync(root,{recursive:true,force:true});}

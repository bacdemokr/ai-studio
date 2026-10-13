// Optional integration against the installed, pinned OpenClaw package.
// Uses an isolated empty configuration and prints one marker, with no model/network.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {beforeTool} from '../runtime/research-guard/index.mjs';
const root=path.resolve(process.argv[2]||'../../work/studio-preview/openclaw/package/node_modules/openclaw');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'bac-exec-contract-'));
process.env.OPENCLAW_STATE_DIR=temp;process.env.OPENCLAW_CONFIG_PATH=path.join(temp,'config.json');
await fs.writeFile(process.env.OPENCLAW_CONFIG_PATH,'{}');
try{
 const dist=path.join(root,'dist'),files=await fs.readdir(dist);let factory;
 for(const file of files.filter(f=>/^bash-tools-[^.]+\.mjs$/.test(f))){
  const source=await fs.readFile(path.join(dist,file),'utf8'),match=source.match(/createExecTool as (\w+)/);
  if(match){factory=(await import(pathToFileURL(path.join(dist,file)).href))[match[1]];break;}
 }
 assert(factory,'Pinned runtime exec factory must exist');
 const tool=factory({host:'gateway',security:'full',ask:'off',cwd:temp,config:{},allowBackground:false});
 const base={title:'Verify exec arguments',command:'/usr/bin/printf BAC_EXEC_OK',workdir:temp,host:'gateway'};
 await assert.rejects(tool.execute('old',{...base,timeout:20}),/timeout.*unsupported.*timeoutSeconds/);
 const agentId='bac-'+'a'.repeat(24),ctx={agentId,sessionKey:`agent:${agentId}:openai-user:bac-plan-${'b'.repeat(24)}-8-working`};
 for(const params of [base,{...base,timeoutSeconds:40},{...base,timeout:20}]){
  const guarded=beforeTool({toolName:'exec',params},ctx).params;
  assert(!Object.hasOwn(guarded,'timeout'));assert(guarded.timeoutSeconds<=40);
  assert(tool.parameters.properties.timeoutSeconds);
  const result=await tool.execute('fixed-'+guarded.timeoutSeconds,guarded);
  assert.equal(result.details.exitCode,0);
  assert(result.content.some(b=>b.text?.includes('BAC_EXEC_OK')));
 }
 console.log('PASS: actual pinned OpenClaw rejects legacy timeout and executes guarded missing/current/legacy arguments. No model or OpenShell used.');
}finally{await fs.rm(temp,{recursive:true,force:true});}

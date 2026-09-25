// Real pinned registry + Gateway load hook, isolated from all preview data.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {retireOwnedTasks} from '../scripts/native_cleanup_tasks.mjs';
const id='bac-'+'a'.repeat(24),other='bac-'+'b'.repeat(24);
let removed=[];
assert.throws(()=>retireOwnedTasks(id,()=>[{agentId:id,status:'running'}],()=>false,x=>removed.push(x)));
assert.deepEqual(removed,[]);
assert.throws(()=>retireOwnedTasks(id,()=>[{agentId:other,status:'succeeded'}],()=>true,x=>removed.push(x)));
assert.deepEqual(removed,[]);
assert.throws(()=>retireOwnedTasks(id,()=>[{agentId:id,status:'succeeded',taskId:'x'}],()=>true,()=>false));
const installed=process.argv[2]&&path.resolve(process.argv[2]);
if(!installed)throw Error('Pass the installed private OpenClaw root');
const temp=fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()),'bac-task-retirement-'));
try {
 fs.symlinkSync(path.join(installed,'package'),path.join(temp,'package'));
 fs.mkdirSync(path.join(temp,'state'));fs.mkdirSync(path.join(temp,'deletion-receipts'));
 const config=path.join(temp,'state/openclaw.json');
 fs.writeFileSync(config,JSON.stringify({agents:{ownership:'explicit',entries:{[id]:{workspace:path.join(temp,'workspace')},[other]:{workspace:path.join(temp,'other')}}}}));
 fs.writeFileSync(path.join(temp,'deletion-receipts',id+'.json'),JSON.stringify({agentId:id,token:'c'.repeat(64)}));
 const loader=new URL('../scripts/native_cleanup_loader.mjs',import.meta.url).href;
 const code=`
 import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
 const dist=path.join(process.argv[1],'package/node_modules/openclaw/dist');
 async function api(prefix,symbol){for(const name of fs.readdirSync(dist).filter(n=>n.startsWith(prefix)&&n.endsWith('.mjs'))){const file=path.join(dist,name),alias=fs.readFileSync(file,'utf8').match(new RegExp('\\\\b'+symbol+' as (\\\\w+)\\\\b'))?.[1];if(alias)return (await import(pathToFileURL(file)))[alias];}throw Error(symbol);}
 const create=await api('task-registry-','createTaskRecord'),list=await api('task-registry-','listTasksForAgentId'),purge=await api('cleanup-service-','purgeAgentSessionStoreEntries');
 for(const agentId of ['${id}','${other}'])create({runtime:'cron',agentId,requesterSessionKey:'agent:'+agentId+':heartbeat',scopeKind:'session',task:'fixture',status:'succeeded',notifyPolicy:'none',deliveryStatus:'not_requested'});
 assert.equal(list('${id}').length,1);assert.equal(list('${other}').length,1);
 const cfg=JSON.parse(fs.readFileSync(process.env.OPENCLAW_CONFIG_PATH));
 assert.equal(await purge(cfg,'${id}'),false);assert.equal(list('${id}').length,0);assert.equal(list('${other}').length,1);
 assert.equal(await purge(cfg,'${id}'),false);
 // A normal native delete without our receipt is untouched.
 assert.equal(await purge(cfg,'${other}'),false);assert.equal(list('${other}').length,1);
 console.log('PASS: real native task retirement updates memory and storage, is repeatable, and preserves unrelated tasks');
 `;
 const result=spawnSync(process.execPath,['--import='+loader,'--input-type=module','-e',code,temp],{env:{...process.env,OPENCLAW_STATE_DIR:path.join(temp,'state'),OPENCLAW_CONFIG_PATH:config},encoding:'utf8',timeout:45000});
 assert.equal(result.status,0,result.stderr);console.log(result.stdout.trim());
}finally{fs.rmSync(temp,{recursive:true,force:true});}

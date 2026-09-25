// Runs inside the native deletion lifecycle, in the Gateway's own task registry.
// Deleting SQLite rows in a separate process would leave its in-memory cache live.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

export function retireOwnedTasks(agentId, list, terminal, remove) {
  const tasks=list(agentId);
  if(tasks.some(task=>task.agentId!==agentId || !terminal(task.status)))
    throw Error('Agent task retirement is not quiescent');
  for(const task of tasks)if(!remove(task.taskId))throw Error('Task retirement was not confirmed');
  if(list(agentId).length)throw Error('Agent tasks remain');
}

export async function purgeRetiredTasks(agentId) {
  if(!/^bac-[a-f0-9]{24}(?:-r\d+)?$/.test(agentId))return;
  const root=path.dirname(process.env.OPENCLAW_STATE_DIR);
  const receiptPath=path.join(root,'deletion-receipts',agentId+'.json');
  let receipt;
  try {
    const info=fs.lstatSync(receiptPath);
    if(!info.isFile() || info.nlink!==1 || fs.realpathSync(receiptPath)!==receiptPath)throw Error('Redirected deletion receipt');
    receipt=JSON.parse(fs.readFileSync(receiptPath,'utf8'));
  } catch(error){if(error.code==='ENOENT')return;throw error;}
  if(receipt.agentId!==agentId || !/^[a-f0-9]{64}$/.test(receipt.token))throw Error('Invalid deletion receipt');
  const dist=path.join(root,'package/node_modules/openclaw/dist');
  async function exported(prefix,symbol) {
    for(const name of fs.readdirSync(dist).filter(n=>n.startsWith(prefix)&&n.endsWith('.mjs'))) {
      const file=path.join(dist,name),source=fs.readFileSync(file,'utf8');
      const alias=source.match(new RegExp('\\b'+symbol+' as (\\w+)\\b'))?.[1];
      if(alias)return (await import(pathToFileURL(file)))[alias];
    }
    throw Error('Pinned task retirement API unavailable');
  }
  const list=await exported('task-registry-','listTasksForAgentId');
  const remove=await exported('task-registry-','deleteTaskRecordById');
  const terminal=await exported('task-registry.store.sqlite-','isTerminalTaskStatus');
  retireOwnedTasks(agentId,list,terminal,remove);
}

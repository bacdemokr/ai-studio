// Read identities through the running gateway; load full local cleanup only for offline deletion.
// The gateway owns the same lifecycle, shared-storage, cron and database cleanup safeguards.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const [root, agentId, operation] = process.argv.slice(2);
if (operation !== undefined && !['--confirm-deleted','--quiesce'].includes(operation)) throw Error('Invalid cleanup operation');
if (agentId !== '--list' && !/^bac-[a-f0-9]{24}(?:-r(?:0|[1-9][0-9]*))?$/.test(agentId || '')) throw Error('Invalid cleanup identity');
const pkg = path.join(root, 'package/node_modules/openclaw');
if (JSON.parse(await fs.readFile(path.join(pkg, 'package.json'), 'utf8')).version !== '2026.9.4') throw Error('Unsupported native runtime version');
const dist = path.join(pkg, 'dist'), files = await fs.readdir(dist);
async function nativeExport(prefix, symbol) {
  for (const name of files.filter(name => name.startsWith(prefix) && name.endsWith('.mjs'))) {
    const file = path.join(dist, name), source = await fs.readFile(file, 'utf8');
    const alias = source.match(new RegExp('\\b'+symbol+' as (\\w+)\\b'))?.[1];
    if (alias) return (await import(pathToFileURL(file)))[alias];
  }
  throw Error('Pinned native API unavailable: '+symbol);
}
async function confirmCompletedDeletion() {
  // A gateway can commit deletion before its reply/connection is lost. Only the
  // durable native journal plus absent owned paths proves that retry is complete.
  const config = JSON.parse(await fs.readFile(process.env.OPENCLAW_CONFIG_PATH, 'utf8'));
  if (config.agents?.entries?.[agentId]) return false;
  const readJournal = await nativeExport('agent-deletion-journal-', 'readAgentDeletionJournal');
  const journal = readJournal(agentId);
  if (journal?.agentId !== agentId || journal.cleanupCompleted !== true || journal.deleteFiles !== true) return false;
  for (const pathname of [journal.workspaceDir, journal.agentDir, journal.sessionsDir]) {
    if (typeof pathname !== 'string' || !path.isAbsolute(pathname)) return false;
    try { await fs.lstat(pathname); return false; }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  console.log(JSON.stringify({ok:true, agentId, failed:[], alreadyDeleted:true, transport:'completed-journal'}));
  return true;
}
async function deleteThroughGateway() {
  const config = JSON.parse(await fs.readFile(process.env.OPENCLAW_CONFIG_PATH, 'utf8'));
  let workspace = config.agents?.entries?.[agentId]?.workspace;
  // An acknowledged partial deletion removes the roster entry first. Resume
  // through the same live gateway and its lifecycle journal, not the offline CLI.
  if (typeof workspace !== 'string' || !path.isAbsolute(workspace)) {
    if (await confirmCompletedDeletion()) return true;
    const readJournal = await nativeExport('agent-deletion-journal-', 'readAgentDeletionJournal');
    const journal = readJournal(agentId);
    if (!journal || journal.agentId !== agentId || journal.cleanupCompleted || !journal.deleteFiles) return false;
    workspace = journal.workspaceDir;
    if (typeof workspace !== 'string' || !path.isAbsolute(workspace)) throw Error('Invalid deletion journal workspace');
  }
  const callGateway = await nativeExport('call-', 'callGateway');
  const credentialsRequired = await nativeExport('call-', 'isGatewayCredentialsRequiredError');
  const transportError = await nativeExport('transport-error-', 'isGatewayTransportError');
  let result;
  try {
    result = await callGateway({method:'agents.delete', params:{agentId,deleteFiles:true},
      mode:'cli', clientName:'cli', requiredMethods:['agents.delete'], timeoutMs:60000});
  } catch (error) {
    if (await confirmCompletedDeletion()) return true;
    // Match the native CLI's pre-request fallback conditions. Never retry an uncertain timeout.
    if (transportError(error) && error.kind === 'closed' && error.code === undefined) return false;
    if (credentialsRequired(error)) return false;
    throw error;
  }
  if (!result || result.ok !== true || result.agentId !== agentId || !Array.isArray(result.failed)) throw Error('Invalid native deletion response');
  // The RPC deliberately retains shared/replaced paths. They are not a successful app deletion.
  let workspaceRetained = true;
  try { await fs.lstat(workspace); } catch (error) { if (error.code === 'ENOENT') workspaceRetained = false; else throw error; }
  console.log(JSON.stringify({...result,workspaceRetained:workspaceRetained||undefined,transport:'gateway'}));
  return true;
}
async function quiesceAgent() {
  const callGateway = await nativeExport('call-', 'callGateway');
  const transportError = await nativeExport('transport-error-', 'isGatewayTransportError');
  const deadline = Date.now()+30000;
  const aborted = new Set();
  while (true) {
    if (Date.now()>=deadline) return {agentId,quiescent:false};
    let result;
    try {
      result = await callGateway({method:'sessions.list',params:{agentId,activeOnly:true},
        mode:'cli',clientName:'cli',requiredMethods:['sessions.list'],timeoutMs:Math.max(1,Math.min(10000,deadline-Date.now()))});
    } catch (error) {
      // A restarting/unreachable gateway proves neither activity nor absence.
      // Persist a pending deletion; never proceed to sandbox/file cleanup.
      if (transportError(error)) return {agentId,quiescent:false};
      throw error;
    }
    if (!Array.isArray(result?.sessions)) throw Error('Invalid active session response');
    if (!result.sessions.length) return {agentId,quiescent:true};
    for (const session of result.sessions) {
      if (typeof session.key!=='string' || !session.key.startsWith('agent:'+agentId+':')) throw Error('Unexpected session owner');
      if (aborted.has(session.key)) continue;
      if (Date.now()>=deadline) return {agentId,quiescent:false};
      aborted.add(session.key);
      try {
        await callGateway({method:'sessions.abort',params:{agentId,key:session.key,clearQueued:true},
          mode:'cli',clientName:'cli',requiredMethods:['sessions.abort'],timeoutMs:Math.max(1,Math.min(10000,deadline-Date.now()))});
      } catch (error) {
        // Abort can commit before its reply is lost. Recheck live activity,
        // rather than declaring failure or repeating the same abort blindly.
        if (!transportError(error)) throw error;
      }
    }
    if (Date.now()>=deadline) return {agentId,quiescent:false};
    await new Promise(resolve=>setTimeout(resolve,250));
  }
}
if (operation === '--quiesce') {
  console.log(JSON.stringify(await quiesceAgent()));
} else if (operation === '--confirm-deleted') {
  // Reconciliation from the parent process must never issue another delete.
  if (!await confirmCompletedDeletion()) process.exit(2);
} else if (agentId === '--list') {
  const callGateway = await nativeExport('call-', 'callGateway');
  console.log(JSON.stringify(await callGateway({method:'agents.list', params:{}, mode:'cli', clientName:'cli', requiredMethods:['agents.list'], timeoutMs:5000})));
} else if (!await deleteThroughGateway()) {
  const matches = files.filter(name => /^agents\.commands\.delete-.*\.mjs$/.test(name));
  if (matches.length !== 1) throw Error('Pinned native deletion command unavailable');
  const {agentsDeleteCommand} = await import(pathToFileURL(path.join(dist, matches[0])));
  // Loading the offline command can take seconds. A gateway cleanup may have
  // finished during that interval; do not turn its success into "not found".
  if (!await confirmCompletedDeletion()) {
    const createRuntime = await nativeExport('runtime-', 'createNonExitingRuntime');
    let report, reconciled=false;
    try {
      // Buffer CLI output so a late "not found" can be reconciled without
      // emitting a failure JSON followed by a second, successful JSON document.
      await agentsDeleteCommand({id:agentId,force:true,json:true}, {...createRuntime(),
        log:()=>{}, error:()=>{}, writeStdout:()=>{}, writeJson:value=>{report=value;}});
    } catch (error) {
      reconciled=await confirmCompletedDeletion();
      if (!reconciled) throw error;
    }
    if (!reconciled) {
      if (report?.agentId === agentId) console.log(JSON.stringify(report));
      else if (!await confirmCompletedDeletion()) throw Error('Invalid native deletion response');
    }
  }
}
await new Promise(resolve => process.stdout.write('', resolve));
process.exit(0);

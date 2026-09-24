// Scoped native heartbeat probe for live-deletion-cycles.py. Never prints session contents.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const [root,agentId,action]=process.argv.slice(2);
if(!/^bac-[a-f0-9]{24}$/.test(agentId||'')||!['wake','active'].includes(action))throw Error('Invalid test probe');
try {
 const pkg=path.join(root,'package/node_modules/openclaw');
 if(JSON.parse(await fs.readFile(path.join(pkg,'package.json'),'utf8')).version!=='2026.9.4')throw Error('Unsupported runtime');
 const dist=path.join(pkg,'dist');let callGateway;
 for(const name of (await fs.readdir(dist)).filter(n=>n.startsWith('call-')&&n.endsWith('.mjs'))){
  const file=path.join(dist,name),source=await fs.readFile(file,'utf8');
  const alias=source.match(/\bcallGateway as (\w+)\b/)?.[1];
  if(alias){callGateway=(await import(pathToFileURL(file)))[alias];break;}
 }
 if(!callGateway)throw Error('Missing pinned RPC');
 const method=action==='wake'?'wake':'sessions.list';
 const params=action==='wake'?{agentId,sessionKey:'agent:'+agentId+':heartbeat-radar',mode:'now',text:'Perform the local deletion test in HEARTBEAT.md now. Do not access websites or send messages.'}:{agentId,activeOnly:true};
 const result=await callGateway({method,params,mode:'cli',clientName:'cli',requiredMethods:[method],timeoutMs:10000});
 if(action==='active'){
  if(!Array.isArray(result.sessions)||result.sessions.some(s=>!s.key.startsWith('agent:'+agentId+':')))throw Error('Invalid scoped sessions');
  console.log(JSON.stringify({active:result.sessions.length,heartbeat:result.sessions.some(s=>s.key.includes('heartbeat'))}));
 }else console.log(JSON.stringify({requested:true}));
 process.exit(0);
}catch(error){console.error(JSON.stringify({errorName:error.name,kind:error.kind,code:error.code,message:String(error.message).split('\n')[0].replace(/(?:https?|wss?):\/\/\S+/g,'[url]').slice(0,240)}));process.exit(1);}

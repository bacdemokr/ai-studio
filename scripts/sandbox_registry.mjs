// Read agent-scoped native registry entries without probing any sandbox.
// Retire only entries the caller has verified absent in OpenShell.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const [root,agentId,namesJson]=process.argv.slice(2),names=namesJson===undefined?null:JSON.parse(namesJson);
if(!/^bac-[a-f0-9]{24}(?:-r[0-9]+)?$/.test(agentId)||(names!==null&&(!Array.isArray(names)||names.some(n=>!/^oc-[a-z0-9-]+$/.test(n)))))throw Error('Invalid cleanup identity');
const pkg=path.join(root,'package/node_modules/openclaw');
if(JSON.parse(await fs.readFile(path.join(pkg,'package.json'),'utf8')).version!=='2026.9.4')throw Error('Unsupported native runtime version');
for(const name of await fs.readdir(path.join(pkg,'dist'))){
 if(!/^registry-.*\.mjs$/.test(name))continue;
 const file=path.join(pkg,'dist',name),source=await fs.readFile(file,'utf8');
 const read=source.match(/readRegistry as (\w+)/)?.[1],remove=source.match(/removeRegistryEntry as (\w+)/)?.[1];
 if(!read||!remove)continue;
 const api=await import(pathToFileURL(file));
 const prefix='agent:'+agentId;
 if(names===null){
  const containers=(await api[read]()).entries.filter(row=>row.backendId==='openshell'&&(row.sessionKey===prefix||row.sessionKey.startsWith(prefix+':')));
  console.log(JSON.stringify({containers}));process.exit(0);
 }
 for(const containerName of names){
  const row=(await api[read]()).entries.find(r=>r.containerName===containerName);
  if(!row)continue;
  if(row.backendId!=='openshell'||!(row.sessionKey===prefix||row.sessionKey.startsWith(prefix+':')))throw Error('Registry ownership mismatch');
  await api[remove](containerName);
 }
 console.log('Missing sandbox records retired');process.exit(0);
}
throw Error('Pinned registry API unavailable');

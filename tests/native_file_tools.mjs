// Pinned OpenClaw tools, without model inference; all files are synthetic.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const pkg=process.argv[2];
assert.equal(JSON.parse(await fs.readFile(path.join(pkg,'package.json'),'utf8')).version,'2026.9.4');
const dist=path.join(pkg,'dist');let create;
for(const name of await fs.readdir(dist)){
 if(!name.startsWith('agent-tools-')||!name.endsWith('.mjs'))continue;
 const src=await fs.readFile(path.join(dist,name),'utf8'),match=src.match(/createOpenClawCodingTools as (\w+)/);
 if(match){create=(await import(pathToFileURL(path.join(dist,name))))[match[1]];break;}
}
assert(create);
const dir=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'bac-native-files-')));
try{
 const workspace=path.join(dir,'workspace');await fs.mkdir(workspace);
 const outside=path.join(dir,'outside.txt');await fs.writeFile(outside,'original');
 const config={agents:{defaults:{workspace},entries:{test:{workspace,tools:{allow:['read','write','edit'],fs:{workspaceOnly:false}},sandbox:{mode:'off'}}}},tools:{fs:{workspaceOnly:false}}};
 const tools=create({config,agentId:'test',sessionKey:'agent:test:main',workspaceDir:workspace,senderIsOwner:true});
 const read=tools.find(t=>t.name==='read'),write=tools.find(t=>t.name==='write');assert(read&&write);
 const result=await read.execute('read-test',{path:outside});assert.match(JSON.stringify(result),/original/);
 await write.execute('write-test',{path:outside,content:'approved edit'});assert.equal(await fs.readFile(outside,'utf8'),'approved edit');
 console.log('PASS: real OpenClaw read/write tools access a requested file outside the default workspace with OpenShell off.');
}finally{await fs.rm(dir,{recursive:true,force:true});}

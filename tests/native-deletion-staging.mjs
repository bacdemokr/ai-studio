// Opt-in pinned native filesystem integration. Uses only an isolated temp root.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const installed=process.argv[2]&&path.resolve(process.argv[2]);
if(!installed)throw Error('Pass the installed private OpenClaw root');
const temp=fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()),'bac-retirement-'));
const id='bac-'+'a'.repeat(24), token='b'.repeat(64);
try {
 fs.symlinkSync(path.join(installed,'package'),path.join(temp,'package'));
 fs.mkdirSync(path.join(temp,'state'));fs.mkdirSync(path.join(temp,'deletion-receipts'));
 const source=path.join(temp,'workspace');fs.mkdirSync(source);
 fs.writeFileSync(path.join(source,'.bac-deletion-owner.json'),JSON.stringify({agentId:id,token}));
 fs.writeFileSync(path.join(source,'private-content'),'test-only');
 const receipt=path.join(temp,'deletion-receipts',id+'.json');
 fs.writeFileSync(receipt,JSON.stringify({agentId:id,token,paths:[source],marked:[source],routed:[]}));
 const trash=pathToFileURL(fs.realpathSync(path.join(temp,'package/node_modules/@openclaw/fs-safe/dist/trash.js'))).href;
 const loader=new URL('../scripts/native_cleanup_loader.mjs',import.meta.url).href;
 const result=spawnSync(process.execPath,['--import='+loader,'--input-type=module','-e',`import {movePathToTrash} from ${JSON.stringify(trash)};console.log(await movePathToTrash(process.argv[1],{allowedRoots:[process.argv[2]]}));`,source,temp],{env:{...process.env,OPENCLAW_STATE_DIR:path.join(temp,'state')},encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
 const destination=result.stdout.trim();assert.ok(destination.startsWith(path.join(temp,'deletion-staging/.Trash')+path.sep));
 assert.equal(fs.existsSync(source),false);assert.equal(fs.readFileSync(path.join(destination,'private-content'),'utf8'),'test-only');
 assert.deepEqual(JSON.parse(fs.readFileSync(receipt)).routed,[source]);
 // Valid marker on an unowned source cannot select staging or move anything.
 fs.mkdirSync(source);fs.writeFileSync(path.join(source,'.bac-deletion-owner.json'),JSON.stringify({agentId:id,token:'c'.repeat(64)}));
 const refused=spawnSync(process.execPath,['--import='+loader,'--input-type=module','-e',`import {movePathToTrash} from ${JSON.stringify(trash)};await movePathToTrash(process.argv[1],{allowedRoots:[process.argv[2]]});`,source,temp],{env:{...process.env,OPENCLAW_STATE_DIR:path.join(temp,'state')},encoding:'utf8'});
 assert.notEqual(refused.status,0);assert.ok(fs.existsSync(source));
 console.log('Pinned native staging: owned path routed, source moved, receipt durable, wrong owner rejected.');
} finally {fs.rmSync(temp,{recursive:true,force:true});}

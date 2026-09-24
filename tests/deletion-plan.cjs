// Batch inspection must prove absence, including orphaned native state.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'bac-delete-plan-')),pkg=path.join(root,'package/node_modules/openclaw'),dist=path.join(pkg,'dist');
const id='bac-'+'a'.repeat(24),ids=Array.from({length:7},(_,i)=>id+'-r'+i),config=path.join(root,'config.json'),trace=path.join(root,'trace');
try{
 fs.mkdirSync(dist,{recursive:true});fs.writeFileSync(path.join(pkg,'package.json'),JSON.stringify({version:'2026.9.4'}));
 fs.writeFileSync(config,JSON.stringify({agents:{entries:{[ids[0]]:{}}}}));
 fs.writeFileSync(path.join(dist,'agent-deletion-journal-fixture.mjs'),`function readAgentDeletionJournal(id){return id.endsWith('-r1')?{cleanupCompleted:false}:id.endsWith('-r2')?{cleanupCompleted:true}:null;}export {readAgentDeletionJournal as r};`);
 fs.writeFileSync(path.join(dist,'registry-fixture.mjs'),`import fs from 'node:fs';function readRegistry(){fs.appendFileSync(process.env.TEST_TRACE,'read\\n');if(process.env.BAD_REGISTRY)throw Error('Registry unavailable');return {entries:[{sessionKey:'agent:${ids[3]}:main'}]};}export {readRegistry as r};`);
 fs.mkdirSync(path.join(root,'state/agents',ids[4]),{recursive:true});
 fs.symlinkSync(path.join(root,'missing'),path.join(root,'state/agents',ids[5]));
 function run(list,extra={}){return spawnSync(process.execPath,['scripts/inspect_deletion_plan.mjs',root,JSON.stringify(list)],{encoding:'utf8',timeout:5000,env:{...process.env,OPENCLAW_CONFIG_PATH:config,TEST_TRACE:trace,...extra}});}
 const result=run(ids);assert.equal(result.status,0,result.stderr);assert.deepEqual(JSON.parse(result.stdout),{unregistered:[ids[6]]});assert.equal(fs.readFileSync(trace,'utf8'),'read\n','One registry read for the whole plan');
 assert.notEqual(run(ids,{BAD_REGISTRY:'1'}).status,0,'Unavailable is not empty');
 assert.notEqual(run([id,'bac-'+'b'.repeat(24)]).status,0,'Cannot combine unrelated identities');
 assert.notEqual(run([id,id]).status,0);assert.notEqual(run([id+'-r01']).status,0);
 assert(fs.lstatSync(path.join(root,'state/agents',ids[5])).isSymbolicLink(),'Inspection must not mutate paths');
 console.log('PASS: one registry read; registered, pending/completed journal, sandbox, orphan folder and symlink never skipped; malformed plans fail closed.');
}finally{fs.rmSync(root,{recursive:true,force:true});}

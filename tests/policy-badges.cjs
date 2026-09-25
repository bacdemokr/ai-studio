const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),calls=[];
function el(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',title:'',classList:{toggle(){}},setAttribute(k,v){this[k]=v;}});return nodes.get(id);}
const context={Map,Set,JSON,Date,el,window:{BacCrewCatalog:[{name:'Dylan',protection:'openshell'}]},selectedCrewRole:0,room:'lounge',agentId:'a',data:{profile:{name:'A',protection:'openshell'},agents:[{key:'a'},{key:'b'}],jobs:[],protectionEvents:[]},api(route,body,owner){return new Promise((resolve,reject)=>calls.push({route,owner,resolve,reject}));}};
vm.createContext(context);
const source=fs.readFileSync('src/studio-policies.js','utf8');
vm.runInContext(source.slice(source.indexOf('const policyBadgeReports='),source.indexOf('function policyTarget()')),context);
const run=s=>vm.runInContext(s,context),tick=()=>new Promise(r=>setImmediate(r));
const report={catalog:{'host:one.test':{hosts:['one.test']},'host:two.test':{hosts:['two.test']}},requested:[],pendingAccess:[{host:'one.test'},{host:'one.test'},{host:'two.test'}]};
(async()=>{
 run('syncPolicyBadges()');run('syncPolicyBadges()');assert.equal(calls.length,1,'Coalesce in-flight lookups');
 calls[0].resolve(report);await tick();assert.match(el('agent-policy').innerHTML,/>2<\/span>/);assert.match(el('agent-policy')['aria-label'],/2 websites awaiting approval/);
 for(let i=0;i<10;i++)run('syncPolicyBadges()');assert.equal(calls.length,1,'Stable state does not poll OpenShell');
 context.agentId='b';context.data.profile.name='B';run('syncPolicyBadges()');assert(!el('agent-policy').innerHTML.includes('badge'),'Do not show A count for B');
 calls[1].resolve({...report,pendingAccess:[]});await tick();assert(!el('agent-policy').innerHTML.includes('badge'));
 context.agentId='a';context.data.profile.name='A';run('syncPolicyBadges()');assert.match(el('agent-policy').innerHTML,/>2<\/span>/);
 context.data.jobs=[{id:'j',status:'done',kind:'chat'}];run('syncPolicyBadges()');assert.equal(calls.length,3);
 context.approved={...report,requested:['host:one.test','host:two.test']};run("rememberPolicyBadge('a:personal',approved)");assert(!el('agent-policy').innerHTML.includes('badge'));
 calls[2].resolve(report);await tick();assert(!el('agent-policy').innerHTML.includes('badge'),'Late pre-approval response must not restore old count');
 calls[3].resolve(context.approved);await tick();
 context.room='mission';run('syncPolicyBadges()');assert.equal(calls[4].route,'crew-policy?role=0');calls[4].resolve(report);await tick();assert.match(el('crew-policy').innerHTML,/>2<\/span>/);assert(!el('agent-policy').innerHTML.includes('badge'));
 context.data.protectionEvents=[{id:'new',owner:'a',role:null}];run('syncPolicyBadges()');assert.equal(calls.length,5,'A hidden personal policy button does not query OpenShell');
 context.room='lounge';run('syncPolicyBadges()');calls[5].reject(Error('offline'));await tick();run('syncPolicyBadges()');assert.equal(calls.length,6,'Failed lookup has a retry backoff');
 console.log('PASS: counts, deduplication, approval removal, account/crew scope, stale responses and request throttling');
})().catch(e=>{console.error(e);process.exitCode=1;});

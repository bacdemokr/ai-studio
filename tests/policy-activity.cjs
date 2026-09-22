const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements={},agent={key:'test-agent',pending:1,latestMission:{id:'run',status:'running'}};
const report={agentId:agent.key,status:'applied',sandboxes:['sandbox'],requested:[],catalog:{weather:{title:'Weather',description:'Live weather',hosts:['example.com']}}};
let calls=0;
const context={window:{BacCrewCatalog:[]},data:{agents:[agent],profile:{name:'Test',protection:'openshell'}},agentId:agent.key,policySnapshot:report,policyLoading:false,policySaving:false,policyVersion:0,
el:id=>elements[id]||(elements[id]={innerHTML:'',open:id==='policy-panel',addEventListener(){}}),escape:String,api:async()=>{calls++;return report;}};
vm.createContext(context);vm.runInContext(fs.readFileSync('src/studio-policies.js','utf8'),context);
(async()=>{
 vm.runInContext('renderPolicySelector()',context);await new Promise(setImmediate);
 assert.match(elements['policy-content'].innerHTML,/Wait for this agent/);
 assert.match(elements['policy-content'].innerHTML,/data-policy-allow="true" disabled/);
 agent.pending=0;agent.latestMission.status='done';
 vm.runInContext('renderPolicySelector()',context);await new Promise(setImmediate);
 assert.doesNotMatch(elements['policy-content'].innerHTML,/Wait for this agent/);
 assert.doesNotMatch(elements['policy-content'].innerHTML,/data-policy-allow="true" disabled/);
 assert.equal(calls,2);
 vm.runInContext('renderPolicySelector()',context);await new Promise(setImmediate);
 assert.equal(calls,2,'unchanged polls should not reload policy');
 assert.doesNotMatch(elements['policy-content'].innerHTML,/data-policy-access-tab|Approve read|protected copy/);
 assert.match(elements['policy-content'].innerHTML,/Approved websites/);
 report.connectionIssues=[{host:'api.open-meteo.com',reason:'dns-failed'}];
 context.policySnapshot={...report,_targetKey:agent.key+':personal'};
 vm.runInContext('renderPolicy()',context);
 assert.match(elements['policy-content'].innerHTML,/DNS lookup failed inside OpenShell/);
 assert.doesNotMatch(elements['policy-content'].innerHTML,/data-policy-permission="host:api.open-meteo.com"/);
 console.log('PASS: completed run clears stale waiting notice, unlocks approvals and refreshes policy once.');
})().catch(e=>{console.error(e);process.exitCode=1});

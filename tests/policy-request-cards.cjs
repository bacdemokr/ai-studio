const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();
const el=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',setAttribute(){}});return nodes.get(id);};
const hosts=['www.google.com','google.com'];
const report={_targetKey:'smith:personal',status:'applied',sandboxes:[{}],requested:[],
 catalog:Object.fromEntries(hosts.map(host=>['host:'+host,{title:host,hosts:[host]}])),
 pendingAccess:[{host:hosts[0],reason:'blocked'},{host:hosts[1],reason:'requested'}]};
const context=vm.createContext({el,policyTarget:()=>({key:'smith:personal',name:'Smith_2',mode:'openshell'}),
 policySnapshot:report,policyCrewRole:null,policySaving:false,policyLoading:false,agentId:'smith',
 data:{agents:[{key:'smith',pending:0}]},escape:String});
const source=fs.readFileSync('src/studio-policies.js','utf8');
vm.runInContext(source.slice(source.indexOf('function renderPolicy(){'),source.indexOf("el('policy-agent').onchange=")),context);
context.renderPolicy();
let html=el('policy-content').innerHTML;
assert.match(html,/Websites awaiting approval<span>2<\/span>/);
for(const host of hosts)assert(html.includes('data-policy-permission="host:'+host+'"'));
assert.equal((html.match(/Requested in your message · not a confirmed policy block/g)||[]).length,1);
assert(!html.includes('latest conversation'));
report.requested=hosts.map(host=>'host:'+host);context.renderPolicy();
html=el('policy-content').innerHTML;
assert.match(html,/Websites awaiting approval<span>0<\/span>/);
assert.match(html,/Approved websites<span>2<\/span>/);
assert(!html.includes('Requested in your message'));
console.log('PASS: blocked and requested hosts render separately; explicit approval clears pending cards');

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio-event-team.js','utf8');
const body=source.slice(source.indexOf(' const turns='),source.indexOf('\n loadChatImages(log'));
const log={innerHTML:'',scrollHeight:0,scrollTop:0,clientHeight:100};
const job={id:'mission',kind:'crew',status:'running',created:1,payload:{handoffs:{3:{}},outputs:{}},result:{}};
const ctx=vm.createContext({i:3,key:'a:3',switched:false,crewChatSignature:'',shieldReplyHeld:()=>false,data:{jobs:[job]},el:()=>log,name:'Morgan',escape:String,messageMarkup:String,crewHandoffMessages:()=>'',customSkillMarkup:()=>'',crewActivityMarkup:()=>'',imageHistoryMarkup:()=>'',crewBriefMessage:()=>'',roundtableMarkup:()=>''});
vm.runInContext('function render(){'+body+'}',ctx);
ctx.render();assert.match(log.innerHTML,/Working on the assigned task/);
job.payload.socialDraft={status:'ready',text:'An early LinkedIn draft.'};
ctx.render();assert.match(log.innerHTML,/An early LinkedIn draft/);assert.match(log.innerHTML,/Writing the webpage/);
// A teammate may still be running when this agent's error arrives.
job.payload.stageErrors={3:'HTML failed'};
ctx.render();assert.match(log.innerHTML,/HTML failed/);
job.status='error';
ctx.render();assert.match(log.innerHTML,/An early LinkedIn draft/);assert.match(log.innerHTML,/HTML failed/);
job.status='done';job.payload.outputs[3]='Page validated';job.payload.website={authored:true};
ctx.render();assert.match(log.innerHTML,/Open webpage/);assert.match(log.innerHTML,/Page validated/);
console.log('PASS: early social draft appears on state refresh and survives page failure/completion.');

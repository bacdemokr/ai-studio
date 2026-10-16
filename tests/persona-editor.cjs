// Focused controller checks; DOM and HTTP are simulated, no live agents touched.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('src/studio-identity.js','utf8');
const controller=source.slice(source.indexOf('function editAgentPersona('),source.indexOf("for(const id of ['portrait','agent-name'])"));
function setup(){
 const profile={name:'Orbit',tone:'kind',tonePrompt:'Warm',purpose:'Research papers.',persona:'guide',skills:['web'],model:'existing',protection:'standard'};
 const elements=['name','tonePrompt','purpose'].map(()=>({value:'',disabled:false,focus(){}}));
 [elements.name,elements.tonePrompt,elements.purpose]=elements;
 const error={hidden:true},cancel={},form={elements,querySelector:s=>s==='[role=alert]'?error:cancel,remove(){this.removed=true;}};
 const old=[{hidden:false},{hidden:false}],host={children:old,append(){},querySelector:()=>({focus(){}})};
 const state={profile:{...profile}},calls=[];let current=true,reopened=0,refreshed=0,rejection=null;
 const context={data:{profile},document:{createElement:()=>form},savedTonePrompt:p=>p.tonePrompt,personas:{guide:'Guide'},tones:{kind:[],cynical:[]},matchesTonePrompt:(key,text)=>key==='cynical'&&text==='Cynical',
 api:async(path,payload,target)=>{calls.push({path,payload,target});if(path==='state')return state;if(rejection)throw Error(rejection);state.profile=payload;},refresh:async()=>{refreshed++;}};
 vm.runInNewContext(controller,context);
 context.editAgentPersona(host,()=>current,async()=>{reopened++;},'agent-orbit');
 return {form,error,cancel,old,state,calls,submit:()=>form.onsubmit({preventDefault(){}}),stop:()=>current=false,reject:msg=>rejection=msg,get reopened(){return reopened;},get refreshed(){return refreshed;}};
}
(async()=>{
 const saved=setup();saved.form.elements.purpose.value='Compare three papers.';saved.form.elements.tonePrompt.value='Cynical';
 saved.state.profile={...saved.state.profile,model:'new-model',skills:['web','documents']};
 await saved.submit();const post=saved.calls.find(c=>c.path==='profile');
 assert.equal(post.target,'agent-orbit');assert.equal(post.payload.purpose,'Compare three papers.');assert.equal(post.payload.tone,'cynical');assert.equal(post.payload.model,'new-model');assert.deepEqual(post.payload.skills,['web','documents']);assert.equal(saved.reopened,1);assert.equal(saved.refreshed,1);
 const cancelled=setup();cancelled.cancel.onclick();assert(cancelled.form.removed);assert(cancelled.old.every(x=>!x.hidden));assert.equal(cancelled.calls.length,0);
 const stale=setup();stale.state.profile.purpose='Changed elsewhere';await stale.submit();assert.equal(stale.calls.length,1);assert.match(stale.error.textContent,/changed elsewhere/);
 const busy=setup();busy.reject('Finish or cancel this agent’s pending missions before changing it.');await busy.submit();assert.equal(busy.error.hidden,false);assert.equal(busy.reopened,0);assert(busy.form.elements.every(x=>!x.disabled));
 const switched=setup();switched.stop();await switched.submit();assert.equal(switched.calls.length,0);
 console.log('PASS: persona save preserves current model/skills; cancel, stale edit, busy rejection and switched-agent guards.');
})().catch(e=>{console.error(e);process.exitCode=1;});

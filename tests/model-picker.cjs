// Exercise picker transitions and stale saves without starting a browser/model.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(){this.hidden=false;this.isConnected=true;this.events={};this.children=new Map();this.scrollTop=0;this.value='';this.dataset={};}
 setAttribute(){}
 addEventListener(type,fn){(this.events[type]??=[]).push(fn)}
 async emit(type,event){for(const fn of this.events[type]||[])await fn(event)}
 querySelector(selector){if(!this.children.has(selector))this.children.set(selector,new Element());return this.children.get(selector)}
 append(child){child.isConnected=true}
 focus(){this.focused=true}
 close(){this.open=false;this.emit('close',{})}
}
(async()=>{
 const nodes=new Map(),el=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
 const root=new Element();let panel,save;
 const models=Array.from({length:249},(_,i)=>({id:'model/'+i,label:'Model '+i}));
 const context={document:{createElement:()=>panel=new Element()},root,el,runtime:{teamModels:models,teamModel:true,teamReady:true},window:{BacCrewCatalog:[{},{},{}]},resetInProgress:false,teamRuntime:()=>({teamReady:true}),teamModel:()=>models[0],agentId:'owner',selectedScenario:'plan',defaultNames:['Casey','Vera','Cody'],escape:String,dialogRevision:0,refreshVersion:0,stateCache:new Map(),data:{teamSelections:['unchanged']},render(){},alert(){},api:async(path,body,owner)=>{assert.equal(path,'team-model');assert.equal(owner,'owner');if(save)await save;return {teamSelections:[body.model]};}};
 context.dialog=()=>{context.dialogRevision++;el('dialog').open=true;};vm.createContext(context);
 const source=fs.readFileSync('src/studio-crew.js','utf8');
 vm.runInContext(source.slice(source.indexOf('const teamModelDialog='),source.indexOf("root.addEventListener('click',async event=>{")),context);
 const open=async role=>root.emit('click',{target:{closest:()=>({dataset:{standbyModel:String(role)}})}});
 const choose=async model=>panel.emit('click',{target:{closest:selector=>selector==='[data-model-choice]'?{dataset:{modelChoice:model}}:null}});
 for(let i=0;i<60;i++){
  await open(i%3);assert.equal(panel.hidden,false);assert.equal(el('dialog').open,true);
  assert.equal((panel.querySelector('.team-model-results').innerHTML.match(/data-model-choice=/g)||[]).length,40);
  if(i%3===0){await choose('model/1');assert.equal(context.data.teamSelections[0],'model/1');}
  else if(i%3===1)await panel.emit('click',{target:{closest:selector=>selector==='[data-model-close]'?{}:null}});
  else {let prevented=false;await el('dialog').emit('cancel',{preventDefault(){prevented=true}});assert(prevented);}
  assert.equal(panel.hidden,true);assert.equal(el('dialog').open,false);
 }
 // A successful Open Task save must not overwrite an Event Brief opened meanwhile.
 let release;save=new Promise(r=>release=r);await open(0);const pending=choose('model/2');
 context.selectedScenario='event-brief';context.data={teamSelections:['event-model']};context.dialogRevision++;el('dialog').close();release();await pending;
 assert.equal(context.data.teamSelections[0],'event-model');
 console.log('PASS: 60 direct picker transitions, bounded results, save/Back/Escape and scenario isolation for delayed saves.');
})().catch(e=>{console.error(e);process.exitCode=1;});

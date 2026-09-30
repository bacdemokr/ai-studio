const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(){this.hidden=false;this.isConnected=true;this.events={};this.children=new Map();this.scrollTop=0;this.value='';this.dataset={};}
 setAttribute(){}
 addEventListener(type,fn){(this.events[type]??=[]).push(fn)}
 emit(type,event){for(const fn of this.events[type]||[])fn(event)}
 querySelector(selector){if(!this.children.has(selector))this.children.set(selector,new Element());return this.children.get(selector)}
 append(child){child.isConnected=true}
 focus(){this.focused=true}
 close(){throw Error('Model navigation must not close the native dialog')}
 showModal(){throw Error('Model navigation must not reopen the native dialog')}
}
const nodes=new Map(),el=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
const root=new Element(),form=el('team-config-form');el('dialog').open=true;
let panel;
const models=Array.from({length:249},(_,i)=>({id:'model/'+i,label:'Model '+i}));
const context={document:{createElement:tag=>{assert.equal(tag,'section');return panel=new Element()}},root,el,runtime:{teamModels:models},teamModel:()=>models[0],teamModelDrafts:new Map(),agentId:'owner',defaultNames:['Casey','Vera','Cody'],escape:s=>String(s)};
vm.createContext(context);
const source=fs.readFileSync('src/studio-crew.js','utf8');
vm.runInContext(source.slice(source.indexOf('const teamModelDialog='),source.indexOf("root.addEventListener('click',async event=>{")),context);
for(let iteration=0;iteration<60;iteration++){
 const role=iteration%3,trigger=form.querySelector('[data-team-model="'+role+'"]');trigger.dataset.teamModel=String(role);trigger.closest=()=>form;
 el('dialog').scrollTop=123;
 root.emit('click',{target:{closest:()=>trigger}});
 assert.equal(form.hidden,true);assert.equal(panel.hidden,false);assert.equal(el('dialog').open,true);
 assert.equal((panel.querySelector('.team-model-results').innerHTML.match(/data-model-choice=/g)||[]).length,40);
 if(iteration%3===0){
  const choice={dataset:{modelChoice:'model/1'}};
  panel.emit('click',{target:{closest:selector=>selector==='[data-model-choice]'?choice:null}});
  assert.equal(context.teamModelDrafts.get(role),'model/1');
 }else if(iteration%3===1){
  panel.emit('click',{target:{closest:selector=>selector==='[data-model-close]'?{}:null}});
 }else{
  let prevented=false;el('dialog').emit('cancel',{preventDefault(){prevented=true}});assert(prevented);
 }
 assert.equal(form.hidden,false);assert.equal(panel.hidden,true);assert.equal(el('dialog').scrollTop,123);assert(trigger.focused);assert.equal(el('dialog').open,true);
}
// Escaping the picker must preserve previously staged selections.
assert.equal(context.teamModelDrafts.get(0),'model/1');
console.log('PASS: 60 picker transitions, single modal, bounded results, selection, Back, Escape, focus and draft preservation');

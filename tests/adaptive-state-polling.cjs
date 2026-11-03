const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/studio.js','utf8');
const timers=new Map(),listeners={},requests=[];let serial=0,now=Date.now();
const c={data:{jobs:[],crewChats:[],agents:[]},agentId:'a',refreshVersion:0,connected:true,
 busy:false,changingAgent:false,removingAgent:false,pendingWrites:0,hiringArrival:false,
 document:{hidden:false,addEventListener:(name,fn)=>listeners[name]=fn},
 window:{addEventListener:(name,fn)=>listeners[name]=fn},
 setTimeout(fn,ms){const id=++serial;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
 Date:{now:()=>now},api:()=>new Promise((resolve,reject)=>requests.push({resolve,reject})),render(){},alert(){}};
vm.createContext(c);
vm.runInContext(source.slice(source.indexOf('  async function refresh()'),source.indexOf("  el('equipped').onclick")),c);
const next=async()=>{assert.equal(timers.size,1);const [id,timer]=[...timers][0];timers.delete(id);return timer.fn();};
const delay=()=>{assert.equal(timers.size,1);return [...timers.values()][0].ms;};
(async()=>{
 c.scheduleStatePoll();assert.equal(delay(),3500);
 c.data.jobs=[{status:'running'}];assert.equal(c.statePollDelay(),650);
 c.data.jobs=[{status:'queued',due:now/1000+3600}];assert.equal(c.statePollDelay(),650,'Keep polling for late policy evidence after completion');
 now+=7900;assert.equal(c.statePollDelay(),650);now+=101;assert.equal(c.statePollDelay(),3500,'Fast tail expires; future scheduled work must not keep it alive');
 c.data.jobs=[];c.data.crewChats=[{status:'stopping'}];assert.equal(c.statePollDelay(),650);
 c.data.crewChats=[];c.data.agents=[{pending:1}];assert.equal(c.statePollDelay(),650);
 c.data.agents=[];c.pendingWrites=1;assert.equal(c.statePollDelay(),650);c.pendingWrites=0;
 now+=8001;
 const first=next();assert.equal(requests.length,1);assert(c.busy);
 listeners.focus();await next();assert.equal(requests.length,1,'focus during a slow request must not overlap it');
 requests[0].resolve(c.data);await first;assert.equal(delay(),3500);
 c.document.hidden=true;listeners.visibilitychange();assert.equal(timers.size,0);
 c.document.hidden=false;listeners.visibilitychange();assert.equal(delay(),0);
 const fail=next();requests[1].reject({status:503,message:'fixture'});await fail;assert.equal(delay(),3500);
 const failAgain=next();requests[2].reject({status:503,message:'fixture'});await failAgain;assert.equal(delay(),7000);
 const recover=next();c.data.jobs=[{status:'running'}];requests[3].resolve(c.data);await recover;assert.equal(delay(),650);
 // A workspace switch invalidates the response, but must not stop polling.
 const stale=next();c.refreshVersion++;c.busy=false;c.agentId='b';
 requests[4].resolve({agentId:'a'});await stale;assert.equal(delay(),650);assert.equal(c.agentId,'b');
 c.connected=false;c.scheduleStatePoll();assert.equal(timers.size,0);
 console.log('PASS: active/idle cadence, bounded completion tail, no overlapping polls, focus/visibility, bounded error backoff, recovery and stale workspace responses.');
})().catch(error=>{console.error(error);process.exitCode=1;});

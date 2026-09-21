const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
// Exercise the actual polling function without submitting any model jobs.
const source = fs.readFileSync('src/studio-compare.js', 'utf8');
const polling = source.slice(source.indexOf('let comparisonRead='), source.indexOf('async function askAllAgents'));
(async () => {
  let calls=0, release;
  const pending=new Promise(resolve=>{release=resolve;});
  const batch={rows:[{key:'test-agent',job:'job-1',status:'running'}]};
  const context=vm.createContext({comparison:batch,comparisonTimer:null,drawComparison(){},
    clearTimeout,setTimeout,api:async()=>{calls++;await pending;return {jobs:[{id:'job-1',status:'done',result:{answer:'Saved result'}}]};}});
  vm.runInContext(polling,context);
  const first=context.pollComparison(false),second=context.pollComparison(false);
  assert.equal(calls,1,'overlapping refreshes share one request');
  release();await Promise.all([first,second]);
  assert.equal(batch.rows[0].status,'done');assert.equal(batch.rows[0].answer,'Saved result');
  await context.pollComparison(false);assert.equal(calls,1,'terminal jobs are not polled again');
  console.log('PASS: overlapping comparison reads coalesce; completed jobs stop polling.');
})().catch(error=>{console.error(error);process.exitCode=1;});

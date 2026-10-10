import assert from 'node:assert/strict';
import {beforeTool, persistResult} from '../runtime/research-guard/index.mjs';

const id = 'bac-' + 'b'.repeat(24);
const ctx = {agentId: id, sessionKey: `agent:${id}:openai-user:${id}`};
const call = (toolName, runId, n, params = {}) => ({toolName, runId, toolCallId: `${runId}-${n}`, params});
const search = n => call('web_search', 'first', n, {query: 'physical ai', count: 20});
assert.equal(beforeTool(search(1), ctx).params.count, 3);
assert.equal(beforeTool(search(1), ctx).params.count, 3); // Native duplicate hook.
assert.equal(beforeTool(search(2), ctx).block, undefined);
assert.equal(beforeTool(search(3), ctx).block, true);
for (let i = 0; i < 5; i++) {
  const event = call('web_fetch', 'first', `fetch${i}`, {url: `https://arxiv.org/abs/${i}`, maxChars: 20000});
  assert.equal(beforeTool(event, ctx).params.maxChars, 3000);
}
assert.equal(beforeTool(call('web_fetch', 'first', 'extra'), ctx).block, true);
// A follow-up in the same conversation gets a fresh budget, not a 15-minute lockout.
assert.equal(beforeTool(call('web_fetch', 'second', 1, {maxChars: 1500}), ctx).params.maxChars, 1500);
const spillPath = '/tmp/openclaw-web-fetch-44efe5b2f1ccc04b.log';
assert.equal(beforeTool(call('read', 'second', 2, {path: spillPath, limit: 300}), ctx).block, true);
assert.equal(beforeTool(call('read', 'second', 3, {file_path: spillPath}), ctx).block, true);
for (const path of ['inbox/email.md', 'artifacts/app.html', 'skills/bac-web/SKILL.md']) {
  assert.equal(beforeTool(call('read', 'second', path, {path}), ctx), undefined);
}
assert.equal(beforeTool(call('write', 'second', 4, {path:'artifacts/brief.md'}), ctx), undefined);
const wrapped = '\n<<<EXTERNAL_UNTRUSTED_CONTENT id="abc">>>\nSource: Web Search\n---\n' + 'source '.repeat(3000) + '\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id="abc">>>';
const envelope = {results: Array.from({length: 5}, (_, i) => ({url:`https://arxiv.org/abs/${i}`, title:'Paper', snippet:wrapped}))};
const message = {role:'toolResult', toolCallId:'search', content:[{type:'text', text:JSON.stringify(envelope)}]};
const shortened = persistResult({toolName:'web_search', message}, ctx).message;
assert(shortened.content[0].text.length < 6500);
assert(JSON.parse(shortened.content[0].text).results.every(r => r.snippet.endsWith('<<<END_EXTERNAL_UNTRUSTED_CONTENT id="abc">>>')));
const fetch = {url:'https://arxiv.org/abs/1', status:200, truncated:true, spill:{path:spillPath, chars:50000},
  text:'<<<EXTERNAL_UNTRUSTED_CONTENT id="abc">>>\nAbstract excerpt\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id="abc">>>\n\n[Showing truncated web_fetch content. Full output: '+spillPath+'.]'};
const cleaned = persistResult({toolName:'web_fetch', message:{...message, content:[{type:'text',text:JSON.stringify(fetch)}], details:fetch}}, ctx).message;
assert(!JSON.stringify(cleaned).includes(spillPath));
assert.equal(cleaned.details.url, fetch.url);
assert.equal(cleaned.details.status, 200);
assert(cleaned.details.text.includes('<<<END_EXTERNAL_UNTRUSTED_CONTENT id="abc">>>'));
assert(cleaned.details.truncated);
// Errors, heartbeat, crew scenarios and unrelated agents remain outside this path.
assert.equal(persistResult({toolName:'web_fetch', message:{...message,isError:true}}, ctx), undefined);
for (const other of [{...ctx,sessionKey:`agent:${id}:main`}, {...ctx,agentId:id+'-r0'}, {...ctx,agentId:'other'}]) {
  assert.equal(beforeTool(call('read','third',1,{path:spillPath}), other), undefined);
  assert.equal(persistResult({toolName:'web_search',message}, other), undefined);
}
console.log('Lounge research: bounded calls, excerpts, spill-file rereads, follow-up budgets and scope passed.');

// Exact-name ownership lookup must reject unknown, mixed and foreign owners.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bac-registry-'));
const pkg = path.join(root, 'package/node_modules/openclaw');
const agentId = 'bac-' + 'a'.repeat(24);
try {
  fs.mkdirSync(path.join(pkg, 'dist'), {recursive: true});
  fs.writeFileSync(path.join(pkg, 'package.json'), JSON.stringify({version: '2026.9.4'}));
  fs.writeFileSync(path.join(pkg, 'dist/registry-fixture.mjs'), `
    async function readRegistry() { return {entries: JSON.parse(process.env.TEST_ROWS)}; }
    async function removeRegistryEntry() { throw Error('Read-only lookup mutated registry'); }
    export {readRegistry as r, removeRegistryEntry as d};
  `);
  const row = {containerName: 'oc-owned', backendId: 'openshell', sessionKey: 'agent:' + agentId + ':main'};
  const run = rows => spawnSync(process.execPath,
    ['scripts/sandbox_registry.mjs', root, '--owner', 'oc-owned'],
    {encoding: 'utf8', env: {...process.env, TEST_ROWS: JSON.stringify(rows)}});
  let result = run([row, {...row, containerName: 'oc-other', sessionKey: 'agent:foreign:main'}]);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {agentId});
  assert.equal(run([row, {...row, sessionKey: 'agent:' + agentId + ':heartbeat'}]).status, 0);
  for (const rows of [[], [{...row, backendId: 'docker'}], [{...row, sessionKey: 'agent:foreign:main'}],
    [row, {...row, sessionKey: 'agent:bac-' + 'b'.repeat(24) + ':main'}]]) {
    assert.notEqual(run(rows).status, 0);
  }
  console.log('Sandbox registry ownership: 6 cases passed');
} finally { fs.rmSync(root, {recursive: true, force: true}); }

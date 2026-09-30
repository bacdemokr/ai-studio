// Restrict only this app's plan researcher. Never change OpenShell policies or other agents.
const sessions = new Map();
const TTL = 15 * 60 * 1000;
function keyFor(ctx) {
  if (!/^bac-[a-f0-9]{24}-r8$/.test(ctx.agentId || '')) return null;
  const match = (ctx.sessionKey || '').match(/:openai-user:bac-plan-([a-f0-9]{24})-8-(?:working|revising)(?:-output-retry)?$/);
  return match ? ctx.agentId + ':' + match[1] : null;
}
export function beforeTool(event, ctx) {
  const key = keyFor(ctx);
  if (!key || !['web_search', 'web_fetch'].includes(event.toolName)) return;
  const now = Date.now();
  for (const [k, v] of sessions) if (now - v.updated > TTL) sessions.delete(k);
  if (!sessions.has(key)) {
    if (sessions.size >= 1000) sessions.delete(sessions.keys().next().value);
    sessions.set(key, {searches: 0, fetches: 0, calls: new Set(), updated: now});
  }
  const state = sessions.get(key), id = event.toolCallId || ctx.toolCallId;
  state.updated = now;
  if (id && state.calls.has(id)) return;
  const blocked = event.toolName === 'web_search' ? state.searches >= 2 : state.searches > 0 || state.fetches >= 5;
  if (blocked) return {block: true, blockReason: 'Research budget reached. Save the evidence already retrieved to the assigned brief and finish. Search excerpts are not full-page reads; report missing details honestly. Do not retry browsing or switch tools.'};
  if (id) state.calls.add(id);
  if (event.toolName === 'web_search') {
    state.searches++;
    return {params: {...event.params, count: Math.min(3, Math.max(1, Number(event.params.count) || 3))}};
  }
  state.fetches++;
  return {params: {...event.params, maxChars: Math.min(4000, Math.max(1, Number(event.params.maxChars) || 3000))}};
}
function excerpt(value, limit) {
  if (typeof value !== 'string' || value.length <= limit) return value;
  // Preserve the native untrusted-content delimiters around a shortened source.
  const wrapped = value.match(/^([\s\S]*?Source: Web Search\n---\n)([\s\S]*)(\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id="[^"]+">>>\s*)$/);
  const note = '\n[Excerpt shortened by the demo; not a full-page read.]';
  return wrapped ? wrapped[1] + wrapped[2].slice(0, limit) + note + wrapped[3] : value.slice(0, limit) + note;
}
export function persistResult(event, ctx) {
  if (!keyFor(ctx) || (event.toolName || ctx.toolName) !== 'web_search' || event.message?.isError) return;
  const blocks = event.message?.content;
  if (!Array.isArray(blocks)) return;
  let envelope;
  for (const block of blocks) {
    if (block.type !== 'text') continue;
    try { const v = JSON.parse(block.text); if (Array.isArray(v.results)) { envelope = v; break; } } catch {}
  }
  if (!envelope) return;
  const results = envelope.results.slice(0, 3).filter(r => r && typeof r === 'object').map(r => {
    const row = {};
    for (const k of ['title', 'url', 'snippet', 'description', 'siteName', 'published', 'publishedDate', 'date']) {
      if (typeof r[k] === 'string') row[k] = k === 'url' ? r[k] : excerpt(r[k], ['snippet', 'description'].includes(k) ? 1200 : 300);
    }
    return row;
  });
  const bounded = {kind: envelope.kind, provider: envelope.provider, query: excerpt(envelope.query, 500),
    count: results.length, results, externalContent: envelope.externalContent,
    truncated: true, note: 'Bounded source excerpts only. Save relevant findings and finish; do not claim full-page verification.'};
  return {message: {...event.message, content: [{type: 'text', text: JSON.stringify(bounded)}], details: bounded}};
}
export default {
  id: 'bac-research-guard',
  register(api) { api.on('before_tool_call', beforeTool); api.on('tool_result_persist', persistResult); }
};

// Bound this app's research and static review. Never change OpenShell policies.
const sessions = new Map();
const reviews = new Map();
const loungeRuns = new Map();
const TTL = 15 * 60 * 1000;
function loungeKey(ctx) {
  const id = ctx.agentId || '';
  return /^bac-[a-f0-9]{24}$/.test(id) && ctx.sessionKey === `agent:${id}:openai-user:${id}` ? ctx.sessionKey : null;
}
function loungeState(event, ctx) {
  const key = loungeKey(ctx), run = event.runId || ctx.runId;
  if (!key || !run) return null;
  const now = Date.now();
  for (const [k, v] of loungeRuns) if (now - v.updated > TTL) loungeRuns.delete(k);
  if (loungeRuns.get(key)?.run !== run) {
    if (loungeRuns.size >= 1000) loungeRuns.delete(loungeRuns.keys().next().value);
    loungeRuns.set(key, {run, searches: 0, fetches: 0, calls: new Map(), updated: now});
  }
  const state = loungeRuns.get(key);state.updated = now;return state;
}
const spillFile = /(?:^|[\\/])openclaw-web-fetch-[a-f0-9]+\.log$/i;
function reviewState(ctx) {
  if (!/^bac-[a-f0-9]{24}-r4$/.test(ctx.agentId || '')) return null;
  const match = (ctx.sessionKey || '').match(/:openai-user:bac-plan-([a-f0-9]{24})-4-(?:working|revising)(?:-output-retry)?$/);
  if (!match) return null;
  const now = Date.now(), key = ctx.agentId + ':' + match[1];
  for (const [k, v] of reviews) if (now - v.updated > TTL) reviews.delete(k);
  if (!reviews.has(key)) {
    if (reviews.size >= 1000) reviews.delete(reviews.keys().next().value);
    reviews.set(key, {reads: 0, chars: 0, ranges: new Set(), calls: new Map(), results: new Map(), updated: now});
  }
  const state = reviews.get(key);state.updated = now;return state;
}
function keyFor(ctx) {
  if (!/^bac-[a-f0-9]{24}-r8$/.test(ctx.agentId || '')) return null;
  const match = (ctx.sessionKey || '').match(/:openai-user:bac-plan-([a-f0-9]{24})-8-(?:working|revising)(?:-output-retry)?$/);
  return match ? ctx.agentId + ':' + match[1] : null;
}
export function beforeTool(event, ctx) {
  if (loungeKey(ctx)) {
    const params = event.params || {};
    // Reading web_fetch's full-output file bypasses maxCharsCap.
    if (event.toolName === 'read' && spillFile.test(String(params.path || params.file_path || ''))) {
      return {block: true, blockReason: 'This web page was already returned as a bounded excerpt. Do not read its full-output file. Use the excerpt, or fetch a specific abstract/article URL if essential evidence is missing and budget remains. Report missing details honestly.'};
    }
    if (['web_search', 'web_fetch'].includes(event.toolName)) {
      const state = loungeState(event, ctx), id = event.toolCallId || ctx.toolCallId;
      if (id && state?.calls.has(id)) return state.calls.get(id);
      const search = event.toolName === 'web_search';
      const blocked = state && (search ? state.searches >= 2 : state.fetches >= 5);
      const result = blocked
        ? {block: true, blockReason: 'This request has reached its research budget. Answer now using the evidence already retrieved, with source links and any gaps. Do not repeat browsing or read full-output files. Do not invent missing findings.'}
        : {params: {...params, ...(search ? {count: Math.min(3, Math.max(1, Number(params.count) || 3))} : {maxChars: Math.min(3000, Math.max(1, Number(params.maxChars) || 3000))})}};
      if (state && !blocked) state[search ? 'searches' : 'fetches']++;
      if (id && state) state.calls.set(id, result);
      return result;
    }
  }
  const review = event.toolName === 'read' && reviewState(ctx);
  if (review) {
    const id = event.toolCallId || ctx.toolCallId;
    if (id && review.calls.has(id)) return review.calls.get(id);
    const params = event.params || {}, offset = Math.max(1, Math.floor(Number(params.offset) || 1));
    const limit = Math.min(120, Math.max(1, Math.floor(Number(params.limit) || 120)));
    const path = String(params.path || params.file_path || '').replace(/\\/g, '/').replace(/^.*\/(inbox|artifacts)\//, '$1/').replace(/^\.\//, '');
    const range = JSON.stringify([path, offset, limit]);
    const result = review.reads >= 8 || review.chars >= 18000 || review.ranges.has(range)
      ? {block: true, blockReason: 'Review read budget reached or this source range was already read. Use the evidence already returned. Do not repeat reads or guess source paths. Finish the review now; explicitly report any unread portion and unverified requirements. A limited review is not a full verification.'}
      : {params: {...params, offset, limit}};
    if (!result.block) {review.reads++;review.ranges.add(range);}
    if (id) review.calls.set(id, result);
    return result;
  }
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
  const review = (event.toolName || ctx.toolName) === 'read' && reviewState(ctx);
  if (review && !event.message?.isError && Array.isArray(event.message?.content)) {
    const id = event.message.toolCallId || event.toolCallId;
    if (id && review.results.has(id)) return review.results.get(id);
    let remaining = Math.min(5000, Math.max(0, 18000 - review.chars)), truncated = false;
    const content = event.message.content.map(block => {
      if (block.type !== 'text' || typeof block.text !== 'string') return block;
      const text = block.text.slice(0, remaining);remaining -= text.length;review.chars += text.length;
      if (text.length === block.text.length) return block;
      truncated = true;
      return {...block, text: text + '\n[Review excerpt shortened. Some source was omitted. Use a focused, unread offset/limit range if budget remains; otherwise report limited coverage. Never claim the entire file was verified.]'};
    });
    const result = truncated ? {message: {...event.message, content, details: {truncated: true, reviewCoverageLimited: true}}} : undefined;
    if (id) review.results.set(id, result);
    return result;
  }
  const personal = loungeKey(ctx), tool = event.toolName || ctx.toolName;
  if ((!keyFor(ctx) && !personal) || !['web_search', 'web_fetch'].includes(tool) || event.message?.isError) return;
  if (tool === 'web_fetch') {
    if (!personal || !Array.isArray(event.message?.content)) return;
    // Preserve source metadata and untrusted markers, but do not invite a
    // full-page reread from the native temporary file.
    const clean = value => {
      if (!value || typeof value !== 'object' || typeof value.text !== 'string' || !value.spill) return value;
      const {spill, ...rest} = value;
      return {...rest, text: value.text.replace(/\n*\[(?:Showing truncated web_fetch content\.[^\]]*|Full output[^\]]*)\]\s*$/i, '') + '\n[Excerpt only. Some page content was omitted; do not read full-output files.]', truncated: true};
    };
    return {message: {...event.message, content: event.message.content.map(block => {
      if (block.type !== 'text') return block;
      try {return {...block, text: JSON.stringify(clean(JSON.parse(block.text)))};} catch {return block;}
    }), details: clean(event.message.details)}};
  }
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

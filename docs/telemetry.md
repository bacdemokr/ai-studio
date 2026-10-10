# Runtime usage panel

The scene footer contains a compact CPU / RAM / Context meter (highest last-reported utilization among agents in the current room). Expand it for per-agent context bars; it remains available in native fullscreen. Multi-Agent demo shows the selected mission’s crew snapshots; Hiring and the lounge show personal runs. Tooltips include the observed model and timestamp when available.

- Cumulative usage (expanded panel): sum of Gateway-reported `usage.total_tokens` for captured responses, including input and output. Persisted in each job's payload, scoped to the requesting participant. This is **recorded app activity**, not a provider billing meter: old jobs, failed/lost responses and provider-unreported usage are not reconstructed. Board resets retain recorded measurements; deleting an agent removes its jobs and measurements. The default `./bac start` clears all runtime jobs, context and usage history; `./bac start --keep-data` preserves them.
- Context: latest fresh OpenClaw session prompt-token snapshot, divided by that session's resolved context budget. A snapshot updates after a response; it is not a live generation counter. Different agents can use one model while maintaining distinct sessions. Splitting context does not guarantee lower aggregate token usage.
- Avg output speed: output tokens divided by elapsed response time, including queueing, prompt processing and tools. This is not inference-only generation speed.
- CPU/RAM: app server host, not the external inference service. Linux uses `/proc/stat` deltas and `MemAvailable`. macOS CPU uses two `top` samples; RAM is active + wired + compressor physical pages, excluding inactive reclaimable cache. Samples are cached for eight seconds; UI polls every five seconds. Unsupported/unavailable values are shown as a dash.
- No credentials, prompts or transcript contents are exposed by `/api/telemetry`. Existing participant authentication and agent ownership checks apply. Reading usage does not call the model.

## OpenClaw evidence

Checked against the installed OpenClaw 2026.9.4 implementation:

- `src/gateway/openai-agent-run-usage.ts`: compatible HTTP usage prefers nonzero aggregate usage, falls back to last-call usage.
- Bundled `session-store-ynrwEWpu.mjs`: session `totalTokens` comes from `deriveSessionTotalTokens`, `totalTokensFresh`, and schema version 1, rather than aggregate input+output.
- Bundled `usage-CDPg_Rzl.mjs`: version-1 totalTokens is a context prompt-token snapshot.
- Gateway HTTP request context: agent-scoped `agent:<id>:openai-user:<user>` session key.

The collector accepts only the exact requested session, a fresh version-1 snapshot, and an update after the run started. A future incompatible runtime produces unknown context, not invented percentages. The gateway response remains string-compatible through a string subclass carrying metrics, preserving existing file/artifact generation.

Focused checks: `tests/test_telemetry.py` exercises aggregate/context separation, stale/missing values, six-role persistence, participant isolation and repeat reads. `tests/telemetry-mission.cjs` checks mission-scoped displays with fixture data; remote browser checks also cover opening Usage & time. Live inference validation requires a configured model.

## Event Brief timing

The current Event Brief crew is Riley, Dylan, Alex and Morgan. Riley is required; the other three are selected by default and can be omitted. Dylan's research and Alex's operations calls can overlap after Riley's brief. Morgan follows their selected contributions. Preparation, saved-state updates and exports are serialized; a provider may still queue concurrent calls.

A failure preserves completed contributions and blocks dependent stages. Stop waits for in-flight work before proceeding with cleanup. Older saved job schemas may include extra review, survey and event-page roles; their metrics remain readable, but those are not the current crew picker.

## Per-scenario Usage & time

After an Event Brief or Open Task run, open **Usage & time** in the scenario controls to see recorded input/output tokens and a breakdown by agent and endpoint. **Total elapsed** runs from submission to completion, including queueing and waits. **Agent time** includes the complete OpenClaw turn, including model responses and tools; it is not inference-only latency. **Turns** counts recorded agent responses, not underlying provider HTTP calls. Concurrent turns can have a combined time greater than wall time.

Repairs retain each recorded response rather than replacing the previous attempt. A saved response is counted only once. Older records remain readable, but previously overwritten attempts and failed/lost responses without usage cannot be reconstructed. Missing token values are unknown, not zero. These numbers support demo comparisons, not billing reconciliation.

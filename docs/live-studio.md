# Live Agent Studio runtime

## Execution path

Browser → session/CSRF-protected BaC API → durable SQLite queue → OpenClaw `/v1/chat/completions` → shared vLLM `bac-local` → native allowed tools → per-participant workspace → saved result and UI events.

OpenClaw 2026.9.4 is pinned. The gateway listens on `127.0.0.1:18789`, vLLM on `127.0.0.1:8000`. The gateway bearer token is an operator credential and stays in the host’s mode-0600 configuration file. The browser receives neither the token nor a raw gateway proxy.

Every participant has a random OpenClaw agent ID, native `IDENTITY.md`, `SOUL.md`, `USER.md`, `AGENTS.md`, `MEMORY.md` and `skills/bac-*/SKILL.md`. Registration happens lazily on the first task. Persona/skill changes take effect on the next task. The participant’s agent leads the crew; four additional agents have separate role workspaces and conversations. All have a model allowlist containing only `bac-vllm/bac-local`.

The serial queue and `agents.defaults.maxConcurrent=1` limit model concurrency. A waiting human decision releases the queue for other work. A restart marks interrupted tasks as needing attention rather than silently replaying potentially completed work. Due tasks persist, but the host must be running. The service uses a process lock to avoid two app workers sharing the same data directory.

## What the UI observes

Events are actual app task starts/completions, role handoffs, equipment decisions and file writes. A character walking to a station is a visualization of a task state. It is not a fine-grained native tool trace, hidden reasoning, or a measured indication that a tool is currently running. Read underlying artifacts to inspect the work. Generated HTML runs in an iframe with `sandbox=allow-scripts`, no same-origin permission and a restrictive no-network CSP. Downloads also include that CSP.

The app uses deterministic station calculations before asking the operations agent to explain them: allocate interest counts with largest remainders; groups = ceil(attendees/group size); slots = floor((duration-common)/(session+turnaround)); stations = ceil(groups/slots). Staff = one presenter per station + ceil(attendees/30) assistants + one lead. Counts describe the event being planned, not the single host Spark’s serving performance.

## Optional integrations

### Telegram

Run `./bac telegram configure` on the host. It asks for a dedicated bot token without echoing it, validates `getMe`, and refuses a bot with an existing webhook. Do not run another polling consumer on this bot. Credentials stay in `studio/telegram.json`, mode 0600.

Participants request a one-use link valid for five minutes, open their private Telegram chat and tap Start. Group messages and unpaired chats are ignored. The web and Telegram paths use the same OpenClaw agent and stable `user` session identifier. Incoming messages explicitly request a reply to that chat; there is no unsolicited broadcast or bulk invitation function. `/stop` disconnects. Polling claims an update before handling it, preventing replayed outgoing replies after restart; a crash during handling can lose that inbound message, so the user may need to retry.

This is a BaC channel adapter around the OpenClaw HTTP API. It is not the native OpenClaw Telegram plugin. The continuity demonstrated—agent identity, conversation and memory—is native OpenClaw state.

### Web search

Website reading (`web_fetch`) and Open-Meteo weather work without a search account. `./bac search configure` stores a Brave API key under the pinned release’s canonical `plugins.entries.brave.config.webSearch` and enables `web_search` only for agents with the Web explorer skill. It adds no second LLM. The host owns any provider charges. Search credentials were not available for live validation here.

### OpenShell

OpenShell is separate from OpenClaw. Start with an installed, working OpenShell CLI and gateway; then `./bac openshell enable` installs `@openclaw/openshell-sandbox@2026.9.4`, selects the `openshell` sandbox backend, session scope, read/write workspace access and **mirror** mode. Mirror mode matters because the app writes uploads/shared briefs on the host; remote mode seeds once and would not reflect those updates reliably.

`./bac openshell check` reads actual OpenShell gateway state and OpenClaw sandbox explanations/listings. After running a task, inspect the created sandbox and its policy on the host. Configuration alone is not enforcement proof, and the UI says so. Native filesystem tools route through the sandbox integration; host-side HTTP tools and the BaC Telegram adapter are not automatically isolated by it. The app’s equipment decision is an application approval, not an OpenShell network-policy approval. Browser automation is not enabled: the pinned OpenShell backend does not support sandbox browser mode.

Without OpenShell, native filesystem tools are restricted to each agent’s workspace (`tools.fs.workspaceOnly=true`). Exec, process, browser, nodes, gateway, cron, messaging and cross-agent session tools are denied; the BaC orchestrator performs controlled handoffs. These app/native tool guards are not an OS isolation boundary. Use this deployment on a trusted workshop network, not as a public adversarial multi-tenant service.

## Storage and deployment

`~/.local/share/bac-demo` (override with `BAC_DATA_DIR`):

- `models/`, `runtime/vllm-env/`: model weights and vLLM installation.
- `openclaw/node/`, `openclaw/package/`: private supported Node and pinned OpenClaw.
- `openclaw/state/`: native configuration and OpenClaw conversation state.
- `studio/studio.sqlite`: participants, queue, handoffs, schedules and pairing state.
- `studio/workspaces/`: persona/skills, uploads, memory and output files.
- `demo/releases/`, `demo/current`, `demo/previous`: immutable application releases.

`./bac update` changes only the application release and restarts its service. It preserves the LLM, OpenClaw, agent files and database. An in-flight task is marked interrupted after the restart; wait for a mission to finish before updating during a presentation. Rollback changes application code, not participant data. No destructive participant-reset control is exposed in the public UI.

## Source contract

Implementation was checked against the upstream tag, not mutable latest documentation:

- [OpenClaw v2026.9.4](https://github.com/openclaw/openclaw/tree/v2026.9.4), commit `3a9d69db306cd7f081e06254cb89c4bcc14a7107`.
- [HTTP agent API](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/gateway/openai-http-api.md).
- [Agent entries schema](https://github.com/openclaw/openclaw/blob/v2026.9.4/src/config/zod-schema.agent-entry-base.ts) and [tool policy types](https://github.com/openclaw/openclaw/blob/v2026.9.4/src/config/types.tools.ts).
- [Native agent workspaces](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/concepts/agent-workspace.md).
- [OpenShell integration](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/gateway/openshell.md).
- [Brave configuration](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/tools/brave-search.md).

Actual local validation used the installed pinned gateway with a protocol fixture behind `bac-local`, not a real LLM: agent registration (with a read-only discovery barrier for hot reload), native write/read tools, persistent memory, repeated HTTP turns and a complete five-agent crew with persisted handoffs passed. See `tests/fixture_model.py`. Spark GPU/model quality and real optional integrations still need host-side acceptance testing.

# Live Agent Studio runtime

## Execution path

Browser → session/CSRF-protected BaC API → durable SQLite queue → OpenClaw `/v1/chat/completions` → shared vLLM `bac-local` → native allowed tools → per-agent workspace → saved result and UI events.

OpenClaw 2026.9.4 is pinned. The gateway listens on `127.0.0.1:18789`, vLLM on `127.0.0.1:8000`. The gateway bearer token is an operator credential and stays in the host’s mode-0600 configuration file. The browser receives neither the token nor a raw gateway proxy.

Each personal agent has a random OpenClaw agent ID, native `IDENTITY.md`, `SOUL.md`, `USER.md`, `AGENTS.md`, `MEMORY.md` and `skills/bac-*/SKILL.md`. Registration happens lazily on the first task. Persona/skill changes take effect on the next task. The preset crew uses Milo plus four specialists, all explicitly outside OpenShell, and needs no personal onboarding. In a custom crew the selected personal agent leads, with optional assignments from the attendee’s collection. Personal assignments retain their protection mode. Assignments are frozen in each mission’s roster; each keeps its native workspace and equipped tools. Specialist crew turns use a mission-specific conversation; personal web and phone messages retain the agent’s stable conversation. All have a model allowlist containing only `bac-vllm/bac-local`.

The serial queue and `agents.defaults.maxConcurrent=1` limit model concurrency. A waiting human decision releases the queue for other work. A restart marks interrupted tasks as needing attention rather than silently replaying potentially completed work. Due tasks persist, but the host must be running. The service uses a process lock to avoid two app workers sharing the same data directory.

## Agent collections and ownership

The session cookie authenticates the participant; `X-BaC-Agent` selects one of their agents for each request. The server checks collection ownership for all agent-scoped reads and writes. Selection lives per tab, and stale polls cannot replace the newly selected workspace. No global “current agent” redirects another tab or Telegram conversation.

The `agents` table maps agent IDs to participants. Migration reuses the original participant ID for their first agent, preserving its native ID, workspace, queued jobs, reset timestamp and phone pairing. Added agents get independent IDs. One attendee may create up to 12 personal agents; the total pending-job budget remains three across that collection. Crew missions retain five distinct role slots and reject duplicate or foreign assignments. Pending assignments prevent persona/skill edits until the mission finishes or is cancelled. Reset applies only to the selected agent’s board; other agents keep their tasks.

## What the UI observes

Events are actual app task starts/completions, role handoffs, equipment decisions and file writes. A character walking to a station is a visualization of a task state. It is not a fine-grained native tool trace, hidden reasoning, or a measured indication that a tool is currently running. Read underlying artifacts to inspect the work. Generated HTML runs in an iframe with `sandbox=allow-scripts`, no same-origin permission and a restrictive no-network CSP. Downloads also include that CSP.

The app uses deterministic station calculations before asking the operations agent to explain them: allocate interest counts with largest remainders; groups = ceil(attendees/group size); slots = floor((duration-common)/(session+turnaround)); stations = ceil(groups/slots). Staff = one presenter per station + ceil(attendees/30) assistants + one lead. Counts describe the event being planned, not the single host Spark’s serving performance.

## Optional integrations

### Telegram

Run `./bac telegram configure` on the host. It asks for a dedicated bot token without echoing it, validates `getMe`, and refuses a bot with an existing webhook. Do not run another polling consumer on this bot. Credentials stay in `studio/telegram.json`, mode 0600.

Participants request a one-use link for the selected agent valid for five minutes, open their private Telegram chat and tap Start. Group messages and unpaired chats are ignored. The web and Telegram paths use the same OpenClaw agent and stable `user` session identifier. Incoming messages explicitly request a reply to that chat; there is no unsolicited broadcast or bulk invitation function. `/stop` disconnects. Polling claims an update before handling it, preventing replayed outgoing replies after restart; a crash during handling can lose that inbound message, so the user may need to retry.

Switching the web selection does not affect an existing phone pairing. Explicitly pairing another agent moves that private Telegram chat to the new agent.

This is a BaC channel adapter around the OpenClaw HTTP API. It is not the native OpenClaw Telegram plugin. The continuity demonstrated—agent identity, conversation and memory—is native OpenClaw state.

### Web search

Website reading (`web_fetch`) and Open-Meteo weather work without a search account. `./bac search configure` stores a Brave API key under the pinned release’s canonical `plugins.entries.brave.config.webSearch` and enables `web_search` only for standard agents with the Web explorer skill. OpenShell-protected agents instead use sandboxed curl and the curated Wikipedia search permission. It adds no second LLM. The host owns any provider charges. Search credentials were not available for live validation here.

### OpenShell

OpenShell is separate from OpenClaw. Start with an installed, working OpenShell CLI and gateway; then run `./bac openshell enable`. It installs `@openclaw/openshell-sandbox@2026.9.4` if needed, prepares a host-owned deny-by-default policy, and uses **mirror** mode. Run it once again after updating from a release with global sandbox defaults. It preserves the operator's gateway/workspace selection. The default is OpenShell off; only personal agents explicitly selecting protection get `mode=all`, backend `openshell`, **agent scope** and read/write workspace access. Every preset crew role explicitly uses `mode=off`.

The Onboarding and Policies tab save a personal agent's protection choice. The next mission writes its native configuration. A live `agents.list` identity fingerprint must match the new tool/sandbox configuration before sending a model request, including when switching off → on. A missing OpenShell setup fails closed. Mirror mode keeps host uploads and shared briefs available inside the sandbox.

Protected agents have host-side `web_fetch` and `web_search` disabled. Their internet reads use native `exec` with `host=sandbox` and `/usr/bin/curl`; a caller cannot redirect that configured executor to the gateway. Automatic provider attachment is disabled, and new sandboxes start with an empty network allowlist. This limits **tool network access**: shared inference and the BaC Telegram transport run on the host and are outside this policy. Browser automation is not enabled.

**Policies** lists four curated groups: Open-Meteo weather/geocoding, Zurich visitor pages, Wikipedia search, and the public GitHub API. Approval permits only the listed HTTPS destinations and read-only REST access for `/usr/bin/curl`. These demo controls never accept arbitrary YAML, shell commands, providers or credentials. Selecting a skill alone grants no network access. Switching off retains earlier approval choices; re-enabling requires checking the current sandbox policy before a mission. If a sandbox was recreated, reapply saved approvals explicitly.

The API resolves the participant-owned native agent to sandbox names through `openclaw sandbox list --json`; it never guesses or accepts a browser-supplied sandbox name. It updates that sandbox with `openshell policy set --wait`, then verifies the effective policy and its **loaded** revision against the desired permissions. Host/global policy is reported for review and is never overwritten. Pending, failed or mismatched updates remain unconfirmed and block protected missions. Mutations require idle agents, owner/session checks and CSRF. Approval history is stored separately from sanitized OpenShell access logs; no raw logs or credentials reach the browser.

`./bac openshell check` reports gateway state and native sandboxes. Configuration alone is not enforcement proof. On the actual Spark, perform this acceptance sequence:

1. Run the preset crew before onboarding; confirm all five roles are OpenShell off.
2. Create a personal agent with Weather lookout and Web explorer, with OpenShell on. Ask for Zurich's current weather. Its first task provisions the sandbox; confirm a matching deny log in Policies, not merely a generic fetch failure.
3. Approve **Weather & city lookup**, verify the loaded revision and exact two destinations, then retry and inspect the live result and matching allow log.
4. Request Wikipedia search while it remains unapproved; confirm it is denied. Revoke weather, retry weather, and confirm denial again.
5. Switch this agent off and run its standard weather tool; another protected agent must remain blocked. Reload and check saved choices. Do not change a mode while that agent has pending work.

Local tests use explicit model/policy fixtures for this sequence. Actual sandbox enforcement, endpoint responses, filesystem restrictions and real model behavior still require the Spark checks above.

Without OpenShell, native filesystem tools are restricted to each agent’s workspace (`tools.fs.workspaceOnly=true`). Exec, process, browser, nodes, gateway, cron, messaging and cross-agent session tools are denied; the BaC orchestrator performs controlled handoffs. These app/native tool guards are not an OS isolation boundary. Use this deployment on a trusted workshop network, not as a public adversarial multi-tenant service.

## Storage and deployment

`~/.local/share/bac-demo` (override with `BAC_DATA_DIR`):

- `models/`, `runtime/vllm-env/`: model weights and vLLM installation.
- `openclaw/node/`, `openclaw/package/`: private supported Node and pinned OpenClaw.
- `openclaw/policies/`: host-owned initial and per-agent policy documents, outside editable agent workspaces.
- `openclaw/state/`: native configuration and OpenClaw conversation state.
- `studio/studio.sqlite`: participants, personal agents, queue, handoffs, schedules and pairing state.
- `studio/workspaces/`: persona/skills, uploads, memory and output files.
- `demo/releases/`, `demo/current`, `demo/previous`: immutable application releases.

`./bac update` changes only the application release and restarts its service. It preserves the LLM, OpenClaw, agent files and database. An in-flight task is marked interrupted after the restart; wait for a mission to finish before updating during a presentation. Rollback changes application code, not participant data. The attendee reset archives only the selected agent’s visible board and cancels pending work; it preserves files/memory and refuses to run during active inference. A different attendee should use a new browser profile.

### OpenShell evidence lab

The 3D Access gate opens **Security lab**. Its concept walkthrough is always labeled illustrative; learner buttons do not execute requests or change policies. The host evidence tab reads a host-only capture report. Run `./bac openshell prove` to collect fixed public GET outcomes and matching OpenShell policy logs in a newly created dedicated sandbox, then clean up that sandbox. The report is timestamped and is not proof of current enforcement for the actual agents. See [scope, failure criteria and host acceptance](cohort-requirements.md).

## Source contract

Implementation was checked against the upstream tag, not mutable latest documentation:

- [OpenClaw v2026.9.4](https://github.com/openclaw/openclaw/tree/v2026.9.4), commit `3a9d69db306cd7f081e06254cb89c4bcc14a7107`.
- [HTTP agent API](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/gateway/openai-http-api.md).
- [Agent entries schema](https://github.com/openclaw/openclaw/blob/v2026.9.4/src/config/zod-schema.agent-entry-base.ts) and [tool policy types](https://github.com/openclaw/openclaw/blob/v2026.9.4/src/config/types.tools.ts).
- [Native agent workspaces](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/concepts/agent-workspace.md).
- [OpenShell integration](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/gateway/openshell.md).
- [OpenShell CLI policy inspection and loaded revision contract](https://github.com/NVIDIA/OpenShell/blob/fa0bfa490e42c87a74a70be6ebb40faee7fb8faa/crates/openshell-cli/src/run.rs), and [canonical policy schema](https://github.com/NVIDIA/OpenShell/blob/fa0bfa490e42c87a74a70be6ebb40faee7fb8faa/crates/openshell-policy-schema/src/lib.rs).
- [Brave configuration](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/tools/brave-search.md).

Actual local validation used the installed pinned gateway with a protocol fixture behind `bac-local`, not a real LLM: agent registration (with a read-only discovery barrier for hot reload), native write/read tools, persistent memory, repeated HTTP turns and a complete five-agent crew with persisted handoffs passed. See `tests/fixture_model.py`. Spark GPU/model quality and real optional integrations still need host-side acceptance testing.

The per-agent sandbox/tool configuration was also validated with the real pinned gateway in an isolated temporary state directory. Live `agents.list` reflected off → on → off configuration fingerprints. This checks native configuration and reload, not OpenShell execution or network enforcement.

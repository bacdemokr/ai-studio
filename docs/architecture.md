# Agent Studio architecture


## Runtime path

```text
Browser → Python API + SQLite queue → OpenClaw gateway → shared model endpoint
                                   ↳ host tools, or OpenShell for protected personal agents
```

The app owns accounts/agent selection, durable jobs, the fixed workflow graph, validation and rendering. OpenClaw owns native agent execution, file/tool calls and conversation sessions. A shared model serves distinct agent contexts; the scene visualizes observed app events rather than deciding task execution.

## Main code boundaries

| Area | Files |
| --- | --- |
| Single operator entry point | `bac`, `scripts/manage.py` |
| Service/model lifecycle | `ops_common.py`, `ops_deploy.py`, `ops_runtime.py`, `ops_llm.py` |
| HTTP and ownership checks | `serve.py` |
| Jobs, profiles, persistence | `studio.py` |
| Native runtime, activity and files | `agent_runtime.py`, `agent_activity.py`, `agent_documents.py` |
| Event workflow | `agent_workflow.py`, `event_agent_tools.py`, `morgan_page.py`, `crew_roundtable.py` |
| Scheduling/exports | `event_planner.py`, `event_rotation.py`, `event_timetable.py` |
| Model settings and ephemeral keys | `runtime_settings.py`, `session_secrets.py` |
| Protection and host-file grants | `agent_policy.py`, `studio_policy.py`, `file_access.py` |
| UI / 3D scene | `src/studio*`, `src/world-*`, `src/campus*`, `src/agent-character.js` |

## Event execution and attribution

Casey briefs → Dylan researches while Alex schedules booth IDs → the app binds final theme labels → Morgan writes HTML/social copy → the app validates and assembles mounts → personal agents react.

Dylan must leave observed research-tool calls and sourced files. Alex chooses staffing and explicit slots; the helper validates and exports those choices. Morgan edits a compact scaffold instead of reading a large repeated timetable. The app inserts the validated timetable into the authored page. The authored HTML and its hash remain available separately. One bounded repair is allowed; a text-only “done” cannot replace missing files. See [live-studio](live-studio.md) for the full contract.

## Results presentation

Results contains separate in-page sections for Dylan’s saved demo proposal, Alex’s schedule, Morgan’s webpage and Morgan’s social post. A role shortcut no longer jumps into Morgan’s HTML and attributes its layout to that role. Research rationale and scheduling criteria are expandable beside the relevant work; the duplicate overview is removed. Completed specialist results are available before the webpage finishes. Dylan’s View proposal / View sources and Alex’s View plan open the saved JSON in a read-only modal, with expandable fields, raw JSON and copying. JSON content is rendered as text; only HTTP(S) values become external links. Alex’s Download Excel retains the original workbook bytes. The modal has one scroll area and closing it preserves the Results position.

Dylan’s proposal fields are displayed verbatim from the validated artifact (with source IDs resolved against its research). The app assigns numbered booth labels and renders those fields. Alex’s chosen slots and rotations are expanded by the schedule tool; the displayed table and Excel use the validated assignments, with final theme labels bound by stable IDs. Each section distinguishes agent content from app rendering and offers the corresponding saved source/export.

The Results panel owns vertical scrolling. Morgan’s preview is a same-origin, **script-disabled** sandbox so the parent can measure its body with `ResizeObserver`; restrictive CSP and removal of active content also apply to old saved pages. Never add `allow-scripts` to this sandbox. Internal webpage anchors scroll the parent panel. Tables may scroll horizontally but have no capped vertical viewport. Preview-only safety/layout changes do not modify saved authored HTML or its download. Roundtable updates do not recreate the webpage or reset the reader’s position.

## Persistence and compatibility

SQLite and workspaces live outside the checkout. The session cookie authenticates the participant; `X-BaC-Agent` selects only an agent they own. Model credentials are memory-only and excluded from saved state. Native files are separate per personal agent and crew role.

The Lounge shows only Ready or Busy, derived from the individual agent’s unfinished requests and event participation. Background demo preparation never sets Lounge Busy; its identity reservation still protects cleanup and configuration. Readiness details stay in the BaC preparation panel; internal activity metadata distinguishes user requests, preparation and roundtable participation. A reservation used to protect an agent during work is not evidence of a personal mission. Delete agent cancels queued work and requests a safe stop for active work; cleanup runs between worker jobs after all calls and post-result writes finish. Pending deletion persists across restart; native cleanup failures stay fenced and require a retry. OpenShell deletion reads only the target agent’s entries through the pinned native registry API, removes those exact sandboxes, verifies their absence, then retires the records through the native locked writer. It never runs the all-sandbox health scan or recreate command. A timed-out sandbox deletion is accepted only if a fresh gateway inventory confirms that the sandbox is absent; gateway errors never count as successful cleanup. Agent cleanup calls the running OpenClaw gateway’s native `agents.delete` method first, avoiding a full deletion-command import per agent. The gateway keeps its lifecycle, shared-storage and database safeguards. The pinned native command remains the offline/deletion-journal fallback. Unknown or timed-out mutation results are never retried through the local path; retained workspace paths still block success. A sandbox already confirmed absent after a delete timeout does not trigger a duplicate inventory lookup. Partial storage cleanup failures still prevent success. Preparation provisions only the required BaC crew and sends no model request. Personal reactions are optional selections; busy or unavailable agents are excluded again at launch, and their runtimes and protection are checked just before a reaction, never as a prerequisite for starting the crew. Completed guest reactions stop showing as active even while the shared event finishes. BaC jobs do not replace the personal agent's latest reply.

The crew catalog retains six stable IDs for old jobs and cleanup; the current UI uses Casey, Dylan, Alex and Morgan. Old job schemas, exports and policy records remain readable. Removing those readers would risk existing data, so they are compatibility code rather than candidates for blind deletion.

## Demo Producer protection

Dylan's native tools run inside an agent-scoped OpenShell sandbox. Preparation, direct chat and event execution verify a loaded policy with exactly `blogs.nvidia.com:443` approved for read-only requests by `/usr/bin/curl`. Python handles research parsing and JSON files inside the sandbox; it invokes curl for network reads. Redirects must stay on that HTTPS origin. Other crew members retain their standard runtimes, and personal-agent approvals are independent.

The model still chooses search queries, reads sources and authors the demo proposals. Pre-approval does not precompute or cache model answers. Workspace files use the native mirror bridge. Model inference remains outside the tool sandbox. Verification failure stops the task; there is no host-side research fallback. Old workflows that prefetch research on the host must be started again through the current Multi-Agent demo form.

`tests/live_crew_research.py` repeats real search/read/save operations and checks unrelated-host denial in native logs. It does not call an LLM or prove complete event generation.

## Polling and performance

State is checked every 1.5 seconds while the page is visible. `/api/state` authenticates and builds the current snapshot, then returns an ETag. An unchanged conditional request returns 304 with no history body. The tab caches snapshots per agent; unchanged responses do not rebuild the UI. Agent switching and stale-response guards still apply. The server still performs its state query and hash; this is a network/render optimization, not an assertion that polling costs nothing.

SQLite indexes serve per-owner history and per-role crew chats. Runtime readiness and host metrics have short caches. The scene limits rendering to roughly 30 FPS and pauses expensive work while hidden. Large model inference remains the dominant task latency; these changes do not claim higher model tokens/second.

## Build and development

`scripts/build.py` assembles explicit UI modules, bundled Three.js and local art into `app/index.html`. No old playground code is included and no remote UI dependency is needed. Frontend rebuilds need a browser refresh; backend changes need a restart. `./bac start` manages the Docker distribution. `./bac dev preview` serves a source checkout in the foreground (`start.sh` is its compatibility alias); advanced Linux `./bac dev start` uses committed release snapshots and user services.

Python tests use temporary stores/adapters. Browser fixtures test rendering and interactions. Neither proves a real model’s quality, sandbox enforcement or Spark performance; those need host rehearsal.

## Event response latency

Casey returns the actual brief directly from the supplied organizer data; the app saves that response verbatim for the specialist handoffs. It does not ask Casey to reread the same JSON or write an extra receipt file. Native identity verification uses the pinned gateway RPC rather than loading the complete CLI. A failed event keeps the specific per-role error and any observed tool calls. Model calls are never silently replayed after a timeout.

Agent-invoked research tools fetch independent queries/articles with at most three concurrent requests. Full retrieved text stays in the research artifact; long tool responses use explicitly marked excerpts so all selected sources fit in the model-visible output. Alex must use the exact unassigned presenter label format and can finish after successful validation/export without rereading the generated timetable. Agents still choose queries, themes and schedules themselves.

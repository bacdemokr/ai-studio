# Agent Studio architecture


## Runtime path

```text
Browser → Python API + SQLite queue → OpenClaw gateway → selected model endpoint(s)
                                   ↳ host tools, or OpenShell for protected personal agents
```

The app owns accounts/agent selection, durable jobs, team orchestration, validation and rendering. OpenClaw owns native agent execution, file/tool calls and conversation sessions. Each hired agent can select its own model; the Open Task connection serves Casey and backups. Agent contexts remain separate; the scene visualizes observed app events rather than deciding task execution.

## Main code boundaries

| Area | Files |
| --- | --- |
| Single operator entry point | `bac`, `scripts/manage.py` |
| Service/model lifecycle | `ops_common.py`, `ops_deploy.py`, `ops_runtime.py`, `ops_llm.py` |
| HTTP and ownership checks | `serve.py` |
| Jobs, profiles, persistence | `studio.py` |
| Native runtime, activity and files | `agent_runtime.py`, `agent_activity.py`, `agent_documents.py` |
| Event workflow | `agent_workflow.py`, `event_agent_tools.py`, `morgan_page.py`, `crew_roundtable.py` |
| Shared connections and credentials | `model_connections.py`, `scenario_models.py`, `runtime_settings.py`, `session_secrets.py`, `team_models.py` |
| OpenShell website approvals | `agent_policy.py`, `studio_policy.py` |
| UI / 3D scene | `src/studio*`, `src/world-*`, `src/campus*`, `src/agent-character.js` |

## Open Task execution and attribution

Casey plans work for up to three specialists. Hired only uses available hired agents; Hired + Standby also permits Scout, Cody, Ada, Iris and Vera. The dispatcher validates captured team mode, identities, tools, dependencies and required handoffs before each call. Explicitly named available participants are honored. Model claims alone do not prove that a file was saved.

Each worker receives its assignment, selected input files and verified earlier handoffs. Casey checks observed results and has one shared repair/recovery allowance. Partial work remains available when a required contribution fails. Independent review uses a different agent; closing personal reactions are separate opinions.

## Results presentation

Mission Control shows actual plan bindings, assignments, handoffs and Casey's review. Results shows the team response and verified saved files, with partial work labeled clearly. HTML previews run in a restricted iframe; file access remains scoped to the authenticated account and selected workspace. Usage & time reports recorded calls and token totals without claiming provider billing accuracy.

## Persistence and compatibility

SQLite and workspaces live outside the checkout. The session cookie authenticates the participant; `X-BaC-Agent` selects only an agent they own. Browser-entered model keys are memory-only; validated `api.cfg` credentials are stored separately on the host. Neither is included in browser state or native agent definitions. See [credential storage](session-credentials.md). Native files are separate per personal agent and crew role.

The Lounge shows Ready or Busy from actual work. Open Task reserves selected hires until their calls and result writes finish. Entering Open Task pauses hired Heartbeats without starting model calls. Completed workers stay at their desks until a new confirmed plan replaces them.

Open Task preserves stable role slots and native identities across upgrades. Retired Event Brief slots are never eligible for new tasks or workspace preparation. Its historical database records remain for ownership and safe cleanup; its routes reject new work. The final Event Brief implementation is preserved in `archive/event-brief-final-2026-10-15`.

Deletion fences an identity before stopping active work. Cleanup operates only on explicitly owned native agents, sandboxes and workspaces, records partial progress, and retries failures without deleting unrelated resources. Inactive browser sessions retire after 60 minutes. See [session and model settings](runtime-settings.md).

## Polling and performance

State is checked every 1.5 seconds while the page is visible. `/api/state` authenticates and builds the current snapshot, then returns an ETag. An unchanged conditional request returns 304 with no history body. The tab caches snapshots per agent; unchanged responses do not rebuild the UI. Agent switching and stale-response guards still apply. The server still performs its state query and hash; this is a network/render optimization, not an assertion that polling costs nothing.

SQLite indexes serve per-owner history and per-role crew chats. Runtime readiness and host metrics have short caches. The scene limits rendering to roughly 30 FPS and pauses expensive work while hidden. Large model inference remains the dominant task latency; these changes do not claim higher model tokens/second.

## Build and development

`scripts/build.py` assembles explicit UI modules, bundled Three.js and local art into `app/index.html`. No old playground code is included and no remote UI dependency is needed. Frontend rebuilds need a browser refresh; backend changes need a restart. `./bac start` manages the Docker distribution. `./bac dev preview` serves a source checkout in the foreground (`launch.sh` is its development shortcut); advanced Linux `./bac dev start` uses committed release snapshots and user services.

Python tests use temporary stores/adapters. Browser fixtures test rendering and interactions. Neither proves a real model’s quality, sandbox enforcement or Spark performance; those need host rehearsal.

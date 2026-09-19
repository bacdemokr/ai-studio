# Current prototype and next integration

## What runs today

One browser session holds the event brief, its revision, agent profiles, selected view, current handoff, calculated capacity and policy choice. A and C read the same state. Buttons or campus autoplay advance a scripted workflow; autoplay pauses for human decisions. Artifact text comes from templates and planning rules, not an LLM. Data is not persisted between refreshes or shared across browsers.

The onboarding screen lets attendees customize a role and try a sample response. Joining the crew replaces that role's agent. The permission text and approval controls are illustrative; no sandbox or email provider is running.

The skill playground offers six independent missions: weather fixtures, prepared search examples, a simulated Telegram phone, a real browser-session note, local CSV analysis with a downloadable report, and a Canvas poster renderer with a downloadable PNG. The passport's name, persona and equipped skill labels transfer into team-role onboarding. The latest event brief is available to the simulated phone reply. A browser event bridge connects the playground to the planner; there is still no backend or model inference. Joining a role does not make its scripted planner tasks autonomously invoke these skills.

A Three.js r180 WebGL scene renders the initial campus. Robot paths, state labels, evidence and decision stops consume the planner snapshot through `bac:crew-state`; this is a visualization of scripted execution, not a separate orchestrator. Solo tool results are added to its evidence feed.

The UI makes no network calls. Python only serves static files. `app/index.html` is an offline standalone adaptation of the inline visualization; `src/bac-planner.html` retains its editable source.

## Intended live design — not implemented

Use one model-serving endpoint on the demo host. Every agent uses that same endpoint with a different role, persona, tool/skill set and scoped state. Select Qwen or Gemma for the whole crew, rather than loading one model per agent. The preferred Qwen3.6 NVFP4/vLLM configuration and a Gemma4 alternative still need verification on the target Spark and have separate `./bac llm` installation/start commands. They are not connected to this UI yet.

Keep authoritative brief revisions, tasks and artifacts in a backend. Emit real task events to the UI so agent movement, handoffs, blocked states and recovery correspond to actual execution. The 3D village and progress board should remain two views of the same event stream.

| Role | Input | Output / dependency |
|---|---|---|
| Event lead | Attendee's brief and constraints | Shared brief, tasks and decisions |
| Demo producer | Audience, topics and session time | Runbooks, device needs, fallback examples |
| Operations | Runbooks, demand and available equipment | Stations, staffing and schedule |
| Marketing | Approved brief and operations plan | Localized invitation and promotional drafts |
| Reviewer | Brief revision and artifacts | Consistency findings and unresolved items |

Visible collaboration should focus on consequential dependencies: changing the session format changes required stations; resolving a device shortage changes the schedule; marketing then updates its draft against that new brief version. Separate roles are useful for focused context, tool access and review. This design does not imply that several agents make a single model execute faster.

Integrate OpenShell around actual tool execution, with role-scoped access and policy decisions surfaced in the UI. An approval, denial or recovery animation should be backed by a real execution result. Do not label the current simulation as enforcement.

## Sizing assumptions

1. Allocate attendees to topics by percentages, using largest remainder rounding so counts sum exactly to the total.
2. Groups per topic = ceil(topic attendees / people per group).
3. Usable minutes = event duration minus welcome and breaks.
4. Slots per station = floor(usable minutes / (session minutes + turnaround minutes)).
5. Dedicated stations per topic = ceil(groups / slots).
6. Sum stations by their assigned device type.
7. Staff = one presenter per station + ceil(attendees / helper ratio) + one event lead.

The model assumes a dedicated station for each active topic, one device per station, and one topic per attendee. It does not model travel between rooms, presenter breaks, power, venue limits or inference contention. These are event planning estimates and should remain distinct from measurements of the host Spark's model-serving performance.

## Suggested next implementation order

1. Backend run state, durable artifact revisions and a shared model client.
2. Real role execution with bounded concurrency on a measured Spark serving configuration.
3. OpenShell tool boundaries and observable approval/denial/recovery.
4. Connect the existing 3D scene to backend execution events instead of the scripted browser state.
5. Add restart/reset, prepared fallback artifacts and multi-attendee session isolation.

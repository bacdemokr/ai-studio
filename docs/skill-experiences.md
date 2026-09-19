> Historical guide for the original offline rehearsal. The current main Agent Studio is documented in [live-studio.md](live-studio.md) and the repository README.

# From a personal agent to a collaborating crew

## Attendee journey

1. **Meet your agent.** Choose a name and a persona. The same agent appears across the missions and later in a team role.
2. **Teach one skill.** Equip Weather lookout or Web scout. Run a short mission, inspect the input and result, and try again without the skill.
3. **Explore access.** A skill may be equipped while the tool connection is blocked. Inspect the stopped step, allow one simulated attempt, or keep it blocked.
4. **Make it personal.** Save a session preference and watch another mission reuse it. Forgetting clears the note.
5. **Take it to your phone.** The intended live Telegram experience is another way to talk to that same agent. The current UI uses a clearly labeled practice phone.
6. **Join the crew.** Choose a role for your agent. Shared inputs and dependent artifacts make handoffs useful: the demo format changes operations, and the operations decision changes marketing copy.

Participants can stop after any solo mission. Planning an event is one team activity within the playground.

## Six experiences

| Experience | Visible learning moment | Current state | Live implementation needed |
|---|---|---|---|
| Weather | Tool data → recommendation; a persona changes presentation | Fictional city fixtures, skill and access checks | Weather provider adapter, real location resolution, units, forecast timestamps and attribution |
| Web search | Search results → inspectable sources → supported summary | Prepared example cards, not external sources | Search provider or browser adapter; URLs and excerpts from actual results; source-aware summary through the shared model |
| Telegram | A phone request reaches the same agent and receives its answer | Practice pairing, draft reply, simulated access decision | Bot adapter, attendee/session pairing, inbound routing and explicit destination-aware outbound actions |
| CSV analysis | Uploaded rows become an inspectable chart and downloadable report | Actual browser calculation, strict columns and validation, no upload | Shared-model interpretation and a sandboxed backend for broader formats |
| Poster studio | Brief changes produce a new downloadable visual artifact | Actual Canvas layout rendered to PNG; en/ko/ja template headlines | Model-written copy or an image-generation adapter, with provenance |
| Remember me | A preference affects the next task; forgetting removes it | One browser-session note, reused in practice outputs | Session-isolated durable storage, retrieval into agent context and deletion controls |

Telegram is a communication channel. It should reuse the attendee's agent identity, tools and session context rather than require an unrelated agent with a separate model. The interface may present connecting that channel as a skill to make onboarding approachable.

No tool in the current preview makes an external request. The practice permission controls illustrate a decision; they do not configure or enforce OpenShell policy.

## The current 3D experience

The initial screen is a real WebGL campus with Event HQ, Demo Studio, Operations, Marketing, Review, a shared-brief hub and an access gate. Robots walk and carry a small document during scripted handoffs. Click a robot or a roster button to inspect the role's persona, skills, task and access. Drag to orbit, scroll to zoom, or pause scene motion.

Run the crew to advance the same planner state used by the C progress board. It stops at a resource shortage and at the simulated delivery boundary. Agent onboarding updates the role and passport in both views. This is not independent model reasoning; moving robots do not imply that an LLM or OpenShell is running.

The Data analyst and Poster studio tiles lead to actual local tools. Their completion events appear in the campus evidence feed; solo skill runs do not currently move a character to a separate skill station. All work is local to one browser session.

## Shared Spark runtime

All agents should use one model endpoint. Tools such as fetching weather or receiving Telegram messages perform their own I/O; summarizing or choosing an action uses that shared model. Bound concurrent inference requests and measure latency on the target Spark before setting attendee capacity. Changing from the preferred Qwen setup to a Gemma alternative is a host-wide model selection, not one model per character.

OpenShell integration belongs around actual tool execution. Start with a visible read-only weather/search boundary, then demonstrate an outbound request that needs a decision and a recoverable denial. Policies and logs need to come from the real runtime before the UI can label a run as protected.

For live Telegram, pair each attendee session with its own destination. A single global last-chat destination is unsuitable for an event with simultaneous attendees. Keep bot credentials on the backend and show only pairing state and destination in the participant UI. The current preview asks for no credentials.

## References inspected

- [bac-demo-kr agent bridge, commit a205ea8](https://github.com/yechank-nvidia/bac-demo-kr/blob/a205ea8b228a6e77f88199649f3f9b6dc55f8655/lobster-classic-ui/agent-bridge.mjs): separate search/news, Telegram, photo-intake and content-generation paths. This supports offering multiple small experiences alongside team workflows.
- [bac-snu-demo server, commit 670d112](https://github.com/bacdemokr/bac-snu-demo/blob/670d11200276d2de56b6d2673a6c9a246d95c3de/app/server.js): browser search through `getSearch`, role-specific agents and a two-way Telegram bridge using `getUpdates` and `sendMessage`. The inspected bridge keeps a global last-chat target; the planned attendee pairing should instead be session-specific.

These repositories were reviewed as implementation references. This playground does not copy or connect their live backend code.

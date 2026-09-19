# From a personal agent to a collaborating crew

## Attendee journey

1. **Meet your agent.** Choose a name and a persona. The same agent appears across the missions and later in a team role.
2. **Teach one skill.** Equip Weather lookout or Web scout. Run a short mission, inspect the input and result, and try again without the skill.
3. **Explore access.** A skill may be equipped while the tool connection is blocked. Inspect the stopped step, allow one simulated attempt, or keep it blocked.
4. **Make it personal.** Save a session preference and watch another mission reuse it. Forgetting clears the note.
5. **Take it to your phone.** The intended live Telegram experience is another way to talk to that same agent. The current UI uses a clearly labeled practice phone.
6. **Join the crew.** Choose a role for your agent. Shared inputs and dependent artifacts make handoffs useful: the demo format changes operations, and the operations decision changes marketing copy.

Participants can stop after any solo mission. Planning an event is one team activity within the playground.

## First four experiences

| Experience | Visible learning moment | Current state | Live implementation needed |
|---|---|---|---|
| Weather | Tool data → recommendation; a persona changes presentation | Fictional city fixtures, skill and access checks | Weather provider adapter, real location resolution, units, forecast timestamps and attribution |
| Web search | Search results → inspectable sources → supported summary | Prepared example cards, not external sources | Search provider or browser adapter; URLs and excerpts from actual results; source-aware summary through the shared model |
| Telegram | A phone request reaches the same agent and receives its answer | Practice pairing, draft reply, simulated access decision | Bot adapter, attendee/session pairing, inbound routing and explicit destination-aware outbound actions |
| Remember me | A preference affects the next task; forgetting removes it | One browser-session note, reused in practice outputs | Session-isolated durable storage, retrieval into agent context and deletion controls |

Telegram is a communication channel. It should reuse the attendee's agent identity, tools and session context rather than require an unrelated agent with a separate model. The interface may present connecting that channel as a skill to make onboarding approachable.

No tool in the current preview makes an external request. The practice permission controls illustrate a decision; they do not configure or enforce OpenShell policy.

## How to make the eventual 3D view useful

Give the village recognizable places: a weather station, a research desk, a phone booth and the event studio. An agent's current activity should move or highlight it at the relevant place. Clicking it reveals the actual request, selected skill, access outcome and resulting artifact. Moving from a solo mission into the event studio preserves its name, persona and equipped skills.

Drive those changes from real execution events once the backend exists. Keep the C progress board for the same run's dependencies, blocked tasks and results. The current implementation still uses CSS panels rather than a 3D scene.

## Shared Spark runtime

All agents should use one model endpoint. Tools such as fetching weather or receiving Telegram messages perform their own I/O; summarizing or choosing an action uses that shared model. Bound concurrent inference requests and measure latency on the target Spark before setting attendee capacity. Changing from the preferred Qwen setup to a Gemma alternative is a host-wide model selection, not one model per character.

OpenShell integration belongs around actual tool execution. Start with a visible read-only weather/search boundary, then demonstrate an outbound request that needs a decision and a recoverable denial. Policies and logs need to come from the real runtime before the UI can label a run as protected.

For live Telegram, pair each attendee session with its own destination. A single global last-chat destination is unsuitable for an event with simultaneous attendees. Keep bot credentials on the backend and show only pairing state and destination in the participant UI. The current preview asks for no credentials.

## References inspected

- [bac-demo-kr agent bridge, commit a205ea8](https://github.com/yechank-nvidia/bac-demo-kr/blob/a205ea8b228a6e77f88199649f3f9b6dc55f8655/lobster-classic-ui/agent-bridge.mjs): separate search/news, Telegram, photo-intake and content-generation paths. This supports offering multiple small experiences alongside team workflows.
- [bac-snu-demo server, commit 670d112](https://github.com/bacdemokr/bac-snu-demo/blob/670d11200276d2de56b6d2673a6c9a246d95c3de/app/server.js): browser search through `getSearch`, role-specific agents and a two-way Telegram bridge using `getUpdates` and `sendMessage`. The inspected bridge keeps a global last-chat target; the planned attendee pairing should instead be session-specific.

These repositories were reviewed as implementation references. This playground does not copy or connect their live backend code.

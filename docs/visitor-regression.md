# Visitor-team regression checks

Use this checklist alongside the general demo regression workflow. Run destructive, reset, connection-loss and concurrency cases with isolated data and participants. Preserve the presenter's agents and settings.

## Team and identity coverage

| Journey | Expected behavior |
| --- | --- |
| Fresh Open Task, reload, and reset | Hired only is selected. Casey remains coordinator. |
| Hired only with no available hires | Clear guidance; no hidden standby dispatch. Distinguish no hires from busy hires. |
| Hired only with one or several hires | Every dispatched specialist is bound to an available hire. No Cody/Scout arrival, fallback or model call. |
| Hired + Standby with and without hires | Suitable hires are preferred; backups can fill missing capabilities. |
| Explicit participant requests | Name a hire and Scout together; verify both actual outputs, not only names in the plan. |
| Out-of-role hire | Ask a Weather buddy to build a counter. Role labels are not eligibility requirements. Existing tools and policy still apply. |
| Unnamed Weather-only team | Ask for research and a webpage without naming hires. Casey uses available file/public-page tools instead of requiring Coding or Web research presets. |
| Two hires with the same preset | Assign author/checker or research/page duties. Verify both named contributions and actual handoff use. Duplicate planner role numbers receive one bounded correction before dispatch; identities stay intact. |
| Missing actual tools | A Programmer-only team cannot claim live web research when no web tools exist. Explain the specific missing capability, with no hidden standby dispatch or fabricated evidence. |
| Reservations and concurrent work | Busy, deleting and reserved hires are unavailable. Heartbeat does not overlap an assigned foreground task. |
| Team-mode changes | During work the control is locked. Afterward, switching preserves prior results and identities; the next task uses the selected mode. |
| Navigation | Hires wait on benches, move only when assigned, and remain selectable across Hiring, Lounge and Open Task. |

## Models, roles and permissions

- Change an idle hire's model from its Open Task badge using search and keyboard navigation. Confirm the same model in Lounge, after reload, and during execution. Preserve its name, persona, skills, protection and saved work.
- Before any plan exists, select two waiting hires in turn using their nameplates, keyboard and 3D bodies. Each opens its own panel and model picker without creating a task. Check polling, a saved Casey draft, deletion while the picker is open, assignment into a real role, completed contributions and navigation to Lounge/Event Brief. `node tests/standby-selection-browser.cjs` covers these journeys with disposable data and simulated inference.
- Change Casey's and a built-in specialist's NVIDIA model from their Open Task badge or the standby list. Confirm the next reply uses the selected model and reload preserves it. Lock an already open picker when work starts or the connection drops, recover after completion/reconnect, and reject a save raced against a new task. Other members and Event Brief must remain unchanged. Run `node tests/captain-model-browser.cjs` for the isolated browser/dispatcher journey with simulated inference.
- Disable disconnected choices. Test Local-only, API-only, both connected, neither connected, and a previously selected model that disappears. Report fixture coverage separately from real Local/Spark execution.
- Race a model selection against a new reservation or deletion. The server must reject a stale change without affecting another agent.
- Exercise Programmer and Web researcher in Lounge and a collaboration. Inspect actual saved files, brief source links, persona, and working page controls.
- For protected researchers, verify both policy-denied web access and permitted workspace handoff writes. A simulated denial does not validate real OpenShell enforcement.
- Exercise default deny, per-agent approval, revocation and a remote HTTP error after approval. Only fresh native policy denials should add an OpenShell explanation to a hired handoff; old events, another agent's events and ordinary HTTP/tool failures must not do so.
- Pair a protected researcher with a standard programmer. Preserve the blocked research limitation in the final result while completing work possible from supplied data; do not silently reroute denied retrieval through the other agent. Test protected Weather-only offline work as well.
- Submit immediately after hiring a protected agent. A running preparation must be described as preparing, preserve the draft and never substitute another participant. Retry after readiness.
- Confirm Event Brief retains its fixed team, independent connection and results.

## Results and recovery

- Run all four unchanged BB prompts in [the scenario collection](../README_POSSIBLESCENARIOS.md), including the store-email attachment. Record delivery time, participants, model/endpoint, completeness and artifact quality.
- Travel: verify dates, weather availability and source links. The original prompt says three days but spans October 17-20; record the interpretation and missing evidence rather than treating a partial result as success.
- Drone research: verify paper identity, age and claimed NVIDIA connection. Label missing or unverified evidence; never accept plausible-looking links alone.
- Store email: reconcile all five stores, percentages, margin versus profit, proposed budgets and actions against the attachment. Inspect the final revised page, not an earlier saved draft.
- Ping-pong: test A/Q and P/M, simultaneous keys, release, scoring, focus and restart inside the app preview. A saved HTML file alone is not a functional pass.
- Open previews, downloads, Mission Control deliverables and Usage & time. Retain earlier drafts, but verify that the current preview opens the final result.
- Inject connection loss before work and after a saved contribution. The former must fail clearly; the latter must expose partial results and files without automatically repeating completed work.
- Delay reset acknowledgement, then test failure and success. Lock the prompt, upload and team controls immediately; preserve an existing draft on failure and keep a new post-reset draft through later polling.
- Check localhost and the machine's actual LAN HTTP address. Host-header simulation alone is insufficient for a remote-browser claim.

## Repeatable checks

Run the Python suite with `python3 -B -m unittest discover -s tests`. Browser suites need Playwright, Chrome and permission to start local fixture servers. Relevant entry points include:

- `tests/team-modes-browser.cjs`, `tests/visitor-teams-browser.cjs`, `tests/visitor-travel-browser.cjs`, `tests/visitor-protection-browser.cjs`
- `tests/personal-models-browser.cjs`, `tests/scenario-models-browser.cjs`, `tests/hiring-role-skills-browser.cjs`
- `tests/reset-draft-browser.cjs`, `tests/scenario-isolation-browser.cjs`, `tests/remote-access-browser.cjs`

Inspect each runner's fixture setup before executing it. Record PASS, FAIL or BLOCKED for each journey, separate real API runs from fixtures, and keep hardware or policy limitations explicit. Include the failure reproduction and successful recheck when a regression is fixed.

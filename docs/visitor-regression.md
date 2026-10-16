# Visitor-team regression checks

Use this checklist alongside the general demo regression workflow. Run destructive, reset, connection-loss and concurrency cases with isolated data and participants. Preserve the presenter's agents and settings.

## Team and identity coverage

| Journey | Expected behavior |
| --- | --- |
| Fresh Open Task, reload, and reset | Hired only is selected. Casey remains coordinator. |
| Hired only with no available hires | Clear guidance; no hidden standby dispatch. Distinguish no hires from busy hires. |
| Hired only with one or several hires | Every dispatched specialist is bound to an available hire. No Cody/Scout arrival, fallback or model call. |
| Hired + Standby with and without hires | Suitable hires are preferred; backups can fill missing capabilities. |
| Explicit participant requests | In Hired + Standby, name a suitable hire and Scout together; verify both actual outputs. In Hired only, never dispatch Scout. An out-of-scope named hire must be declined. |
| Out-of-role hire | Ask a Weather buddy with Live weather only to build a counter; decline it. Equip Coding and repeat; the skill can extend scope if actual tools permit the work. |
| Unnamed Weather-only team | Ask for company research and an interactive webpage. Tool availability alone must not justify assignment. Explain the missing expertise without inventing work or calling standby. |
| Two hires with the same preset | Assign distinct in-scope duties, such as two research questions for two researchers. Do not treat a research role alone as permission to implement a webpage. Verify both named contributions and actual handoff use. Duplicate planner role numbers receive one bounded correction before dispatch; identities stay intact. |
| Missing actual tools | A Programmer-only team cannot claim live web research when no web tools exist. Explain the specific missing capability, with no hidden standby dispatch or fabricated evidence. |
| Skill requirements | No preset or custom purpose can receive coding or HTML tasks without Coding. Check correction before dispatch, including HTML disguised as research. Other assignments must fit an equipped skill too; Weather does not authorize business analysis. |
| Reservations and concurrent work | Busy, deleting and reserved hires are unavailable. Heartbeat does not overlap an assigned foreground task. |
| Team-mode changes | During work the control is locked. Afterward, switching preserves prior results and identities; the next task uses the selected mode. |
| Navigation | Hires wait on benches, move only when assigned, and remain selectable across Hiring, Lounge and Open Task. |

Check that Casey’s chat and Mission Control show the saved reason for each selection and declined named hire, with historical names preserved. Legacy plans without reasons must remain readable. These explanations must not expand the scene speech bubbles.

## Models, roles and permissions

- Change an idle hire's model from its Open Task badge using search and keyboard navigation. Confirm the same model in Lounge, after reload, and during execution. Preserve its name, persona, skills, protection and saved work.
- Before any plan exists, select two waiting hires in turn using their nameplates, keyboard and 3D bodies. Each opens its own panel and model picker without creating a task. Check polling, a saved Casey draft, deletion while the picker is open, assignment into a real role, completed contributions and navigation to Lounge/Hiring. `node tests/standby-selection-browser.cjs` covers these journeys with disposable data and simulated inference.
- Change Casey's and a built-in specialist's NVIDIA model from their Open Task badge or the standby list. Confirm the next reply uses the selected model and reload preserves it. Lock an already open picker when work starts or the connection drops, recover after completion/reconnect, and reject a save raced against a new task. Other members must remain unchanged. Run `node tests/captain-model-browser.cjs` for the isolated browser/dispatcher journey with simulated inference.
- Disable disconnected choices. Test Local-only, API-only, both connected, neither connected, and a previously selected model that disappears. Report fixture coverage separately from real Local/Spark execution.
- Race a model selection against a new reservation or deletion. The server must reject a stale change without affecting another agent.
- Exercise Programmer and Web researcher in Lounge and a collaboration. Inspect actual saved files, brief source links, persona, and working page controls.
- For protected researchers, verify both policy-denied web access and permitted workspace handoff writes. A simulated denial does not validate real OpenShell enforcement.
- Exercise default deny, per-agent approval, revocation and a remote HTTP error after approval. Only fresh native policy denials should add an OpenShell explanation to a hired handoff; old events, another agent's events and ordinary HTTP/tool failures must not do so.
- Pair a protected researcher with a standard programmer. Preserve the blocked research limitation in the final result while completing work possible from supplied data; do not silently reroute denied retrieval through the other agent. Test protected Weather-only offline work as well.
- Submit immediately after hiring a protected agent. A running preparation must be described as preparing, preserve the draft and never substitute another participant. Retry after readiness.
- Confirm Stage 3 opens Open Task directly. No Event Brief room, setting, reset or background preparation request may appear, including after loading a saved session from the archived version.

## Results and recovery

Exercise every current example in `src/goal-examples.json` with its suggested skills, then remove a required skill and repeat. Verify both an equipped hired team and Hired + Standby calling suitable backups; absence of a failure is not proof of successful dispatch. A partial or unavailable outcome is correct when the remaining roles cannot complete the request; distinguish it from an execution failure. Check that the Programmer preset always includes fixed Coding Web researcher always includes fixed Web research, and Data analyst always includes fixed Data interpretation, including API saves and old-profile upgrades. Include a custom developer without Coding (must decline), Weather buddy with Coding (may implement), two same-role hires, the Data analyst preset with Data interpretation, and Hired + Standby filling a missing role. For the event example, use the supplied agenda and produce the page and announcement; no Event planner preset is required. Keep original BB prompts separate from these current UI templates.

Bill splitter explicitly requests one Coding specialist; verify that Casey does not recruit a second agent. Travel requests three different specialists: Web research, UX design and Coding, with both handoffs used by the implementation. The other example chips request two different specialists. Verify the requested number of distinct runtime identities actually contribute. Two plan labels, a spectator reaction, or one identity assigned more than once do not count. If Hired only lacks enough suitable hires, it must not claim the requested workflow was fulfilled. Ping-pong recommends UX design + Coding: verify Iris (or a UX design hire) saves a concise interaction spec and Cody (or a Coding hire) implements from it.

For each example, map the tooltip's suggested skills to saved hire profiles and the actual standby catalog. Inspect actual called IDs, equipped skills, model, assigned work, saved handoffs and final outputs. A plan that names Ada but never calls her is a failure. If a suggested skill exists in standby, a suitable standby must be called and complete its portion. Do not accept an unnecessary refusal or a mismatched hire doing the work as a positive pass. Test removing a suitable hire and rerunning with its standby replacement. Also check Hired only never calls that replacement. The compact Travel template needs Web research + UX design + Coding for three official tourism stops; it excludes weather research. Slack announcements currently requires a hire for the full Event page suggested team; record that availability limitation rather than inventing standby qualifications.

GPU portfolio: use the attached `scenario/datacenter_gpu_portfolio.csv` and the oracle in its companion Markdown. Require Data interpretation analysis followed by Coding consuming the saved brief to build the HTML dashboard. Verify both participants and handoff use, the top-five CSV/chart (exactly five, stable ties), the 11-product comparison, normalized bandwidth units, same-TDP memory findings and demo/upper-limit labels. No rack multiplication, unsupported efficiency claims or outside research. Run an equipped hired pair and Ada + Cody as standby. Remove Coding or Data interpretation in Hired only: a truthful partial/unavailable result is valid, but full completion by the wrong specialist is not. Weather-only must not perform either portion. Switch store email -> GPU CSV -> another example; only the selected sample should be attached, while manual uploads retain their selection.

After submitting an example, verify that its sample attachment is released from the next draft immediately, while manually attached files keep their selection. For Bill splitter, check blank/non-finite/negative inputs, whole-person validation, calculations, keyboard controls and reset. A custom developer without Coding must not produce a game; the Programmer preset cannot drop its fixed Coding skill. For games produced with Coding, verify simultaneous keys, key release, leaving the preview, restart, both paddle collisions and scoring.

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

Run the Python suite with `python3 -B -m unittest discover -s tests`. Browser suites need Playwright, Chrome and permission to start local fixture servers. The following browser list is intentionally non-exhaustive; relevant entry points include:

- `tests/team-modes-browser.cjs`, `tests/visitor-teams-browser.cjs`, `tests/visitor-travel-browser.cjs`, `tests/visitor-protection-browser.cjs`
- `tests/personal-models-browser.cjs`, `tests/captain-model-browser.cjs`, `tests/standby-selection-browser.cjs`, `tests/hiring-role-skills-browser.cjs`
- `tests/open-task-only-browser.cjs`, `tests/open-task-settlement-browser.cjs`, `tests/open-task-heartbeat-browser.cjs`
- `tests/visitor-planning-presence-browser.cjs`, `tests/visitor-seating-browser.cjs`, `tests/team-selection-browser.cjs`
- `tests/reset-draft-browser.cjs`, `tests/remote-access-browser.cjs`

Inspect each runner's fixture setup before executing it. Record PASS, FAIL or BLOCKED for each journey, separate real API runs from fixtures, and keep hardware or policy limitations explicit. Include the failure reproduction and successful recheck when a regression is fixed.

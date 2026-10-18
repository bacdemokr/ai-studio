# Live Agent Studio runtime

## Execution path

Stage 3 is Open Task. Send `/goal` in Casey's chat to start team work. Conversations, documents and results persist when changing rooms. Other specialists and Lounge agents without Tech Radar accept direct messages; Tech Radar uses autonomous Heartbeat. Unsupported `/goal` submissions are rejected before a job starts.

In Open Task, Mission Control starts empty, then shows the current plan’s actual assignments, contributions and decisions. Results shows files and the response from that plan only. Casey coordinates your hires in **Hired only** (default). **Hired + Standby** also makes Scout, Cody, Ada, Iris and Vera available as backups. Any hired role can participate in relevant work. Substantive assignments must match the explicitly equipped skill as well as actual tool permissions; naming an agent does not override a mismatch. Legacy role indexes remain reserved for saved workspace compatibility.


## Agent collections and ownership


The session cookie authenticates the participant; `X-BaC-Agent` selects one of their agents for each request. The server checks collection ownership for all agent-scoped reads and writes. Selection lives per tab, and stale polls cannot replace the newly selected workspace. No global “current agent” redirects another tab.

The `agents` table maps agent IDs to participants. Migration reuses the original participant ID for their first agent, preserving its native ID, workspace, queued jobs, reset timestamp and phone pairing. Added agents get independent IDs. One attendee may create up to 12 personal agents; the total pending-job budget remains three across that collection. Open Task assigns up to three distinct specialists, with saved role indexes describing assignments rather than requiring a particular named agent. Duplicate or foreign assignments are rejected. Pending assignments prevent persona/skill edits until the mission finishes or is cancelled. Scenario reset clears only the selected Stage 3 scenario; hired agents and their own files are preserved. Remove agents deletes personal agents and their data.

## What the UI observes

Events represent actual app task starts/completions, assignments, handoffs and file writes. Character movement visualizes task state; it is not a native tool trace or hidden reasoning. Casey’s chat and Mission Control show saved role/skill selection reasons and declined named agents. Read actual artifacts and observed tool activity to inspect the work.

Self-contained HTML pages and games use a script-enabled iframe without same-origin permission and with a restrictive no-network CSP. Downloads also include a restrictive CSP. The former Event Brief survey, event catalogue and replanning routes return HTTP 410; they are not active compatibility features. The final Event Brief version remains on the archive branch.

## Optional integrations

### Web search

Standard research agents use the bundled keyless Parallel search provider when configured by runtime setup. Website reading and weather also work without a paid search account. OpenShell-protected agents use sandboxed curl and approved destinations instead of host-side web tools. See the bounded research behavior below.

### OpenShell

OpenShell is separate from OpenClaw. Start with an installed, working OpenShell CLI and gateway; the first protected run now automatically prepares the OpenClaw integration (the host CLI `./bac dev openshell enable` remains available). It installs `@openclaw/openshell-sandbox@2026.9.4` if needed, prepares a host-owned deny-by-default policy, and uses **mirror** mode. Outdated integration settings are repaired on the first protected run. Concurrent setup attempts are serialized; setup errors stop the protected request. Setup requests a safe gateway restart to reload plugin registration; it checks readiness before continuing. It preserves the operator's gateway/workspace selection. The default is OpenShell off; only personal agents explicitly selecting protection get `mode=all`, backend `openshell`, **agent scope** and read/write workspace access. Current built-in Open Task specialists use standard mode. Hired agents keep their individual protection in the Lounge and Open Task. Policy activation is checked during preparation and before protected calls; assigning research does not grant destinations.

The Hiring and Policies tab save a personal agent's protection choice. The next mission writes its native configuration. A live `agents.list` identity fingerprint must match the new tool/sandbox configuration before sending a model request, including when switching off → on. A missing OpenShell setup fails closed. Mirror mode keeps host uploads and shared briefs available inside the sandbox.

Protected agents have host-side `web_fetch` and `web_search` disabled. Their internet reads use native `exec` with `host=sandbox` and `/usr/bin/curl`; a caller cannot redirect that configured executor to the gateway. Automatic provider attachment is disabled, and new sandboxes start with an empty network allowlist. This limits **tool network access**: shared inference runs on the host and is outside this policy. Browser automation is not enabled.

**Approved websites** lists five curated groups: arXiv, weather/city lookup, Zurich visitor pages, Wikipedia search, and the public GitHub API. The weather group covers api.open-meteo.com, geocoding-api.open-meteo.com and wttr.in. Groups are approval shortcuts: saved approvals and the approved list contain one entry per exact hostname, without overlaps. Each hostname can be revoked independently. Existing group-shaped records are expanded for display while their original native policy is verified; the next explicit policy edit stores the individual grants. Pending requests may also propose an exact validated public hostname. Approval permits only the listed HTTPS destinations and read-only REST access for `/usr/bin/curl`. These demo controls never accept arbitrary YAML, shell commands, providers or credentials. Selecting a skill alone grants no network access. Switching off retains earlier approval choices; re-enabling requires checking the current sandbox policy before a mission. If a sandbox was recreated, reapply saved approvals explicitly.

The API resolves the participant-owned native agent to sandbox names through `openclaw sandbox list --json`; it never guesses or accepts a browser-supplied sandbox name. It updates that sandbox with `openshell policy set --wait`, then verifies the effective policy and its **loaded** revision against the desired permissions. Host/global policy is reported for review and is never overwritten. Pending, failed or mismatched updates remain unconfirmed and block protected missions. Mutations require idle agents, owner/session checks and CSRF. Approval history is stored separately from sanitized OpenShell access logs; no raw logs or credentials reach the browser.

`./bac dev openshell check` reports gateway state and native sandboxes. Configuration alone is not enforcement proof. On the actual Spark, perform this acceptance sequence:

1. Create a personal agent with Live weather and Web research, with OpenShell on. Ask for Zurich's current weather. Its first task provisions the sandbox; confirm a matching deny log in Policies, not merely a generic fetch failure.
2. Approve **Weather & city lookup**, verify the loaded revision and exact three destinations, then retry and inspect the live result and matching allow log.
3. Request Wikipedia search while it remains unapproved; confirm it is denied. Revoke weather, retry weather, and confirm denial again.
4. Switch this agent off and run its standard weather tool; another protected agent must remain blocked. Reload and check saved choices. Do not change a mode while that agent has pending work.

Local tests use explicit model/policy fixtures for this sequence. Actual sandbox enforcement, endpoint responses, filesystem restrictions and real model behavior still require the Spark checks above.

Without OpenShell, native read/write/edit tools can access user-requested host paths (`tools.fs.workspaceOnly=false`); host OS permissions still apply and workspace remains the default output location. Protected agents use workspace-only native file tools and user uploads. Website approvals change actual OpenShell network rules; they never import host files or write back to host paths. Exec, process, browser, nodes, gateway, cron, messaging and cross-agent session tools are denied; the BaC orchestrator performs controlled handoffs. These app/native tool guards are not an OS isolation boundary. Use this deployment on a trusted workshop network, not as a public adversarial multi-tenant service.

## Storage and deployment

`~/.local/share/bac-demo` (override with `BAC_DATA_DIR`):

- `models/`, `runtime/vllm-env/`: model weights and vLLM installation.
- `openclaw/node/`, `openclaw/package/`: private supported Node and pinned OpenClaw.
- `openclaw/policies/`: host-owned initial and per-agent policy documents, outside editable agent workspaces.
- `openclaw/state/`: native configuration and OpenClaw conversation state.
- `studio/studio.sqlite`: participants, personal agents, queue, handoffs, schedules and pairing state.
- `studio/workspaces/`: persona/skills, uploads, memory and output files.
- `demo/releases/`, `demo/current`, `demo/previous`: immutable application releases.

`./bac dev update` changes only the application release and restarts its service. It preserves the LLM, OpenClaw, agent files and database. Managed updates and rollback refuse pending missions or policy changes; finish or stop them in the app first. An unexpected server interruption still marks running tasks as needing attention. Rollback changes application code, not participant data. Use the app’s separate Open Task reset controls to clear a scenario after active work stops. Remove agents deletes personal agents and their files; Reset all clears both scenarios and hires. Model connection settings remain. Localhost and trusted-LAN browsers use the same session/ownership controls; only one browser session may present at a time. See [session cleanup](runtime-settings.md#demo-session-cleanup).

### OpenShell evidence lab

The Security lab remains an operator diagnostic; decorative scene equipment no longer opens panels. Its concept walkthrough is always labeled illustrative; learner buttons do not execute requests or change policies. The host evidence tab reads a host-only capture report. Run `./bac dev openshell prove` to collect fixed public GET outcomes and matching OpenShell policy logs in a newly created dedicated sandbox, then clean up that sandbox. The report is timestamped and is not proof of current enforcement for the actual agents. See the [current host acceptance rehearsal](spark-operations.md#protected-demo-deployment-gate).

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

### Historical local macOS OpenShell record

The current release pins OpenShell **0.1.4** in `docker/runtime-lock.json`. Docker uses matching gateway, supervisor and sandbox-runtime images with schema-v2 gateway configuration. Native development uses the app-owned CLI under its data directory and verifies its version before protected operations; it no longer silently selects an older Homebrew CLI. `./bac dev openshell enable` installs the checksum-verified CLI and requires a matching selected gateway. It does not replace a shared host gateway. On Apple Silicon, configure a matching VM driver and explicitly select it with `compute_driver = "vm"`; use a separate gateway/state directory when an older shared gateway must remain available. The first sandbox can take longer while its images are prepared. New protected hires queue model-free sandbox preparation; a configured plugin alone is not evidence of a running sandbox.

The following is dated acceptance evidence, not a current macOS, Linux or Spark guarantee. Verified on the local preview host on 2026-09-20: native OpenShell VM reached Ready; the adapter read the effective sandbox policy and confirmed its loaded revision plus default network rules; an SSH command returned `BAC_SANDBOX_READY` with exit 0. An unapproved HTTPS request returned 403 (the sanitized log reader did not return a matching denial entry, so this is not recorded as a complete deny/allow/deny proof). Cached-image creation succeeded. Both temporary verification sandboxes were deleted. No model inference or participant workspace was used for this check.

If a protected request reports `Sandbox backend "openshell" is not registered`, the running OpenClaw plugin registry did not apply the saved configuration. Plugin discovery alone is insufficient evidence. OpenShell setup now requests `gateway restart --safe` after saving the integration so native active-work draining can run before plugin registration is rebuilt. A reachable model-list endpoint proves gateway connectivity, not successful sandbox provisioning; the protected run must still succeed. Reconnect the model in Settings if the app was restarted, because the old session-only provider proxy is no longer available.


## Resetting BaC crew chats between demos

Stage 3 → Reset asks for confirmation, stops active team work and waits for it to settle, then clears team chats, plan history, generated artifacts, attached documents (including extracted text), and custom Casey/standby model choices in the team's shared and specialist workspaces. Built-in roles return to their default models. API connection settings, personal-agent model choices, personal agents, and personal files/chats are preserved. All roles receive fresh conversation session keys, including after a restart. Reset works without a model connection. Native OpenClaw transcripts remain stored but are not reused as conversation context; this is not secure data erasure. Download attached documents and generated files before confirming Reset if you want to keep them.



Open Task reserves its selected hires while their assignments are active. Idle hires wait in seats sized to the current visiting group. Completed workers stay at their desks until a new confirmed plan replaces them. Other available hires may give short closing reactions; full text remains in the conversations/results and scene acknowledgements stay brief. Reopening a finished task does not start another model call.

## Explicit team requests with /goal

The demo targets desktop browsers and presentation mode. The collaboration prompt and design/build skills exclude mobile layouts, touch controls and mobile testing unless explicitly requested. No mobile-specific development or acceptance checks are required unless the user asks for them.

Start a message to Casey in Open Task with `/goal` and the result you want. **Hired only** is the default and needs at least one available hire. **Hired + Standby** prefers suitable hires and also permits Scout (research), Cody (programming), Ada (analysis), Iris (design) and Vera (review), including when there are no hires. Specific role presets and Coding/Web research skills are not admission requirements. Casey always coordinates.

The task captures its team mode and available hired profiles. Casey receives their actual tools and permitted-use limits and selects up to three distinct specialists. Named hires are requested participants only when the task fits their equipped skill. Casey must explain a substantial mismatch rather than force unrelated work; a name does not grant tools or permissions. In Hired only, every specialist needs a hired identity; invalid built-in assignments receive one bounded planning repair, then stop if still invalid. Old built-in-only plans remain readable for compatibility, but that mode is no longer offered in the UI.

Specialists execute in the chosen order and receive earlier contributions. Before each remaining assignment, Casey checks the saved work and may stop early only when requirements are satisfied, including named participants and requested independent review. Missing capabilities produce an unavailable response or useful partial work with explicit gaps. The three-specialist limit is not proof of completion; no fourth specialist is called automatically. Incomplete handoffs, malformed decisions and exhausted recovery retain available contributions as partial results.

Idle hires follow visitors into the room and sit on waiting benches; confirmed assignments send the selected hires to workbenches. Built-in backups enter only when allowed and selected. Unassigned hires do not become Scout or Cody merely because a previous plan used those role numbers. Animation never triggers, delays or substitutes for model execution. Only the active specialist performs work; unused assignments remain marked Not started.

Mission Control records Casey’s plan, each dispatched assignment and saved result, progress checks and the final response. Planned or skipped specialists are labeled uncalled. Cards preserve focus, selection and expanded results during polling. Saved decisions and handoffs remain inspectable after reload without replaying work or inventing timestamps. Results shows the current plan’s actual response and files. A saved response remains visible if a later interruption changes job status.

A plan uses one call for a zero-specialist answer and up to seven base calls for three specialists, including progress checks and final synthesis; bounded recovery and optional personal reactions can add calls. Stop prevents further calls after the current one returns. The team selector stays locked during work. Changing it afterward preserves history; reload or Reset Open Task defaults new tasks to Hired only. Reset clears the scenario’s history and exported results, restores built-in model defaults, and retains hires, their model choices and their own files.


After a successful `/goal` response is saved, other available hired agents who did not perform a specialist assignment may give short personal reactions based on their saved tone, role and interests, using the final answer and bounded specialist summaries. These are opinions, not independent verification. The answer and files are visible before reactions finish; reactions never rewrite the deliverable. Guests are captured from the same studio at submission, skipping busy/deleting agents. Their existing OpenShell protection is verified before each call; a failed guest can be retried without rerunning specialists. Casey’s conversation and each guest’s personal history retain the reactions. The existing audience-table animation is reused for newly submitted plans. Stop reactions, Open Task Reset and deletion fence in-flight calls and prevent subsequent replies; unsupported or failed plans do not trigger reactions.

Messages without the leading command remain direct requests to the selected agent. `/goal` delegates to the selected hired team, with built-in backups available only in Hired + Standby. Hired specialists retain their own identity, model, skills and protection; already-assigned hires do not receive duplicate closing reactions. Existing OpenShell grants remain in force. Personal workspaces are not copied wholesale. Name the input files in the current request (for example `sales (1).csv`), or explicitly refer to uploaded/attached documents in Casey's Open Task chat. Casey selects document IDs separately for each assignment, including originals needed by an independent reviewer. Only those selected files are copied into temporary specialist inboxes; unrelated agents and files are excluded. PDF/PPTX/XLSX inputs use extracted text and do not imply that images, formulas or layout were inspected. Input snapshots allow up to 10 documents totaling 30 MB, retaining the 10 MB per-file limit. Invalid IDs or image selections stop before any specialist starts. Attached chat images go to Casey and only specialists explicitly assigned `useImages:true`. Specialists also receive text handoffs and verified files produced earlier in that plan. Changed HTML pages and bounded text/code files are copied into a temporary inbox and removed after the receiving call. Existing files and paths merely mentioned by the model are not forwarded. The command does not authorize sending or publishing. Cody can write source and self-contained webpage prototypes with file tools, but cannot run arbitrary code or install dependencies. Vera must distinguish static inspection from tests actually executed. Ada interprets supplied tables without a statistics engine; Iris defines layouts and interaction criteria without claiming browser or usability tests. Reserve roles reuse account-owned identities and are registered only when invoked.

In `/goal`, the global request is background for specialists; each receives Casey’s specific assignment, expected result and role boundary. The research assignment produces a cited brief, the programming assignment builds the page or program, and independent review checks supplied work. These roles can belong to hires; Scout, Cody and Vera are the corresponding built-in backups. Only programming assignments receive the general webpage-creation instruction. Out-of-role HTML is not exported as a team preview or forwarded as an accepted implementation; a checkpoint cannot use it to skip a pending programming assignment. Casey can still finish early when the actual in-scope results satisfy the request. These delegation boundaries do not change direct chats.

Explicit requests such as “add review” are recorded as a required independent review. A review assignment is required after the producing roles, using a different agent and the relevant original inputs plus delivered work. It must use an available hire in Hired only; Vera is also an option in Hired + Standby. If all three slots were assigned without a reviewer, Casey gets one bounded opportunity to revise the team before dispatch. A required review cannot be skipped by a complete early-stop decision; if it cannot finish, the final result states that review is missing. A saved file alone does not fulfill this requirement.

General content repairs are not dispatched at intermediate checkpoints. A required file that was not saved can receive one handoff recovery; recognized output-limit failures can receive one shorter retry. These share the allowance with final targeted revision, so a plan does not loop through repairs.

Specialists receive temporary, readable copies of earlier deliverables. Their handoff manifest and published-file references use those local read paths; Casey retains the public download references for the final answer. Temporary copies are removed after the call. Producers and reviewers are instructed to preserve missing-data and uncertainty labels from the evidence, including forecast dates and units. This is guidance, not deterministic fact checking: a working page still needs content review.

The final citation check accepts arXiv abstract, PDF and HTML representations of the same paper ID and version. Different versions, paper IDs, hosts and queries remain distinct. The check validates observed source links, not whether every claim is supported by their content.

After the initial specialist work, Casey may authorize **one targeted revision** for a concrete unmet requirement supported by a saved contribution or review. The target must be an already-called specialist with a completed contribution; planned-but-uncalled roles, new specialists and Casey are rejected. This applies to every participating expertise, including analysis, writing and design. Optional polish is not a revision trigger. The initial outputs remain immutable in the trace, the revised contribution is saved separately, and Casey verifies it once without another specialist cycle. A failed repair retains the original files; further requested repairs or incomplete verification produce a partial result. New previews prefer the repaired page while the original is still available in its contribution. The same participant receives another paper handoff without another team entrance.

Casey's `/goal` control phases use native tool restrictions, not just prompt instructions: planning denies all tools; progress checks, final synthesis and revision verification allow only workspace file reads. The existing identity/configuration barrier confirms each mode before inference. Ordinary direct chat restores the regular tool configuration on its next preparation. No extra Captain identity or container is created. Control responses request JSON object formatting and concise decisions; validation still rejects invalid assignments and decisions. A malformed progress decision or runtime failure after a saved contribution returns that work as a partial result without dispatching further specialists or replaying the failed request.

For failed native model requests, the adapter checks only the matching session and invocation time in the native transcript. Known malformed tool-call errors receive a fixed, sanitized explanation; if recorded output reaches the configured token cap, the message notes possible truncation without asserting its cause. Raw model text, tool arguments, credentials and unrelated session errors are never included in this diagnosis. Missing evidence retains the generic runtime error. The existing output cap is unchanged.

If a task explicitly names a valid input ID such as `document-0` but omits its `inputs` array, only those exact IDs are resolved from the already user-scoped manifest. Explicit empty selections remain empty; unrelated inbox files are not copied. A complete checkpoint cannot skip a planned programmer while a requested webpage is absent, or a planned reviewer when the user explicitly requested independent review. Ordinary early completion without those unmet requirements remains supported.

A plan has a 600-second **dispatch budget** covering Captain and specialist work: once exhausted, it starts no new calls and returns the saved work as partial. This is not a hard interruption at 600 seconds. An already-running native request still follows its existing timeout (normally 360 seconds), and cancellation/reset still wait for in-flight work to settle. The optional personality reactions are not part of the repair cycle.

Plans are stored as crew conversations, so account isolation, crew reset and policy-update fences apply. Completed specialist contributions survive later failures. A failed plan is not silently rerun, and a stopped in-flight tool call may finish before cancellation settles.

Casey's Open Task composer starts with `/goal `. Type `/` to select it again (click, Enter or Tab). `/plan` and `/plans` remain supported aliases.
Escape dismisses the suggestion. Other composers have no slash-command suggestions.
Lounge direct and scheduled messages cannot start plans, even through the API; a rejected
submission retains the draft. Existing plans started from Lounge in older versions remain
readable. New plans use Casey's conversation as context; follow-up messages there can
refer to the saved team response. Context is bounded to 12 recent completed turns
and 8,000 characters, and follows chat resets. Other personal agents' conversations
and uploaded documents are not automatically shared.

Generated HTML pages appear as **Preview webpage** buttons in personal chats,
crew chats and `/goal` results. The viewer supports Desktop/Mobile widths and HTML
downloads. Each output is saved with its producing mission so later edits do not
replace older previews. Ask for self-contained HTML with inline styles, scripts
and images: previews run in an isolated frame without external network access.

### Time-limited research turns

Native agent turns normally have a 360-second timeout. Open Task research assignments, including hired researchers, have a separate 150-second budget across retries, plus bounded search/page access. A timeout alone does not identify the cause. Saved briefs and bounded successful tool excerpts may be preserved as incomplete evidence for subsequent stages; failed reads, hidden reasoning and other sessions are excluded. Casey must label missing evidence rather than inventing successful research. The plan also has the dispatch budget described above.

### Observed collaboration progress

While a `/goal` invocation is running, Casey's chat and the active specialist's chat show a bounded live list of observed native tool calls and their statuses. The footer reports time since the request, not time spent thinking. When no tool is currently observed running, it says it is waiting for the agent response; missing telemetry is labeled separately. Source content, hidden reasoning, tool arguments, host directories and URL queries are excluded. State polling reads only the authorized job's exact native session and invocation time, never dispatches work, and stops reading after completion or cancellation.

### Shared connections and scenario models

Settings → Model configures Local and External Endpoint once, then **Models** provides separate **Open Task** connection selectors. Hired agents use individual models from Hiring/Edit agent or their idle Open Task model badge; new hires default to connected Local, otherwise the configured External Endpoint model (Data analyst prefers NVIDIA Ultra when available). For built-in teams and earlier agents using the shared default, an unavailable preferred source can fall back to the other ready source; active calls are not replayed. Neither connection being ready blocks model work without blocking Settings.

For Casey and backups on NVIDIA, select **Hired + Standby** and open **Standby specialists** to change model choices; return to Hired only before starting if needed. Defaults are Nemotron 3 Ultra for Casey and Ada, Nemotron 3.5 Super VL for Cody and Iris, and Nemotron 3.5 Lightning for Scout and Vera. Local and other external providers use the selected connection model for Casey and backups; hired agents keep their individual choices. See [model selection](plan-team-models.md).

A validated `api.cfg` key is optional and host-persisted; manually entered keys are session-only. Both can serve the shared NVIDIA connection. See [credential storage](session-credentials.md).

### Compact demo scope and output-limit recovery

The demo defaults to 32K context per agent session and at most 16K output per response. Smaller configured contexts reduce the output cap. These are application settings, not a fixed OpenClaw/OpenShell ceiling. See [context and output budgets](runtime-settings.md#context-and-output-budgets).

By default, `/goal` targets a small working desktop demo with the minimum necessary specialists. Design specs target 60 lines / 600 words; handoff summaries target 120 words. Explicit requirements take precedence. Forwarded history is capped at 8,000 characters; contribution summaries are bounded and omit tool activity, while saved files remain available for inspection.

An explicit model output-limit error, a tool call truncated at the output limit, or a file-write command returned as plain text allows one fresh-session retry per plan, for either a specialist or a Captain decision, provided at least 30 seconds remain in the existing time budget. The retry inspects saved work and finishes essentials without repeating successful actions. The runtime checks native transcripts for unexecuted text-form write commands even when a later summary claims success. It never executes the printed command itself. Code recovery requests a complete minimal page first (target under 6,000 characters), followed by small native edits. Other errors do not trigger this retry. A second output-limit failure preserves partial work and stops; it is never labelled complete automatically.

Research quality for compact demos: Scout targets two relevant questions, prefers topic-specific source indexes over generic homepages, and aims to stop after one or two useful articles. The prompt budget is at most five fetch attempts including failures, reserving two for a fallback source; the bundled research guard enforces the fetch quota for Scout’s `/goal` research. Reputable secondary reporting is allowed after publisher failures unless the user requests official-only sources. Explicit policy denials must not be bypassed. Briefs preserve dates, reporting periods and exact source links; unrelated content is excluded. Cody omits unsupported metric cards rather than filling the page with missing-data messages. Without relevant evidence, the output must be labeled a prototype, not completed research. The bundled Scout configuration provides keyless Parallel Search.

### Scout search-first demo
Runtime setup installs pinned `@openclaw/parallel-plugin@2026.7.1` and selects keyless `parallel-free` for standard research agents. Scout starts with one focused search, up to three results and 2–3 relevant findings in a brief under 300 words. Scout saves that brief with native write once relevant evidence is available. If the first search misses the requested subject or date range, one reformulated search is allowed within the existing two-search ceiling. It is not used to polish sufficient evidence. Fewer findings are acceptable; if neither search finds relevant current evidence, Scout saves an honest failure note. Adjacent technology alone does not satisfy a requested research topic. Queries include the current year or requested period, and results are checked for publication dates and reporting periods. Search excerpts are cited as excerpts; full-page reads are not implied. Parallel remains the default search provider. If search is unavailable, supported direct reads of known public URLs may continue within the same research budget. This does not switch search providers or bypass OpenShell; a policy denial cannot be routed around. Scope is guided by prompts and bounded by the research guard: at most two searches with three bounded excerpts each, or five bounded page reads; after search, further page reads are blocked. The search request timeout is 20 seconds. A separate 150-second Scout budget spans retries and preserves saved briefs or completed source excerpts if finalization times out. Protected personal agents retain their existing tool and network restrictions. No search API key is required. Existing Docker installs need the rebuilt dependency image (`./bac start`).

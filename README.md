# NVIDIA Build-a-Claw

Hire personal agents, try their skills, and collaborate with Riley or Casey and their specialist agents in the **Multi-Agent demo**.

This guide describes **`preview/stage3-scenarios`** on GitLab. The frozen Zurich branch and older releases have different controls.

[Presenter runbook](docs/demo-runbook.md) · [Demo workflow](DEMO_WORKFLOW.md) · [Example scenarios](README_POSSIBLESCENARIOS.md)

## Start on a new PC

**Requires:** Ubuntu 24.04, rootful Docker Engine 28+, Docker Compose 2.24+, internet access, and permission to run `docker info`. Intel/AMD and ARM64 (DGX Spark) are supported.

Clone the preview with an account that has access to the GitLab repository:

```bash
git clone --branch preview/stage3-scenarios https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2.git
cd bacdemo-tier2
./bac start
```

Startup optionally loads the NVIDIA inference API key from `api.cfg`. If the file is empty, invalid or the API cannot be reached, Studio still starts so you can configure Local or External Endpoint in Settings. A failed validation prints a warning and does not overwrite a saved key. Use `--keep-data` when retaining runtime data and settings. Valid keys are checked with a small inference request before being saved.

Open **http://localhost:8080** on the host, or **http://SPARK_IP:8080** from another computer on the same trusted network. Both provide the same Settings and demo controls. The validated key is available automatically under **Settings → Model → External Endpoint**. Enable **Local** and/or **External Endpoint** once. Hired agents choose their model in Hiring or Edit agent and default to Local when connected. Under **Models**, choose the connections for **Event Brief** and **Open Task** independently. Automatic prefers External for built-in teams.

The first start builds the runtime image for your PC and downloads the pinned OpenShell images. OpenClaw and OpenShell are included; no host Python or Node installation is needed. BaC does not install model weights. A local model server can serve any stage and runs separately.

## Prepare a local model (optional)

`./bac vllm` starts or reuses **Qwen by default**, then waits for the exact model
ID and a small inference request to succeed. This command runs independently of
Docker, Studio, and the Stage 3 API key. Ordinary `./bac start` never starts or
waits for a local model, even if model configuration exists or model files are
missing. `./bac stop` stops the BaC services and their OpenShell sandboxes, but leaves the host model server running and preserves saved data. Use `./bac stop --all` to also stop the local model launched by this installation, remove the Compose stack, and delete its application data volumes. Externally managed model servers and model weights are preserved.

```bash
./bac vllm                # Prepare Qwen, default wait: 600 seconds
./bac vllm --model qwen   # Same, explicit selection
./bac vllm --model gemma  # Only if a Gemma installation is configured
./bac vllm --restart      # Stop the configured server, restart and wait
./bac vllm --status       # Inspect the local model
./bac vllm --logs         # Show the managed model service journal
./bac vllm --stop         # Stop only a model this helper launched
./bac start               # Start Studio separately
```

When Studio is inside a `build-a-claw` installation, `./bac vllm` automatically
reads the selected model's launch settings from the immediate parent's `config.json` if
`local-model.json` is absent. It resolves the weight path relative to that
installation and reuses its executable and environment settings. This does not
invoke the parent demo or enable local models during ordinary Studio startup. The parent directory must be named `build-a-claw`. For example, a parent model path of `models/qwen` corresponds to `../models/qwen` from the Studio checkout; the helper resolves it to an absolute path.

For a standalone installation or to override those settings, put a
machine-specific `local-model.json` beside `bac`. It contains a `models`
object and optional `wait_seconds` (1–3600). Each model specifies its `model_id`,
`model_path`, `base_url`, `context_window`, exact `argv` list, and `env` object.
Qwen remains the command default regardless of `default_model` or `enabled` in
this file. `model_path` must be an **absolute path**, not a literal `../models/qwen`.
Use the installed executable and actual weight path in `argv` too. These paths
can point anywhere on the host PC; a `build-a-claw` parent is not required when
this file is present. No model files or runtime packages are downloaded.
If paths are missing, `vllm` explains the problem; `start` is unaffected.

After starting Studio, connect Stages 1 and 2 in **Settings → Model → Local**
using the model ID and endpoint printed by `vllm`. Stage 3 retains its separate
NVIDIA inference API default, with optional local routing per scenario. Model preparation does not change Studio's
saved provider settings.

The helper requires host Python 3.9+ and a systemd user session to launch a new
background model service. It displays loading progress every 15 seconds, fails
early if the service exits, and times out with a useful error. An unexpected
listener is rejected. Normal `./bac vllm` startup reuses a healthy external server without stopping it.
A newly launched model is stopped if readiness fails. Logs remain in the user
journal; model files are preserved. Changing a managed model's launch settings
requires `./bac vllm --stop` first.

If the service launch record is missing or its invocation ID has changed,
`./bac vllm` can still reuse the endpoint after checking the configured model,
context limit and successful inference. It does not adopt or stop that service.
If the endpoint is not ready, inspect `./bac vllm --status` and `./bac vllm --logs`
and retry when loading finishes. `--restart` refuses an active service with an
unmatched launch record before signalling any processes.

Machine-specific configuration and service identity under `.local-model/` are
ignored by Git. Do not put API credentials in this unauthenticated local model
configuration. BaC removal does not delete the external weights or vLLM runtime;
stop a helper-owned model explicitly before removing Studio.

`./bac vllm --restart` is the demo recovery command. It checks the replacement
installation first, stops the helper-owned service (or the exact configured
external vLLM command and its captured workers), restarts Qwen, and waits for
successful inference. It sends TERM first and uses KILL if workers do not exit.
It never uses a broad process-name kill. If an occupied port cannot be tied to
the configured command, restart fails without killing that listener. Explicit
restart may interrupt other applications using this same model server.

Missing-installation errors list the required executable and weights paths, explain
how to update local-model.json, and remind you that ./bac start still works
independently. Failed new launches print the final startup-log lines automatically.

## API key and model settings

### Stage 3: Multi-Agent demo

`api.cfg` sits beside `bac` and contains only your NVIDIA inference API key on one line. Edit this file directly; startup never asks you to type a key in the terminal. To change the key, edit `api.cfg`, then run:

```bash
./bac start
```

- The validated key is saved on this computer with owner-only file permissions. Refreshing the browser does not require re-entry.
- Missing or rejected keys do not block startup. No unverified key is saved.
- API validation failures preserve any previously saved connection. Settings checks the currently configured connection before marking it ready.
- The repository tracks an **empty `api.cfg` placeholder**. Startup installs a local Git clean filter that stages an empty file while preserving your working key. Release packages also contain an empty file; the Docker image excludes it.

If you want to edit `api.cfg` and use Git **before your first start**, install the filter first:

```bash
bash scripts/setup-key-filter.sh
```

In Stage 3, **Models & connection** opens the shared Model settings. Preferences apply to new work; active requests are never automatically replayed. For Open Task on NVIDIA, expand **Standby specialists** and click the model beside each agent to search and save its choice. Event Brief uses the selected connection model for its entire team. Choices are locked while the team is working. Other external providers use the model selected for the shared endpoint. Hiring/Lounge, Event Brief and Open Task have separate rows in the same settings panel. Save both scenario choices together without switching floors.

### Stages 1 and 2: Hiring and Agent lounge

Open **Settings → Model → Local → Configure**, search the model list, and connect a model with tool calling:

| Server | Endpoint |
| --- | --- |
| Ollama on this PC | `http://127.0.0.1:11434/v1` |
| vLLM on this PC | `http://127.0.0.1:8000/v1` (use its actual port) |
| Other OpenAI-compatible server | Its API URL ending in `/v1` |

Keyless local servers need no API key. Provider keys entered in these settings are kept in memory for the current tab and must be re-entered after refresh, tab closure, or app restart. The enabled connections supply individual hired-agent models and the separate **Event Brief** and **Open Task** selections. A host-saved NVIDIA key from `api.cfg` remains available after refresh; only keys entered in the browser need re-entry.

## Try the demo

1. **Hiring:** choose a character, role, tone, and skills.
2. **Agent lounge:** chat with a hired agent, inspect files, or approve OpenShell access.
3. **Multi-Agent demo:** enter the **Event Brief** or **Open Task** floor directly from the studio overview or Studio Map. Both spaces branch directly off the Lounge concourse as equal choices, with their own signs and accent colors. Entering Stage 3 or choosing **Scenarios** shows the spaces together. Switching spaces never clears either workspace.

**Event Brief** restores the fixed Riley, Dylan, Alex and Morgan crew. The app prepares this crew in the background once a model connection is available, without running inference. Open **Plan an event**, enter event details, and launch when preparation is ready. Reopening the form reuses the prepared team. While the app is open, it checks readiness in the background and prepares again after model changes, scenario resets or server restarts, without requiring a visit to Stage 3. A failed preparation waits for a manual retry. The team produces researched demo ideas, an operations timetable and an event webpage. Dylan retains his OpenShell protection.

**Open Task**: message Casey with `/goal` and a concrete task, optionally attaching documents. **Include hired agents** starts off. With it off, the built-in specialists do the work and your hired agents give their usual short reactions afterward. Turn it on to prefer suitable agents you hired for specialist assignments, with built-in specialists available as backup. The toggle controls who does the work, not whether personal reactions happen. Event Brief keeps its fixed team. Each scenario retains its own history, documents and results. Choosing another scenario does not cancel active work.

This experimental `preview/visitor-agent-teams` branch adapts Paul Roeseler's hired-agent collaboration from `proeseler/stage3-demo` to the current dispatcher, preserving its verified handoffs, bounded recovery and cancellation.

To choose who does the work, turn on **Include hired agents**, then name them and their assignment:

```text
/goal Let Pixel handle the coding instead of Cody. Build a small desktop counter page.
```

Natural phrasing is supported, including mixed teams such as “Let Scout find three places in Barcelona, then have Pixel turn the findings into a page.” Casey selects each agent and its work explicitly. If that selection is incomplete, Casey gets one chance to clarify it before any specialist starts; the app does not guess roles from nearby keywords.

Pixel actually performs the coding, even if its saved role is weather advice. Its identity, voice, skills, workspace and OpenShell policy stay the same; the assignment does not grant extra tools. Named agents are not replaced because they lack expertise. When upstream output is incomplete, named agents still attempt their assignments with the available evidence and the result stays partial. Busy or unavailable agents are reported; cancellation, connection failures and the overall time budget can still stop the task. The existing maximum of three specialists applies, with a different agent required for independent review.

The choice is captured when you submit a task and cannot change while it runs. Room changes keep your choice; reloading the page or resetting Open Task starts with it off for new tasks. Naming a hired agent while it is off asks you to enable it before any work starts.

Hired agents use their selected **Hiring** model for both specialist assignments and closing reactions. Casey and built-in backups use **Open Task** settings, including its existing per-agent NVIDIA model choices. Connect both when combining the two. Agents invited for assignments or reactions are reserved so chat, Heartbeat and edits do not overlap the team task. Busy or unavailable guests are skipped under the existing reaction rules. With participation on, hired specialists do not receive a duplicate closing-reaction call. Follow-up messages to a hired specialist open its existing Lounge conversation. Scenario reset clears the shared team history and exported results, while preserving the hired agent's own files and identity.

`/plan` and `/plans` remain supported aliases for `/goal`. Only Open Task's Casey chat supports these team commands. Lounge agents without Tech Radar accept direct messages; Event Brief uses **Plan an event**. Casey's Open Task chat starts with `/goal ` and restores it after a successful send. Delete the prefix to send a direct message. Specialists accept direct messages only, without `/goal` hints or suggestions; send team tasks to Casey. Their inputs start empty and clear after sending; existing drafts stay intact when switching characters.

The room starts with Casey. Once Casey assigns a team, selected hired agents walk from the Lounge to Open Task with their existing appearance. Unselected agents stay in the Lounge. Hired participants return when the task finishes, stops, or resets; their contributions remain available in the results. Travel is visual only and never delays model execution. Switching rooms does not restart the walk; reduced motion places agents directly. Built-in backups keep their normal entrance. Specialists execute in assignment order. The backup pool is Scout (Web Researcher), Ada (Data analyst), Iris (UX designer), Cody (Programmer), and Vera (Reviewer). Dylan, Alex and Morgan appear only in Event Brief. Coding assignments, including those given to hired agents, prioritize a compact, usable desktop demo: no mobile layouts or touch controls, no optional polish loops, and no extra design pass unless needed. Save the core implementation in one pass and return once required work is delivered. Explicitly requested independent review is still required. Casey reserves a repair for an observed defect, not a repeated save/read confirmation.

**Mission Control** shows assignments, expected results, contributions, and Casey’s decisions in execution order. **Results** shows the current plan’s response and saved files, with previews for generated HTML pages. While a plan is running, Casey’s composer and the working specialist’s composer are disabled. Stop immediately shows a pending state and prevents duplicate clicks while cancellation is being sent; an in-flight runtime call may still need to settle. Partial and failed work remains visible rather than being presented as complete.

Example:

```text
/goal Build a self-contained desktop HTML page comparing the figures in the
attached CSV. Use only the supplied data and include a clear comparison chart.
```

**Heartbeat:** equip an agent with the **Tech Radar skill** to check for an unread technical article every 20 seconds and share a summary with a source link. The first check waits at least 10 seconds; runtime preparation or other model work may delay it further. Pause or resume in the agent panel. Any agent with this skill is automatic-only, including agents with additional skills: manual chat and attachments are disabled, and group chat requests exclude it. Remove the skill to restore manual chat; pausing Heartbeat does not enable it. [Heartbeat and Telegram details](docs/heartbeat.md).

**Settings → Location** sets the default city (Zurich). **Settings → Reset** offers **Remove agents** for Stages 1 & 2, separate **Reset scenario** buttons for Event Brief and Open Task, available from any room, and **Reset all** for both. Reset all stops and clears both Stage 3 scenarios before removing hired agents; model and connection settings are preserved. The **Reset button in the team utility row** stops work and clears data only in the selected scenario after confirmation; the other scenario, personal agents and model settings are preserved. **Settings → Telegram** optionally relays new Heartbeat summaries while the connected tab stays open.

### Review and bounded rework

Casey can answer directly or select up to three specialists. Simple tasks need no fixed team size. To require review, say so explicitly:

```text
/goal Analyze the attached earnings table. Add an independent review of the
calculations, units, reporting periods, and conclusions before the final answer.
```

- Requested review is included in the initial team, normally Ada then Vera for supplied-data analysis. Casey cannot mark the request complete by skipping that review. A planned code review also runs before completion.
- Between stages, Casey checks whether the next assignment can proceed. General content revisions are not dispatched at every intermediate checkpoint.
- A missing required file, recognized output-limit failure or context overflow can use one bounded recovery attempt. At final synthesis, Casey can instead request one targeted repair from an already participating specialist for a concrete unmet requirement. These paths share the repair allowance; they do not create repeated retry loops.
- No new specialist joins during a repair, and no automatic second specialist review follows it. Casey checks the revised contribution and states what remains unverified. If review or required work cannot finish, the result is partial or unavailable.
- A plan has a 600-second dispatch budget. This is not a guaranteed wall-clock finish time: cancellation and timeouts may need to wait for an in-flight runtime call. Saved work is retained.

Saved-file checks prove delivery, not correctness. Specialist reviews are static inspections unless actual execution evidence is available. Generated pages run in a restricted preview, so browser storage must be optional. Local JavaScript form handlers and validation work; network requests, actual form submissions and parent-page access stay blocked. Offline demos must not promise emails, bookings or remote saves.

Static review uses bounded source excerpts: at most eight reads, 120 lines per read, and 18,000 retained source characters per plan. Duplicate reads are blocked. Vera must disclose unread sections or unverified requirements; reaching the limit does not certify the whole artifact. This reduces repeated-read context overflow without limiting Cody’s saved code length.

### Research limits

Scout uses keyless Parallel Search: one focused search and 2–3 useful findings by default, then saves a short cited brief. Fewer findings are acceptable; stale or irrelevant results are reported honestly. No separate search API key is needed.

The bundled research guard enforces at most two searches (three bounded excerpts each), or five bounded page reads, per research job. After a search, save the available excerpts instead of opening more pages. Hired specialists inherit these Open Task budgets, bounded file responses and review limits. Their protected command calls have a five-call budget and a 20-second timeout per call. Lounge research also receives concise research instructions and bounded fetched excerpts, with runtime context compaction. Neither changes OpenShell permissions or guarantees every request fits the model context.

Lounge research answers ordinary questions directly; it saves a brief when requested or assigned as a team handoff. Its generated research instructions use the agent's actual transport: native web tools for standard agents, approved sandbox requests for OpenShell agents. Personal tone and reply styles remain in `SOUL.md`; Event Brief and Open Task use their own role and delivery contracts.

Small saved evidence briefs and bounded excerpts from observed tool results are passed directly to Casey for synthesis. If the final reply cites a public URL absent from those results and their returned links, it is withheld as partial rather than labeled complete. This citation check does not verify every factual claim or establish that sources are current.

Research assignments have a 150-second budget across retries, whether Scout or a hired agent performs them. At the deadline, saved work and completed search/page excerpts are preserved for the team; missing evidence is reported honestly.

## Everyday commands

| Action | Command |
| --- | --- |
| Install / start fresh, clearing agents, work, context and usage history | `./bac start` |
| Start or apply app changes while preserving runtime data | `./bac start --keep-data` |
| Check status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| Stop services and local model, then delete Compose containers and data volumes | `./bac stop --all` |
| **Delete BaC and its data** | **`./bac remove`** |

To update, finish active work, then run in the repository folder:

```bash
git pull --ff-only
./bac start --keep-data
```

Use normal Git commands to update your checkout. Resolve local changes or divergent history before pulling. With the Git key filter configured, your local key stays in `api.cfg`.

By default, `start` recreates services and clears agents, conversations, results, context, recorded usage and runtime settings. Project files, `api.cfg`, shared host files, images and the separately managed local model are preserved. Use `./bac start --keep-data` when applying app changes without clearing runtime data. There is no `./bac restart` or `./bac update` command. Use `git pull --ff-only` followed by `./bac start --keep-data` for a non-destructive app update; `./bac vllm --restart` restarts only the local model server.

Only one browser session can use the demo at a time; other browsers show an **already open** message without preparing duplicate agents. Tabs at the same address in the same browser share the existing agents. Close those tabs before opening a different browser; disconnected browsers release access after 90 seconds, once running work finishes.

Abandoned browser sessions and their agents are [automatically removed after 60 minutes](docs/runtime-settings.md#demo-session-cleanup), once active work finishes. Open tabs renew their session automatically. A preserving restart gives saved browsers 60 minutes to reconnect.

`remove` asks you to type `remove` once. It deletes BaC containers, data, shared files, backups, recorded project images, local settings, and `api.cfg`. A source checkout keeps its code; an installed release folder is removed. Other projects and your model server remain.

[Setup & troubleshooting](docs/docker-setup.md) · [Model settings](docs/runtime-settings.md) · [Development & tests](docs/development.md)

### Scenario preview provenance

This preview starts from the frozen Zurich snapshot (`feba7df`). The viewport improvements, room information guides and side-by-side agent definition viewer adapt Benjamin Bayart’s contributions (`ee717f3`, `8993a20`, `09b4794`, `3c54aba`); the initial Stage 3 picker took inspiration from his scenario cards; scenarios now appear as separate 3D floors. The fixed Event Brief workflow is restored from `archive/bac-planning` (`94198b6`). Default startup clears runtime data; `./bac start --keep-data` retains agents and previous work. There is no `./bac restart` command. Existing Zurich team ownership migrates to Plan without changing native identities; Event Brief creates a separate team when first used.

Scenario presentation lives in `src/stage-scenarios.json`, shared by the scene, navigation and accessible fallback. Floors branch in pairs from a common concourse and use automatic overview framing, so three or four scenarios fit without hard-coded camera coordinates. Selecting a space moves the camera directly to it with a gentle zoom out and back in; it does not stop at intermediate rooms. New selections replace an in-progress move, and reduced-motion settings skip the animation. New scenarios also require an explicit backend workflow and ownership identifier; adding a visual entry alone does not enable a new workflow.

### Files and Event Brief recovery

Use **Files** in the team utility row to browse the selected specialist’s uploads and results. In the Lounge, use **Files** beside **Instructions** for the selected hired agent. The button is hidden when that agent has no files, and the file dialog has no agent selector. Open a file to preview or download it. **Instructions** shows AGENTS.md, IDENTITY.md and SOUL.md side by side, with Copy and no Download. Click the agent name or portrait for all saved definitions, including skills and memory. These are browser-based views of the server workspace, so they work when the demo runs on another computer. They do not open the presenter’s OS file manager.

Empty scenarios have Reset disabled. Manually requested event preparation, conversations, uploaded documents and results count as saved work. Completed background preparation alone does not enable Reset. Reset clears only the selected scenario; the built-in Event Brief template remains available for the next run.

The default context budget is 32,768 tokens per agent session; the output cap is 16,384 tokens per response. These are demo settings, not universal model or OpenShell limits. Connections configured with less than 32,768 context tokens use at most half of their context for output, leaving the rest for input and tools. If a model hits its output limit, that role gets at most one concise retry in a fresh context, preserving saved files and completed tool results. Existing deliverable checks still apply. Context overflow can use the same single recovery allowance: Dylan validates saved Event Brief themes first, while Open Task reuses saved files and evidence with focused reads instead of rebuilding completed work. Failed model requests are not automatically replayed for other provider errors. Runtime preparation and read-only readiness checks have separate bounded recovery. To resume, run `./bac vllm` if needed, then `./bac start --keep-data` when preserving runtime data. See [context and output budgets](docs/runtime-settings.md#context-and-output-budgets).

### Shared model connections

In **Settings → Model**, Local and External Endpoint are independent checkboxes. Configure each connection, search the automatically loaded model list, and connect. External Endpoint supports NVIDIA Inference, OpenAI and Anthropic. An `api.cfg` key can supply NVIDIA automatically; newly entered keys stay in memory for the browser credential session.

New hired agents default to **Local** when connected. Expand **Model** below **OpenShell protection** to search the available models. Disconnected options are disabled. Each agent keeps its choice in the Lounge, Heartbeat and Open Task. Edit agent lets you change it while that agent is idle. An unavailable selected model blocks that agent rather than silently switching to another connection. If Local is unavailable, select a connected external model or connect Local before hiring. Existing agents can still be edited while their saved model is offline. Existing agents without a model choice retain the previous Lounge setting; editing other fields does not switch them to Local.

Stage-level defaults prefer Local for legacy Hiring/Lounge agents and External Endpoint for Stage 3; saved manual preferences are preserved. The panel highlights the actual ready connection rather than showing an ambiguous Auto option. For those stage-level preferences, if the preferred connection is disabled or unavailable, new work uses the other ready connection. Explicit per-agent choices do not use this fallback. If neither is ready, requests are blocked with **Model not connected**. Connection checks verify model availability, not model quality or task completion. Existing work is not retried automatically.

Use local/private endpoints reachable from the OpenClaw host. Local mode does not launch vLLM automatically. Scenario resets preserve connection settings. The launcher treats `api.cfg` as optional. When Open Task uses Local, a warning explains that it may be slower or produce less reliable results for complex requests. With neither connection ready, tasks remain blocked. Event Brief does not show this Open Task warning.

### Scenario teams and models

Event Brief uses Riley (event coordinator), Dylan, Alex and Morgan, with event-specific identity and role instructions. Open Task keeps Casey as its team captain. Each scenario has separate native agents, workspaces, conversations and memory, including before any model request. Existing generated Event Brief definitions are upgraded; custom definitions and saved work are preserved.

All Event Brief agents use the model selected on their active connection in **Settings > Model**, whether Local or External Endpoint. Old per-agent choices do not override that connection. Open Task retains per-agent NVIDIA model choices in its specialist roster; Local and other external providers use the selected connection model.


## FAQ

### several instances, not the same version on one computer
if you end up installing (throught *git clone* or else) different version of the demo, you could encounter some issues of starting one version or the other. Issue may come from one earlier version was using and creating some environment without cleaning them after being stop.

1. **Docker Volume(s) seen issue**

   As part of the deployment, some volumes are created. When stopping the solution, those volumes (and backup) may not been cleaned nicely after stopping.

   In case, and to be sure.

   ```bash
   ./bac stop --all
   ./bac start
   ```

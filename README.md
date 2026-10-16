# NVIDIA Build-a-Claw

Hire personal agents, try their skills, and bring a goal to Casey and the selected team in **Open Task**.

This guide describes **`preview/visitor-agent-teams`** on GitLab. The frozen Zurich branch and older releases have different controls.

[Presenter runbook](docs/demo-runbook.md) · [Demo workflow](DEMO_WORKFLOW.md) · [Example scenarios](README_POSSIBLESCENARIOS.md)

## Start on a new PC

**Requires:** Ubuntu 24.04, rootful Docker Engine 28+, Docker Compose 2.24+, internet access, and permission to run `docker info`. Intel/AMD and ARM64 (DGX Spark) are supported.

Clone the preview with an account that has access to the GitLab repository:

```bash
git clone --branch preview/visitor-agent-teams https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2.git
cd bacdemo-tier2
./bac start
```

Startup optionally loads the NVIDIA inference API key from `api.cfg`. If the file is empty, invalid or the API cannot be reached, Studio still starts so you can configure Local or External Endpoint in Settings. A failed validation prints a warning and does not overwrite a saved key. Use `--keep-data` when retaining runtime data and settings. Valid keys are checked with a small inference request before being saved.

Open **http://localhost:8080** on the host, or **http://SPARK_IP:8080** from another computer on the same trusted network. Both provide the same Settings and demo controls. The validated key is available automatically under **Settings → Model → External Endpoint**. Enable **Local** and/or **External Endpoint** once. Hired agents default to connected Local, otherwise the configured External Endpoint model. Change the model in Hiring, Edit agent, or by clicking a hired agent’s model badge in Open Task while idle. Model changes are locked while the agent is working or reserved for a task. Under **Models**, choose the **Open Task** connection. The selector shows the connection currently used.

The first start builds the runtime image for your PC and downloads the pinned OpenShell images. OpenClaw and OpenShell are included; no host Python or Node installation is needed. BaC does not install model weights. A local model server can serve any stage and runs separately.

## Demo stages and presenter aids

1. **Hiring:** define a role and voice, equip the skills needed for its work, and review the current model. Hiring also works without a custom skill for ordinary conversation. Click the **i** beside a skill to read its shipped instructions before hiring. **How does an agent work?** shows the model, instructions, skills, memory, tools and runtime together.
2. **Agent Lounge:** try one agent, inspect its files, and demonstrate OpenShell access decisions. Tech Radar also shows **Heartbeat**: scheduled checks, observed activity and honest waiting states.
3. **Open Task:** Casey coordinates the selected team. **Hired only** is the default; **Hired + Standby** adds suitable backup specialists. The **Team** control sits above the message box. **Example goals** chips below Casey’s introduction offer Travel, Drone research, Store email review, Ping-pong and Event page. Examples fill an editable draft, never auto-send or change team mode. The store example attaches BB’s fictional email. The event example uses this same room and team; it does not restore Event Brief.

In the Lounge, use normal chat with an OpenShell-protected agent. For example, ask it to read `https://example.com`. **OpenShell Policy** shows observed network decisions and saved workspace results. Approve a website there and resend the request to see what changes. See [the presenter walkthrough](docs/demo-runbook.md#openshell-in-the-lounge).

Casey assigns substantial work only when the agent’s **explicitly equipped skill** covers it and its actual tools permit it. Naming an agent does not expand its scope. A Weather buddy with Live weather only should decline game development; adding Coding makes a small game an appropriate assignment. Ordinary conversation and small adjacent requests remain possible. Skill suitability is model-guided, not a security boundary; OpenShell and tool permissions enforce access separately. Casey’s chat and Mission Control show saved **Why this agent** and **Not assigned** explanations; scene speech bubbles stay concise.

### Dependencies, hardware and model evidence

| Area | What is needed / what has been checked |
| --- | --- |
| Packaged demo | Docker and Compose as listed above. The image supplies Python 3, Node.js, OpenClaw, OpenShell and document utilities. The precise pinned versions are in `docker/runtime-lock.json` and Settings → Reset → Issue report. No host Python/Node is needed for `./bac start`. |
| Browser | A current desktop browser with WebGL. Three.js r180 is bundled; no renderer download is needed at runtime. Playwright is for development tests only. |
| API inference | An Ubuntu x86-64 or ARM64 host for the container runtime. Inference runs at the endpoint; a host inference GPU is not needed. No measured minimum host RAM/CPU benchmark is claimed. |
| Local inference | A separately prepared, tool-calling model server and sufficient GPU/unified memory for that exact model, quantization and context. DGX Spark ARM64 is a deployment target. `./bac vllm` reuses configured weights; it does not download them. There is no universal GPU/VRAM minimum for all models. |
| Recorded real API tests | The October 14 visitor tests used `azure/openai/gpt-5.6-terra` for hires through NVIDIA Inference. Store email review and selected research/build journeys produced inspected artifacts. Travel and drone examples also returned honest partial results. Generated ping-pong physics still had defects in that run. These are scenario observations, not blanket model certification. |
| Local / other models | Qwen is the configured local launcher default; other listed models are selectable endpoints, not proof of a tested scenario. The same multi-agent examples have not been benchmarked on local Qwen in the cited run. Rehearse on the target host before presenting. |

For multi-agent quality and responsiveness, a rehearsed External Endpoint is recommended. Local operation remains available. Source records and exact per-scenario limitations are described in [example scenarios](README_POSSIBLESCENARIOS.md), [visitor testing](docs/visitor-regression.md), and the [setup guide](docs/docker-setup.md).

### Version and support information

**Settings → Reset → Issue report** shows the app version, source branch/commit, local modifications and pinned runtime versions. **Copy diagnostics** includes build identity, current connection/workload state and recent safe diagnostic events. **Download** exports a larger report. Neither includes credentials, prompts, responses or file contents. `/health` and the startup log identify the running server build as well.

`VERSION` starts at **0.2.001**. Each subsequent newly authorized GitLab publication advances the final number: **0.2.002**, **0.2.003**, and so on. Keep at least three digits in that number. Prepare the next version with `python3 -B scripts/build_info.py bump patch`, commit it with the changes, then rebuild so the UI and logs identify the delivered commit. The initial 0.2.001 is already prepared; do not bump it again before its first publication. Local builds, restarts, tests, and retries of the same push do not change the version. Change the major/minor series deliberately when agreed. This is an app version label, not strict SemVer (the final number has leading zeros). Publication remains an explicit maintainer action.

### Diagnose an issue

Use `./bac status` for service state and `./bac logs` for a short recent console log. After reproducing a problem, use **Settings → Reset → Issue report → Copy diagnostics**, then paste it with the steps you took and the approximate time. Use **Download** if more history is needed. Copy includes up to 80 matching server events; Download includes up to 400, with additional size limits. Both include browser errors from the current tab and the current session's recent job states. Other participants' job records are excluded.

Detailed structured records live at `$BAC_DATA_DIR/studio/logs/diagnostics.jsonl` (inside the packaged container: `/var/lib/bac/studio/logs/diagnostics.jsonl`). Each record has a UTC timestamp, version, source commit, build fingerprint and server run ID. Request IDs connect API errors to queued jobs; job IDs connect progress, model usage, failure categories and exception source locations. Confirmed OpenShell denials are distinct from error text merely reporting an OpenShell failure. See [diagnostics details](docs/diagnostics.md) for retention and limits.

## Prepare a local model (optional)

`./bac vllm` starts or reuses **Qwen by default**, then waits for the exact model
ID and a small inference request to succeed. This command runs independently of
Docker, Studio, and the Stage 3 API key. Ordinary `./bac start` never starts or
waits for a local model, even if model configuration exists or model files are
missing. `./bac stop` stops the BaC services and their OpenShell sandboxes, but leaves the host model server running and preserves saved data. Use `./bac stop --all` to also stop the local model launched by this installation, remove the Compose stack, and reset its application data and OpenShell policies. Externally managed model servers and model weights are preserved.

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
NVIDIA inference API default, with optional Local routing for Open Task. Model preparation does not change Studio's
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

In Stage 3, **Models & connection** opens the shared Model settings. Preferences apply to new work; active requests are never automatically replayed. On NVIDIA, choose **Hired + Standby** and expand **Standby specialists** to change Casey’s or a backup’s model. You can return to Hired only before starting the task. Choices are locked while the team is working. Casey and backups use the selected connection model with Local or other external providers; hires retain their individual choices. Hires choose models individually.

### Stages 1 and 2: Hiring and Agent lounge

Open **Settings → Model → Local → Configure**, search the model list, and connect a model with tool calling:

| Server | Endpoint |
| --- | --- |
| Ollama on this PC | `http://127.0.0.1:11434/v1` |
| vLLM on this PC | `http://127.0.0.1:8000/v1` (use its actual port) |
| Other OpenAI-compatible server | Its API URL ending in `/v1` |

Keyless local servers need no API key. Provider keys entered in these settings are kept in memory for the current tab and must be re-entered after refresh, tab closure, or app restart. The enabled connections supply individual hired-agent models and the **Open Task** selection. A host-saved NVIDIA key from `api.cfg` remains available after refresh; only keys entered in the browser need re-entry.

## Try the demo

1. **Hiring:** choose a character, role, tone, and skills.
2. **Agent lounge:** chat with a hired agent, inspect files, or approve OpenShell access.
3. **Open Task:** enter Stage 3 from the studio overview or Studio Map. Casey coordinates your task in one room.

**Programmer** equips the **Coding** skill for small, self-contained desktop pages and games. It saves a working file and applies focused follow-up edits. **Web researcher** equips **Web research** for brief, cited answers, reading supplied URLs first. Both work directly in the Lounge and can join Casey's team; role and tone remain separate from tool permissions. Research creates a file only when requested or needed for a handoff. OpenShell researchers can save that brief inside their protected workspace; network access still needs the relevant policy approval.


**Open Task**: message Casey with `/goal` and a concrete task, optionally attaching documents. Choose **Hired only** (default, Casey coordinates your hires) or **Hired + Standby** (your hires with built-in backups). In both modes, idle agents follow you into the room and wait on benches; assigned agents move to workbenches. Following alone does not start model work. Any hired role can participate; Coding and Web research are not requirements. A **Programmer** and a **Web researcher** are one useful pairing for a research-and-build demo. Hired only needs at least one available hire. Hired + Standby can use backups even without hires. Each keeps its identity, model and permissions. Open Task retains its history, documents and results; changing rooms does not cancel active work.

This experimental `preview/visitor-agent-teams` branch adapts Paul Roeseler's hired-agent collaboration from `proeseler/stage3-demo` to the current dispatcher, preserving its verified handoffs, bounded recovery and cancellation.

To require a hired agent’s participation, name it and its assignment in either mode:

```text
/goal Have Pixel build a small desktop counter page.
```

In **Hired + Standby**, you can explicitly combine a hire and a backup, such as “Let Scout find three places in Barcelona, then have Pixel turn the findings into a page.” Casey selects each agent and its work explicitly. If that selection is incomplete, Casey gets one chance to clarify it before any specialist starts; the app does not guess roles from nearby keywords.

Pixel performs the coding when its equipped Coding skill covers the request. If Coding is missing, Casey explains the missing skill instead of forcing participation or silently assigning the job to Cody. Its identity, voice, workspace and OpenShell policy remain unchanged. When a suitable named agent lacks upstream evidence, it may still contribute its own in-scope portion with clear gaps. Busy or unavailable agents are reported; cancellation, connection failures and the overall time budget can still stop the task. The maximum of three specialists applies, with a different agent required for independent review.

The team choice is captured when you submit and locked while the task runs. Room changes preserve it; reloading or resetting Open Task defaults new tasks to **Hired only**. Changing the team after a completed task keeps earlier results. Reset Open Task first when you want a clean demonstration.

Hired agents use their selected **Hiring** model for both specialist assignments and closing reactions. Casey and built-in backups use **Open Task** settings, including its existing per-agent NVIDIA model choices. Ensure the Open Task connection and each participating hire’s model connection are ready. Agents invited for assignments or reactions are reserved so chat, Heartbeat and edits do not overlap the team task. Busy or unavailable guests are skipped under the existing reaction rules. In either team mode, hired specialists do not receive a duplicate closing-reaction call. Follow-up messages to a hired specialist open its existing Lounge conversation. Scenario reset clears the shared team history and exported results, while preserving the hired agent's own files and identity.

`/plan` and `/plans` remain supported aliases for `/goal`. Only Open Task's Casey chat supports these team commands. Lounge agents without Tech Radar accept direct messages. Casey's Open Task chat starts with `/goal ` and restores it after a successful send. Delete the prefix to send a direct message. Specialists accept direct messages only, without `/goal` hints or suggestions; send team tasks to Casey. Their inputs start empty and clear after sending; existing drafts stay intact when switching characters.

**Data analyst** equips **Data interpretation** as its fixed core skill. Use it in the Lounge to compare supplied CSV or table values, rank figures and save findings with clear units and limitations. Pair it with a Programmer for the store or GPU dashboard examples in Open Task; additional skills remain editable.

Idle hired agents follow you into Open Task and wait beside Casey. Assigned agents move to workbenches with their existing appearance and stay there after delivering their work, including while Casey plans the next task. Once the next team is confirmed, replaced hires move directly to the waiting seats. Closing personal reactions happen in place, without a trip through the Lounge. Leaving the room sends idle agents back to the Lounge. Their contributions remain available in the results. Travel is visual only and never delays model execution. Switching rooms does not restart the walk; reduced motion places agents directly. Built-in backups keep their normal entrance. Specialists execute in assignment order. The backup pool is Scout (Web Researcher), Ada (Data analyst), Iris (UX designer), Cody (Programmer), and Vera (Reviewer). Coding assignments, including those given to hired agents, prioritize a compact, usable desktop demo: no mobile layouts or touch controls, no optional polish loops, and no extra design pass unless needed. Save the core implementation in one pass and return once required work is delivered. Explicitly requested independent review is still required. Casey reserves a repair for an observed defect, not a repeated save/read confirmation.

**Mission Control** shows assignments, expected results, contributions, and Casey’s decisions in execution order. **Results** shows the current plan’s response and saved files, with previews for generated HTML pages. While a plan is running, Casey’s composer and the working specialist’s composer are disabled. Stop immediately shows a pending state and prevents duplicate clicks while cancellation is being sent; an in-flight runtime call may still need to settle. Partial and failed work remains visible rather than being presented as complete.

Example:

```text
/goal Build a self-contained desktop HTML page comparing the figures in the
attached CSV. Use only the supplied data and include a clear comparison chart.
```

**Heartbeat:** equip an agent with the **Tech Radar skill** to check for an unread technical article every 20 seconds and share a summary with a source link. The first check waits at least 10 seconds; runtime preparation or other model work may delay it further. Pause or resume in the agent panel. Any agent with this skill is automatic-only, including agents with additional skills: manual chat and attachments are disabled, and group chat requests exclude it. Remove the skill to restore manual chat; pausing Heartbeat does not enable it. [Heartbeat and Telegram details](docs/heartbeat.md).

**Settings → Location** sets the default city (Zurich). **Settings → Reset** offers **Remove agents** for Stages 1 & 2, **Reset Open Task**, and **Reset all** for Open Task and hired agents. Model and connection settings are preserved. The team utility Reset stops and clears Open Task while preserving hired agents and their personal files. **Settings → Telegram** relays new Heartbeat summaries while the connected tab stays open.

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

The bundled research guard enforces at most two searches (three bounded excerpts each), or five bounded page reads, per research job. After a search, save the available excerpts instead of opening more pages. Hired specialists inherit these Open Task budgets, bounded file responses and review limits. Their protected command calls have a five-call budget and a maximum 40-second timeout per call. Lounge research also receives concise research instructions and bounded fetched excerpts, with runtime context compaction. Neither changes OpenShell permissions or guarantees every request fits the model context.

OpenShell hires make public read requests inside their own sandbox instead of using host-side web tools. Websites start blocked and approvals belong to each agent. Approve a required site in that agent's **OpenShell Policy** panel, then retry. Verified denials identify the agent and blocked site in Open Task results; an HTTP error alone is not treated as a policy denial. Workspace-only work can continue without internet approval.

Lounge research answers ordinary questions directly; it saves a brief when requested or assigned as a team handoff. Its generated research instructions use the agent's actual transport: native web tools for standard agents, approved sandbox requests for OpenShell agents. Personal tone and reply styles remain in `SOUL.md`; Open Task uses its own role and delivery contracts.

Small saved evidence briefs and bounded excerpts from observed tool results are passed directly to Casey for synthesis. If the final reply cites a public URL absent from those results and their returned links, it is withheld as partial rather than labeled complete. This citation check does not verify every factual claim or establish that sources are current.

Research assignments have a 150-second budget across retries, whether Scout or a hired agent performs them. At the deadline, saved work and completed search/page excerpts are preserved for the team; missing evidence is reported honestly.

## Everyday commands

| Action | Command |
| --- | --- |
| Install / start fresh, clearing agents, work, context and usage history | `./bac start` |
| Start or apply app changes while preserving runtime data | `./bac start --keep-data` |
| Check status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| Stop services and local model, then reset Compose data and OpenShell policies | `./bac stop --all` |
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

### Optional browser testing

Playwright automates browser checks on Windows, Linux and macOS. It is a development dependency only: BaC, its Docker services and the movable information windows run normally without Playwright, Node.js on the host, or any Playwright-managed browser. In a source checkout, `./bac start` reports when the optional local Playwright package is absent but does not delay or block startup.

To prepare Chromium, Firefox and Microsoft Edge for tests, run from the repository root:

```bash
npm install --save-dev playwright
npx playwright install chromium firefox msedge
```

On supported Linux systems, Playwright can install the required OS libraries too:

```bash
npx playwright install --with-deps chromium firefox msedge
```

Microsoft Edge availability depends on the operating system and CPU architecture; it may not be available on ARM64 Linux systems such as DGX Spark. Installing a browser does not automatically run every test against it: tests launch Chromium with `chromium.launch()`, Edge with `chromium.launch({channel: 'msedge'})`, or Firefox with `firefox.launch()`. Do not add Playwright to `docker/runtime/package.json`, which contains production runtime dependencies.

### Scenario preview provenance

This preview builds on the Zurich snapshot and the Stage 3 contributions from Benjamin Bayart and Paul Roeseler. The final version containing Event Brief is preserved at [archive/event-brief-final-2026-10-15](https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2/-/tree/archive/event-brief-final-2026-10-15). This branch now contains Hiring, Agent Lounge and Open Task. Default startup clears runtime data; `./bac start --keep-data` preserves existing work. Open Task keeps its previous native identities, models and history when upgrading.

Open Task presentation lives in `src/stage-scenarios.json`, shared by the scene, navigation and accessible fallback. Stage 3 opens this room directly; old Event Brief navigation preferences are ignored. New room selections replace an in-progress camera move, and reduced-motion settings skip the animation. Retired workflow routes reject new work. Stable role slots, saved ownership records and cleanup compatibility remain so upgrades do not duplicate or orphan native agents.

### Files and recovery

Use **Files** in the team utility row to browse the selected specialist’s uploads and results. In the Lounge, use **Files** beside **Instructions** for the selected hired agent. The button is hidden when that agent has no files, and the file dialog has no agent selector. Open a file to preview or download it. **Instructions** shows AGENTS.md, IDENTITY.md and SOUL.md side by side, with Copy and no Download. Click the agent name or portrait for all saved definitions, including skills and memory. These are browser-based views of the server workspace, so they work when the demo runs on another computer. They do not open the presenter’s OS file manager.

Reset Open Task stays disabled until there is saved work to clear. Conversations, uploaded documents and results count as work; opening the room alone does not.

The default context budget is 32,768 tokens per agent session; the output cap is 16,384 tokens per response. These are demo settings, not universal model or OpenShell limits. Connections configured with less than 32,768 context tokens use at most half of their context for output, leaving the rest for input and tools. If a model hits its output limit, that role gets at most one concise retry in a fresh context, preserving saved files and completed tool results. Existing deliverable checks still apply. Context overflow can use the same single recovery allowance: Open Task reuses saved files and evidence with focused reads instead of rebuilding completed work. Failed model requests are not automatically replayed for other provider errors. Runtime preparation and read-only readiness checks have separate bounded recovery. To resume, run `./bac vllm` if needed, then `./bac start --keep-data` when preserving runtime data. See [context and output budgets](docs/runtime-settings.md#context-and-output-budgets).

### Shared model connections

In **Settings → Model**, Local and External Endpoint are independent checkboxes. Configure each connection, search the automatically loaded model list, and connect. External Endpoint supports NVIDIA Inference, OpenAI and Anthropic. An `api.cfg` key can supply NVIDIA automatically; newly entered keys stay in memory for the browser credential session.

New hired agents default to connected **Local**, otherwise the default model configured under **External Endpoint**. The collapsed Model summary shows the selected model; you do not need to open it before hiring. Expand **Model** below **OpenShell protection** to search the available models. Disconnected options are disabled. Each agent keeps its choice in the Lounge, Heartbeat and Open Task. Edit agent lets you change it while that agent is idle. An unavailable selected model blocks that agent rather than silently switching to another connection. If neither connection is ready, the summary shows **Not connected** and hiring waits for a connection. Existing agents can still be edited while their saved model is offline. Existing agents without a model choice retain the previous Lounge setting; editing other fields does not switch them to Local.

Stage-level defaults prefer Local for legacy Hiring/Lounge agents and External Endpoint for Stage 3; saved manual preferences are preserved. The panel highlights the actual ready connection rather than showing an ambiguous Auto option. For those stage-level preferences, if the preferred connection is disabled or unavailable, new work uses the other ready connection. Explicit per-agent choices do not use this fallback. If neither is ready, requests are blocked with **Model not connected**. Connection checks verify model availability, not model quality or task completion. Existing work is not retried automatically.

Use local/private endpoints reachable from the OpenClaw host. Local mode does not launch vLLM automatically. Scenario resets preserve connection settings. The launcher treats `api.cfg` as optional. When Open Task uses Local, a warning explains that it may be slower or produce less reliable results for complex requests. With neither connection ready, tasks remain blocked.

### Open Task team and models

Open Task uses Casey as its captain, your hired agents and optional standby specialists. Event Brief is retired on this branch; its old saved data is not resumed or shown as current work.

Casey and Open Task backups retain per-agent NVIDIA model choices; Local and other external providers use the selected connection model for those built-in agents. Hires keep their own models in either team mode.

In Open Task, click Casey's or a built-in specialist's model badge to search and change its NVIDIA model while the team is idle. The standby list offers the same control. An idle hire's badge changes only that hire's model. Selections apply to the next request and persist after reload; existing results are preserved.

Before Casey assigns any work, click a waiting hire's nameplate or character to open its panel and change its model. Selecting an agent does not start a task; model changes are locked while the agent is reserved for work.


## FAQ

### Switching between installed versions

Stop the currently running demo before starting another checkout. `./bac start` starts with clean runtime data; use `./bac start --keep-data` only when you want to retain the existing session.

If an older Docker installation left an incompatible stack or volumes, run `./bac stop --all` from that installation before starting the intended version. This also stops its managed local model and resets demo data volumes and OpenShell policies; model weights remain. Restart local inference with `./bac vllm` if needed. See [Docker setup and recovery](docs/docker-setup.md).

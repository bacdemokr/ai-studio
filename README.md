# NVIDIA Build-a-Claw

Hire personal agents, try their skills, and collaborate with Casey and specialist agents in the **Multi-Agent demo**.

## Start on a new PC

**Requires:** Ubuntu 24.04, rootful Docker Engine 28+, Docker Compose 2.24+, internet access, and permission to run `docker info`. Intel/AMD and ARM64 (DGX Spark) are supported.

Clone the private GitHub repository with an account that has access:

```bash
git clone https://github.com/bacdemokr/ai-studio.git
cd ai-studio
./bac start
```

Startup optionally loads the NVIDIA inference API key from `api.cfg`. If the file is empty, invalid or the API cannot be reached, Studio still starts so you can configure Local or External Endpoint in Settings. A failed validation preserves previously saved connections and prints a warning. Valid keys are checked with a small inference request before being saved.

Open **http://localhost:8080**. The validated key is available automatically under **Settings → Model → External Endpoint**. Enable **Local** and/or **External Endpoint**, then choose stage preferences below. Auto prefers Local for Stages 1/2 and External Endpoint for Stage 3.

The first start builds the runtime image for your PC and downloads the pinned OpenShell images. OpenClaw and OpenShell are included; no host Python or Node installation is needed. BaC does not install model weights. A local model server, if used for Stages 1 and 2, runs separately.

## Prepare a local model (optional)

`./bac vllm` starts or reuses **Qwen by default**, then waits for the exact model
ID and a small inference request to succeed. This command runs independently of
Docker, Studio, and the Stage 3 API key. Ordinary `./bac start` never starts or
waits for a local model, even if model configuration exists or model files are
missing. `./bac stop` stops the BaC services and their OpenShell sandboxes, but leaves the host model server running. Use `./bac stop --all` to also stop the local model launched by this installation. Externally managed model servers are left running and reported explicitly. Saved files, model weights and settings are preserved. The next `./bac start` resumes only the BaC sandboxes recorded by the shutdown command.

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
- GitHub tracks an **empty `api.cfg` placeholder**. Startup installs a local Git clean filter that stages an empty file while preserving your working key. Release packages also contain an empty file; the Docker image excludes it.

If you want to edit `api.cfg` and use Git **before your first start**, install the filter first:

```bash
bash scripts/setup-key-filter.sh
```

In Stage 3, **Models & connection** opens the shared Model settings. Preferences apply to new work; active requests are never automatically replayed. NVIDIA retains per-agent choices under **Agent API models**. Other external providers use the model selected for the shared endpoint. Event Brief and Open Task keep separate preferences.

### Stages 1 and 2: Hiring and Agent lounge

Open **Settings → Model → Local → Set up**, load the models, and connect a model with tool calling:

| Server | Endpoint |
| --- | --- |
| Ollama on this PC | `http://127.0.0.1:11434/v1` |
| vLLM on this PC | `http://127.0.0.1:8000/v1` (use its actual port) |
| Other OpenAI-compatible server | Its API URL ending in `/v1` |

Keyless local servers need no API key. Provider keys entered in these settings are kept in memory for the current tab and must be re-entered after refresh, tab closure, or app restart. The same enabled connections are available to all stages, with separate stage preferences.

## Try the demo

1. **Hiring:** choose a character, role, tone, and skills.
2. **Agent lounge:** chat with a hired agent, inspect files, or approve OpenShell access.
3. **Multi-Agent demo:** enter the **Event Brief** or **Open Task** floor directly from the studio overview or Studio Map. Both spaces branch directly off the Lounge concourse as equal choices, with their own signs and accent colors. Entering Stage 3 or choosing **Scenarios** shows the spaces together; signs show **Continue** when work is saved. Switching spaces never clears either workspace.

**Event Brief** restores the fixed Casey, Dylan, Alex and Morgan crew. Open **Plan an event**, enter event details, prepare the crew, and launch. The team produces researched demo ideas, an operations timetable and an event webpage. Dylan retains his OpenShell protection.

**Open Task** uses the Zurich Plan collaboration flow: message Casey with `/goal` and a concrete task, optionally attaching documents. Casey selects the needed specialists. Each scenario has its own team identities, chat history, model selections, documents and results. They share the Stage 3 API connection and hired-agent collection. Choosing another scenario does not cancel active work.

`/plan` and `/plans` remain supported aliases for `/goal`. Only Open Task's Casey chat supports these team commands. Lounge agents accept direct messages; Event Brief uses **Plan an event**. Casey's Open Task chat starts with `/goal ` and restores it after a successful send. Delete the prefix to send a direct message. Specialists accept direct messages only, without `/goal` hints or suggestions; send team tasks to Casey. Their inputs start empty and clear after sending; existing drafts stay intact when switching characters.

The room starts with Casey. The selected specialists join together and execute in assignment order. The pool is Scout (Web Researcher), Ada (Data analyst), Iris (UX designer), Cody (Programmer), and Vera (Reviewer). Dylan, Alex and Morgan appear only in Event Brief; they are not in the Plan specialist pool. Coding tasks prioritize a compact, usable desktop demo: no mobile layouts or touch controls, no optional polish loops, and no extra design pass unless needed. Cody aims to save the core implementation in one pass and returns once required work is delivered. Explicitly requested independent review is still required. Casey reserves a repair for an observed defect, not a repeated save/read confirmation.

**Mission Control** shows assignments, expected results, contributions, and Casey’s decisions in execution order. **Results** shows the current plan’s response and saved files, with previews for generated HTML pages. While a plan is running, Casey’s composer and the working specialist’s composer are disabled. Stop immediately shows a pending state and prevents duplicate clicks while cancellation is being sent; an in-flight runtime call may still need to settle. Partial and failed work remains visible rather than being presented as complete.

Example:

```text
/goal Build a self-contained desktop HTML page comparing the figures in the
attached CSV. Use only the supplied data and include a clear comparison chart.
```

**Heartbeat:** hire **Tech Radar** to share one previously unshared technical article every 30 seconds, with a source link. Pause or resume in the agent panel. Tech Radar is automatic-only: manual chat and attachments are disabled, and group chat requests exclude it. [Heartbeat and Telegram details](docs/heartbeat.md).

**Settings → Location** sets the default city (Zurich). **Settings → Reset** offers **Remove agents** for Stages 1 & 2, **Reset scenario** for the selected Stage 3 scenario, and **Reset all** for both. Reset all stops and clears both Stage 3 scenarios before removing hired agents; model and connection settings are preserved. The **Reset button in the team utility row** stops work and clears data only in the selected scenario after confirmation; the other scenario, personal agents and model settings are preserved. **Settings → Telegram** optionally relays new Heartbeat summaries while the connected tab stays open.

### Review and bounded rework

Casey can answer directly or select up to three specialists. Simple tasks need no fixed team size. To require review, say so explicitly:

```text
/goal Analyze the attached earnings table. Add an independent review of the
calculations, units, reporting periods, and conclusions before the final answer.
```

- Requested review is included in the initial team, normally Ada then Vera for supplied-data analysis. Casey cannot mark the request complete by skipping that review. A planned code review also runs before completion.
- Between stages, Casey checks whether the next assignment can proceed. General content revisions are not dispatched at every intermediate checkpoint.
- A missing required file or a recognized output-limit failure can use one bounded recovery attempt. At final synthesis, Casey can instead request one targeted repair from an already participating specialist for a concrete unmet requirement. These paths share the repair allowance; they do not create repeated retry loops.
- No new specialist joins during a repair, and no automatic second specialist review follows it. Casey checks the revised contribution and states what remains unverified. If review or required work cannot finish, the result is partial or unavailable.
- A plan has a 600-second dispatch budget. This is not a guaranteed wall-clock finish time: cancellation and timeouts may need to wait for an in-flight runtime call. Saved work is retained.

Saved-file checks prove delivery, not correctness. Specialist reviews are static inspections unless actual execution evidence is available. Generated pages run in a restricted preview, so browser storage must be optional. Local JavaScript form handlers and validation work; network requests, actual form submissions and parent-page access stay blocked. Offline demos must not promise emails, bookings or remote saves.

Static review uses bounded source excerpts: at most eight reads, 120 lines per read, and 18,000 retained source characters per plan. Duplicate reads are blocked. Vera must disclose unread sections or unverified requirements; reaching the limit does not certify the whole artifact. This reduces repeated-read context overflow without limiting Cody’s saved code length.

### Research limits

Scout uses keyless Parallel Search: one focused search and 2–3 useful findings by default, then saves a short cited brief. Fewer findings are acceptable; stale or irrelevant results are reported honestly. No separate search API key is needed.

The bundled research guard enforces at most two searches (three bounded excerpts each), or five bounded page reads, per research job. After a search, Scout saves the available excerpts instead of opening more pages. These limits apply only to Scout’s `/goal` research; other agents and OpenShell policies are unchanged.

Small saved evidence briefs and bounded excerpts from observed tool results are passed directly to Casey for synthesis. If the final reply cites a public URL absent from those results and their returned links, it is withheld as partial rather than labeled complete. This citation check does not verify every factual claim or establish that sources are current.

Scout has a 150-second research budget across retries. At the deadline, saved work and completed search/page excerpts are preserved for the team; missing evidence is reported honestly.

## Everyday commands

| Action | Command |
| --- | --- |
| Install / start / apply app changes and validate the key | `./bac start` |
| Check status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| Stop services, sandboxes and this installation’s local model | `./bac stop --all` |
| **Delete BaC and its data** | **`./bac remove`** |

To update, finish active work, then run in the repository folder:

```bash
git pull --ff-only
./bac start
```

Use normal Git commands to update your checkout. Resolve local changes or divergent history before pulling. With the Git key filter configured, your local key stays in `api.cfg`.

`start` recreates services and can interrupt active work. It preserves agents, conversations, and results. App changes reuse the runtime image; dependency changes rebuild it automatically. There is no `./bac restart` or `./bac update` command. Use `git pull --ff-only` followed by `./bac start` for app updates; `./bac vllm --restart` restarts only the local model server.

`remove` asks you to type `remove` once. It deletes BaC containers, data, shared files, backups, recorded project images, local settings, and `api.cfg`. A source checkout keeps its code; an installed release folder is removed. Other projects and your model server remain.

[Setup & troubleshooting](docs/docker-setup.md) · [Model settings](docs/runtime-settings.md) · [Development & tests](docs/development.md)

### Scenario preview provenance

This preview starts from the frozen Zurich snapshot (`feba7df`). The viewport improvements, room information guides and side-by-side agent definition viewer adapt Benjamin Bayart’s contributions (`ee717f3`, `8993a20`, `09b4794`, `3c54aba`); the initial Stage 3 picker took inspiration from his scenario cards; scenarios now appear as separate 3D floors. The fixed Event Brief workflow is restored from `archive/bac-planning` (`94198b6`). Startup retains the overview and does not delete agents. There is no `./bac restart` command. Existing Zurich team ownership migrates to Plan without changing native identities; Event Brief creates a separate team when first used.

Scenario presentation lives in `src/stage-scenarios.json`, shared by the scene, navigation and accessible fallback. Floors branch in pairs from a common concourse and use automatic overview framing, so three or four scenarios fit without hard-coded camera coordinates. New scenarios also require an explicit backend workflow and ownership identifier; adding a visual entry alone does not enable a new workflow.

### Files and Event Brief recovery

Use **Files** beside the team API controls to browse the selected scenario’s team results or a member’s `inbox/` and `artifacts/`. In the Lounge, use **Files** beside **Code**. Open a file to preview or download it. Definition files in **Agent files** also have a Download button. These are browser-based views of the server workspace, so they work when the demo runs on another computer. They do not open the presenter’s OS file manager.

Empty scenarios have Reset disabled. Event preparation, conversations, uploaded documents and results count as saved work. Reset clears only the selected scenario; the built-in Event Brief template remains available for the next run.

Event Brief keeps the bounded output budget rather than globally increasing it to the context limit. If a model hits its output limit, that role gets at most one concise retry in a fresh context, preserving saved files and completed tool results. Existing deliverable checks still apply. Other connection or provider failures are not automatically retried. To resume after a full shutdown, run `./bac vllm` if needed, then `./bac start`.

### Shared model connections

In **Settings → Model**, Local and External Endpoint are independent checkboxes. Set up each connection, load a model, and connect. External Endpoint supports NVIDIA Inference, OpenAI and Anthropic. An `api.cfg` key can supply NVIDIA automatically; newly entered keys stay in memory for the browser credential session.

Auto prefers Local for Hiring/Lounge and External Endpoint for Stage 3. If the preferred connection is disabled or unavailable, new work uses the other ready connection. If neither is ready, requests are blocked with **Model not connected**. Connection checks verify model availability, not model quality or task completion. Existing work is not retried automatically.

Use local/private endpoints reachable from the OpenClaw host. Local mode does not launch vLLM automatically. Scenario resets preserve connection settings. The launcher treats `api.cfg` as optional. When Open Task uses Local, a warning explains that it may be slower or produce less reliable results for complex requests. With neither connection ready, tasks remain blocked. Event Brief does not show this Open Task warning.

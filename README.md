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

Startup checks the NVIDIA inference API key in `api.cfg`. If the file is empty or the API rejects the key, startup prints instructions and exits. Edit `api.cfg`, then run `./bac start` again. Startup checks access to the configured team models and makes a small inference request before restarting services.

Open **http://localhost:8080**. **Stage 3 is configured automatically** with the validated key. For **Stages 1 and 2**, connect a model separately in **Settings → Model**.

The first start builds the runtime image for your PC and downloads the pinned OpenShell images. OpenClaw and OpenShell are included; no host Python or Node installation is needed. BaC does not install model weights. A local model server, if used for Stages 1 and 2, runs separately.

## Prepare a local model (optional)

`./bac vllm` starts or reuses **Qwen by default**, then waits for the exact model
ID and a small inference request to succeed. This command runs independently of
Docker, Studio, and the Stage 3 API key. Ordinary `./bac start` never starts or
waits for a local model, even if model configuration exists or model files are
missing. `./bac stop` stops Studio only.

```bash
./bac vllm                # Prepare Qwen, default wait: 600 seconds
./bac vllm --model qwen   # Same, explicit selection
./bac vllm --model gemma  # Only if a Gemma installation is configured
./bac vllm --restart      # Stop the configured server, restart and wait
./bac vllm --status       # Inspect the local model
./bac vllm --logs         # Show the managed model service journal
./bac vllm --stop         # Stop only a model this helper launched
./bac start                # Start Studio separately
```

Put a machine-specific `local-model.json` beside `bac`. It contains a `models`
object and optional `wait_seconds` (1–3600). Each model specifies its `model_id`,
`model_path`, `base_url`, `context_window`, exact `argv` list, and `env` object.
Qwen remains the command default regardless of `default_model` or `enabled` in
this file. Executable and weight paths can point anywhere on this PC. The
existing parent installation is configured on this machine, but the parent demo
is never invoked or modified. No model files or runtime packages are downloaded.
If paths are missing, `vllm` explains the problem; `start` is unaffected.

After starting Studio, connect Stages 1 and 2 in **Settings → Model → Local**
using the model ID and endpoint printed by `vllm`. Stage 3 retains its separate
NVIDIA inference API connection. Model preparation does not change Studio's
saved provider settings.

The helper requires host Python 3.9+ and a systemd user session to launch a new
background model service. It displays loading progress every 15 seconds, fails
early if the service exits, and times out with a useful error. An unexpected
listener is rejected. A healthy external server is reused and never stopped.
A newly launched model is stopped if readiness fails. Logs remain in the user
journal; model files are preserved. Changing a managed model's launch settings
requires `./bac vllm --stop` first.

Machine-specific configuration and service identity under `.local-model/` are
ignored by Git. Do not put API credentials in this unauthenticated local model
configuration. BaC removal does not delete the external weights or vLLM runtime;
stop a helper-owned model explicitly before removing Studio.

## API key and model settings

### Stage 3: Multi-Agent demo

Scout uses keyless Parallel Search: one focused search and 2–3 useful findings by default, then immediately saves a short cited brief and finishes without follow-up browsing. Fewer findings are acceptable; stale or irrelevant results are reported honestly. No separate search API key is needed. Scout has a 150-second research budget across retries. At the deadline, saved work and completed search/page excerpts are preserved for the team; missing evidence is reported honestly.

For code tasks, a planned Vera review runs before Casey can mark the result complete. Saved-file checks confirm delivery; specialist reviews are static inspections unless actual execution evidence is available. Generated pages run in a restricted preview, so browser storage must be optional.


`api.cfg` sits beside `bac` and contains only your NVIDIA inference API key on one line. Edit this file directly; startup never asks you to type a key in the terminal. To change the key, edit `api.cfg`, then run:

```bash
./bac start
```

- The validated key is saved on this computer with owner-only file permissions. Refreshing the browser does not require re-entry.
- Missing or rejected keys stop startup with instructions to edit `api.cfg`. Empty files are detected before Docker is invoked.
- Network or API service failures stop startup without replacing your key or restarting running services. Startup never silently falls back to the previous saved key.
- GitHub tracks an **empty `api.cfg` placeholder**. Startup installs a local Git clean filter that stages an empty file while preserving your working key. Release packages also contain an empty file; the Docker image excludes it.

If you want to edit `api.cfg` and use Git **before your first start**, install the filter first:

```bash
bash scripts/setup-key-filter.sh
```

In Stage 3, open **API & models** to view connection status and choose each agent’s model. Select the single **Apply changes** button to save your selections for the next request. The UI explains how to manage the key from the terminal; it has no Stage 3 key-entry form.

### Stages 1 and 2: Hiring and Agent lounge

Open **Settings → Model**, choose a provider, load the models, and connect. For a local model with tool calling, choose **Local / on-prem**:

| Server | Endpoint |
| --- | --- |
| Ollama on this PC | `http://127.0.0.1:11434/v1` |
| vLLM on this PC | `http://127.0.0.1:8000/v1` (use its actual port) |
| Other OpenAI-compatible server | Its API URL ending in `/v1` |

Keyless local servers need no API key. Provider keys entered in these settings are kept in memory for the current tab and must be re-entered after refresh, tab closure, or app restart. These settings do not change Stage 3’s connection or agent model selections.

## Try the demo

1. **Hiring:** choose a character, role, tone, and skills.
2. **Agent lounge:** chat with a hired agent, inspect files, or approve OpenShell access.
3. **Multi-Agent demo:** message Casey or use `/plan` with a concrete task. Add documents when needed. Casey selects the specialists needed for the request.

**Mission Control** shows assignments and execution progress. **Results** shows the current plan’s response and saved files, with previews for generated HTML pages. While a plan is running, the composer shows a neutral progress notice; messaging resumes when it finishes or is stopped. Partial and failed work remains visible rather than being presented as complete.

Example:

```text
/plan Improve the attached webpage with interactive plots. Use the attached handoff,
keep the existing features, and save a self-contained HTML file.
```

**Heartbeat:** hire **Tech Radar** to share one previously unshared technical article every 30 seconds, with a source link. Pause or resume in the agent panel. [Heartbeat and Telegram details](docs/heartbeat.md).

**Settings → Location** sets the default city (Zurich). **Settings → Reset** manages demo data; Stage 3 also has its own **Reset** control. **Settings → Telegram** optionally relays new Heartbeat summaries while the connected tab stays open.

## Everyday commands

| Action | Command |
| --- | --- |
| Install / start / apply app changes and validate the key | `./bac start` |
| Check status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| **Delete BaC and its data** | **`./bac remove`** |

To update, finish active work, then run in the repository folder:

```bash
git pull --ff-only
./bac start
```

Use normal Git commands to update your checkout. Resolve local changes or divergent history before pulling. With the Git key filter configured, your local key stays in `api.cfg`.

`start` recreates services and can interrupt active work. It preserves agents, conversations, and results. App changes reuse the runtime image; dependency changes rebuild it automatically. There is no separate restart command.

`remove` asks you to type `remove` once. It deletes BaC containers, data, shared files, backups, recorded project images, local settings, and `api.cfg`. A source checkout keeps its code; an installed release folder is removed. Other projects and your model server remain.

[Setup & troubleshooting](docs/docker-setup.md) · [Model settings](docs/runtime-settings.md) · [Development & tests](docs/development.md)

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

Stage 3 uses `/plan` exclusively for team tasks. Mission Control shows only the current plan’s recorded assignments and results; before a plan starts, it shows an empty state. The retired event-planning pipeline and event results no longer appear. Saved historical files are preserved.

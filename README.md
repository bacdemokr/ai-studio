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

Startup checks the NVIDIA inference API key in `api.cfg`. If the file is empty or the API rejects the key, enter a valid key at the hidden terminal prompt. Startup checks access to the configured team models and makes a small inference request before restarting services.

Open **http://localhost:8080**. **Stage 3 is configured automatically** with the validated key. For **Stages 1 and 2**, connect a model separately in **Settings → Model**.

The first start builds the runtime image for your PC and downloads the pinned OpenShell images. OpenClaw and OpenShell are included; no host Python or Node installation is needed. BaC does not install model weights. A local model server, if used for Stages 1 and 2, runs separately.

## API key and model settings

### Stage 3: Multi-Agent demo

`api.cfg` sits beside `bac` and contains only your NVIDIA inference API key on one line. You can enter it at the startup prompt or edit the file yourself. To change the key, edit `api.cfg`, then run:

```bash
./bac start
```

- The validated key is saved on this computer with owner-only file permissions. Refreshing the browser does not require re-entry.
- Missing or rejected keys prompt again in an interactive terminal. Noninteractive startup exits with instructions.
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
| Download the latest GitHub `main` | `./bac update` |
| Check status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| **Delete BaC and its data** | **`./bac remove`** |

To update, finish active work, then run in the repository folder:

```bash
./bac update
./bac start
```

`update` requires a clean `main` checkout and fast-forwards only. It refuses divergent commits, development branches, and local source changes. It does not stop running work. Your local key stays in `api.cfg` with the Git filter configured.

`start` recreates services and can interrupt active work. It preserves agents, conversations, and results. App changes reuse the runtime image; dependency changes rebuild it automatically. There is no separate restart command.

`remove` asks you to type `remove` once. It deletes BaC containers, data, shared files, backups, recorded project images, local settings, and `api.cfg`. A source checkout keeps its code; an installed release folder is removed. Other projects and your model server remain.

[Setup & troubleshooting](docs/docker-setup.md) · [Model settings](docs/runtime-settings.md) · [Development & tests](docs/development.md)

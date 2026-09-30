# Install and run BaC

**Requires:** Ubuntu 24.04, Docker Engine 28+, Compose 2.24+, internet for startup key validation and image downloads, and permission to run `docker info`. Use local, rootful Docker Engine. Docker Desktop on Mac is a development/test environment, not this deployment target.

## First start

Clone the repository on your PC, then start it. The same commands work on Intel/AMD and ARM64 (DGX Spark):

```bash
git clone https://github.com/bacdemokr/ai-studio.git
cd ai-studio
./bac start
```

The first start creates `.env` from the supplied example, builds the pinned runtime image and downloads the OpenShell images. Later starts reuse the image unless its dependencies changed.

Startup works without an inference key. Use Stage 3 **API & models** to connect the API for this browser session and save model selections with **Apply changes**.

Open **http://localhost:8080**. For Stages 1 and 2, open **Settings → Model**. Choose **Local / on-prem**, enter the endpoint, **Load models**, then **Connect model**.

- Ollama on this PC: `http://127.0.0.1:11434/v1`
- Another compatible server: its URL ending in `/v1`, for example `http://127.0.0.1:8000/v1`
- Choose a model with tool calling. Leave the key empty if the server needs none.

The model stays on the host; Linux host networking reaches localhost. BaC installs no model weights or GPU drivers. Its pinned OpenClaw and OpenShell runtimes are isolated from existing host installations. No host Python or Node is required.

## Commands

| Action | Command |
| --- | --- |
| Install / start / apply updated code | `./bac start` |
| Check status | `./bac status` |
| View recent logs | `./bac logs` |
| Stop, keep data | `./bac stop` |
| **Uninstall BaC and its data** | **`./bac remove`** |

`./bac start` may interrupt active work. Stage 3 keeps its validated key across refreshes. Reconnect API-key providers for Stages 1 and 2 afterward. Keyless local models need no credential re-entry.

## Update

Finish active tasks, then run inside the same repository folder:

```bash
git pull --ff-only
./bac start
```

Keep your local `.env`, `shared` and `backups`; Git excludes them. If Git reports local edits or a diverged branch, resolve those before starting so you run the intended version.

| Layer | Updates |
| --- | --- |
| Runtime image: Python, Node, OpenClaw, OpenShell | Only when dependencies change |
| App files: UI, server, skills, characters | `git pull --ff-only`, then `./bac start` |
| User data: agents, conversations, results | Preserved separately |

Keep the repository folder: app files are copied into the container at startup, so host edits do not alter a running session. `./bac start` checks compatibility and rebuilds the runtime image only when necessary.

## If startup fails

| Message or symptom | Action |
| --- | --- |
| Missing or rejected inference key | Connect a valid key in Stage 3 **API & models** |
| Inference API unavailable or rate-limited | Check connectivity or wait, then retry; the existing key is not replaced |
| Docker unavailable | Start Docker; check `docker info` works for your account |
| Wrong architecture | Use Docker running locally on this PC and its native architecture |
| Missing source files | Check `git status`; restore missing tracked files before starting |
| Port occupied | Change the relevant port in `.env`, then `./bac start` |
| Model unreachable | Check the host model server and its actual port; use a `/v1` endpoint |
| Model answers but tools fail | Try a tool-capable model and inspect the agent's Activity |
| Other startup failure | Run `./bac logs`; fix the reported issue, then `./bac start` |

Default ports: app **8080**, OpenClaw **28689**, OpenShell **28680**, health **28681**. Settings → Location changes the default city (Zurich). Settings → Reset deliberately clears demo data.

## Data and removal

Data lives in `bac-demo_studio-data`, `bac-demo_client-certs`, and `/var/lib/bac-openshell`. `shared/` is exposed as `/host-files`; Linux file permissions must allow container UID 10001. One BaC installation is supported per machine.

`./bac remove` asks you to type `remove` once. It deletes BaC containers, agents, chats, results, shared files, backups, recorded current/previous project images, local settings, and `api.cfg`. The repository code remains. Host model servers and other projects remain. Images still used elsewhere are reported rather than forcibly removed. Docker's shared build cache and manually copied backups outside this folder are not searched or pruned.

For a same-host backup, finish active work, then:

```bash
docker compose exec studio python3 scripts/container_runtime.py idle
./bac stop
mkdir -p backups
docker compose run --rm --no-deps --user 0 -v "$PWD/backups:/backup" init backup
./bac start
```

Backups contain app data and gateway metadata/certificates, not every sandbox's mutable filesystem. They are not complete machine-migration backups. Never use `docker compose down -v` for an update.

### Inference API key

Connect the key through Stage 3 **API & models**. It is validated and kept in memory only; the app does not load credential files. Reconnect after refreshing/closing the browser session or restarting the server. Model choices remain saved, but credentials do not. Legacy `api.cfg` and credential files are unused; remove them manually if they are no longer needed.

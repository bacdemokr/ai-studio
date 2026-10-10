# Install and run BaC

**Requires:** Ubuntu 24.04, Docker Engine 28+, Compose 2.24+, internet for startup key validation and image downloads, and permission to run `docker info`. Use local, rootful Docker Engine. Docker Desktop on Mac is a development/test environment, not this deployment target.

## First start

For the current preview, clone the GitLab branch on your PC. The same commands work on Intel/AMD and ARM64 (DGX Spark):

```bash
git clone --branch preview/stage3-scenarios https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2.git
cd bacdemo-tier2
./bac start
```

The first start creates `.env` from the supplied example, builds the pinned runtime image and downloads the OpenShell images. Later starts reuse the image unless its dependencies changed.

Startup optionally validates the NVIDIA inference key in `api.cfg`. A missing, rejected or unreachable key does not block startup. A validated key becomes available automatically in **Settings → Model**; Local and External Endpoint can also be configured there.

Open **http://localhost:8080** on the host or **http://SPARK_IP:8080** from another computer on the same trusted network. Settings are available through either address. In **Settings → Model**, configure Local and/or External Endpoint, then choose the connection for each stage. Model endpoint URLs are resolved by the Spark, not by the browser computer.

- Ollama on this PC: `http://127.0.0.1:11434/v1`
- Another compatible server: its URL ending in `/v1`, for example `http://127.0.0.1:8000/v1`
- Choose a model with tool calling. Leave the key empty if the server needs none.

The model stays on the host; Linux host networking reaches localhost. BaC installs no model weights or GPU drivers. Its pinned OpenClaw and OpenShell runtimes are isolated from existing host installations. No host Python or Node is required.

## Commands

| Action | Command |
| --- | --- |
| Start fresh, clearing runtime data | `./bac start` |
| Apply updated code and keep runtime data | `./bac start --keep-data` |
| Check status | `./bac status` |
| View recent logs | `./bac logs` |
| Stop, keep data | `./bac stop` |
| Stop managed model and remove the Compose stack/data volumes | `./bac stop --all` |
| **Uninstall BaC and its data** | **`./bac remove`** |

`./bac start` may interrupt active work and clears runtime data by default. Keys entered in the browser need reconnecting after refresh or restart; a validated NVIDIA key from `api.cfg` can supply all stages. Keyless local models need no credential re-entry.

## Update

Finish active tasks, then run inside the same repository folder:

```bash
git pull --ff-only
./bac start --keep-data
```

Keep your local `.env`, `shared` and `backups`; Git excludes them. If Git reports local edits or a diverged branch, resolve those before starting so you run the intended version.

| Layer | Updates |
| --- | --- |
| Runtime image: Python, Node, OpenClaw, OpenShell | Only when dependencies change |
| App files: UI, server, skills, characters | `git pull --ff-only`, then `./bac start --keep-data` |
| User data: agents, conversations, results | Preserved with `--keep-data`; cleared by plain `start` |

Keep the repository folder: app files are copied into the container at startup, so host edits do not alter a running session. `./bac start` checks compatibility and rebuilds the runtime image only when necessary.

## If startup fails

| Message or symptom | Action |
| --- | --- |
| Missing or rejected inference key | Startup continues; choose Local in Settings, or replace the key and use `./bac start --keep-data` |
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

`./bac stop` preserves saved data. `./bac stop --all` is a destructive reset: it also stops the managed local model, removes the Compose stack, and deletes the `studio-data` and `client-certs` volumes. Model weights, externally managed model servers, `shared/`, and `/var/lib/bac-openshell` remain.

`./bac remove` asks you to type `remove` once. It deletes BaC containers, agents, chats, results, shared files, backups, recorded current/previous project images, local settings, and `api.cfg`. The repository code remains. Host model servers and other projects remain. Images still used elsewhere are reported rather than forcibly removed. Docker's shared build cache and manually copied backups outside this folder are not searched or pruned.

For a same-host backup, finish active work, then:

```bash
docker compose exec studio python3 scripts/container_runtime.py idle
./bac stop
mkdir -p backups
docker compose run --rm --no-deps --user 0 -v "$PWD/backups:/backup" init backup
./bac start --keep-data
```

Backups contain app data and gateway metadata/certificates, not every sandbox's mutable filesystem. They are not complete machine-migration backups. Never use `docker compose down -v` for an update.

### Inference API key

`api.cfg` is optional and contains only the NVIDIA key on one line. There is no interactive key prompt. Startup checks model access and a small inference request before saving it. Empty, rejected or unreachable credentials produce a warning but do not block Settings or replace a valid saved connection. A fresh default start still clears runtime settings; use `--keep-data` when retaining them.

A validated key is saved with owner-only file permissions and can supply all stages through External Endpoint. The tracked placeholder and release packages contain no key, and the Docker image excludes `api.cfg`. Startup installs a Git clean filter that keeps the key out of commits while preserving the local file. Run `bash scripts/setup-key-filter.sh` first if you plan to edit the key and use Git before the first start.

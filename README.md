# NVIDIA Build-a-Claw

Hire personal agents, try their skills, and run **Multi-Agent demo (BaC Planning)**.

## Start on a new PC

**Ubuntu 24.04 · Docker Engine 28+ · Docker Compose 2.24+**

Clone this repository, then start:

```bash
git clone https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2.git
cd bacdemo-tier2
./bac start
```

Open **http://localhost:8080** → **Settings → Model** → connect your model.

The first start builds the runtime image for your PC (Intel/AMD or DGX Spark) and downloads the pinned OpenShell images. Internet and permission to run `docker info` are required. OpenClaw and OpenShell are included; no host Python or Node installation is needed. Your model server runs separately.

## Everyday commands

| Action | Command |
| --- | --- |
| Start / apply updated app files | `./bac start` |
| Restart | `./bac restart` |
| Status / recent logs | `./bac status` / `./bac logs` |
| Stop, keeping data | `./bac stop` |
| **Delete BaC and its data** | **`./bac remove`** |

**Update:** finish active tasks, then run in the same repository folder:

```bash
git pull --ff-only
./bac start
```

App changes reuse the runtime image; dependency changes rebuild it automatically. Agents, conversations and results are preserved. Start/restart can interrupt active work.

**Remove:** type `remove` once to confirm. Deletes BaC containers, data, shared files, backups, project images while keeping source code. Other projects and your model server remain.

## Model and location

Choose **Local / on-prem** in Settings → Model. Enter your existing endpoint, **Load models**, then **Connect model**:

| Server on this PC | Endpoint |
| --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` |
| Other OpenAI-compatible server | `http://127.0.0.1:8000/v1` or its actual port |

The model runs outside BaC's Docker stack. Use a model with tool calling; a keyless local server needs no API key. Keyed providers need reconnecting after refreshing/closing the tab or restarting the app.

**Settings → Location** sets the default city for all agents. Default: Zurich. **Settings → Reset** clears demo data.

## Try it

1. **Hiring:** choose a character, role, tone and skills.
2. **Agent lounge:** chat, inspect files, or approve OpenShell access.
3. **Multi-Agent demo (BaC Planning):** prepare the crew and run an event. View each agent's work in Results and Activity.

Agents research, schedule and write. The app coordinates the workflow, validates artifacts and renders data such as timetables. Failed runs remain visible.

[Setup & troubleshooting](docs/docker-setup.md) · [Presenter guide](docs/demo-runbook.md) · [Development & tests](docs/development.md)

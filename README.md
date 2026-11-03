# AI Studio

An interactive Build-a-Claw demo: hire agents, try them in the Lounge, and let Casey coordinate a team in **Open Task**.

Development branch: `preview/visitor-agent-teams`.

## Start

Use Ubuntu 24.04 with local, rootful Docker Engine **28+**, Docker Compose **2.24+**, and permission to run `docker info`. Supports amd64 and arm64, including DGX Spark. The first start needs internet access.

```bash
git clone --branch preview/visitor-agent-teams https://gitlab-master.nvidia.com/jinhol/bacdemo-tier2.git
cd bacdemo-tier2
./bac start
```

Open **http://localhost:8080** or **http://HOST_IP:8080** on your trusted network. In **Settings → Model**, connect Local or an External Endpoint with tool calling. An NVIDIA key in the optional `api.cfg` can supply the connection automatically; a missing or invalid key does not block startup.

**Plain `./bac start` clears demo runtime data. Use `./bac start --keep-data` to retain agents, conversations and results.**

The runtime includes OpenClaw and OpenShell. Host Python/Node and a local inference GPU are not required for the Docker app. Local inference runs separately; BaC does not download model weights. See [installation and troubleshooting](docs/docker-setup.md) or [source development](docs/development.md).

## Use the demo

1. **Hiring:** choose a character, tone, role and skills. Preset core skills stay fixed; extra skills can be added.
2. **Agent Lounge:** chat with a hire, edit its files/instructions, or demonstrate Tech Radar's scheduled Heartbeat.
3. **Open Task:** send `/goal` to Casey. **Hired only** uses your hires; **Hired + Standby** also permits backup specialists. Casey chooses assignments from the available skills and tools.

Example buttons fill an editable draft. Sample attachments upload only when you send it. Travel guide and Event page use **Settings → Location**.

**Mission Control** shows assignments, contributions and the final response. **Advanced reasoning** reveals provider-returned reasoning or summaries when available; opening it makes no extra model call. **Results** opens saved work, and **Usage & time** shows recorded usage. Missing skills and incomplete work are reported explicitly.

To demonstrate **OpenShell**, hire a protected Web researcher, ask it to read a website, inspect the decision in **OpenShell Policy**, approve access and resend. Website approvals do not grant host-file access. [Presenter walkthrough](docs/demo-runbook.md).

## Update and operate

Finish active work before updating:

```bash
git pull --ff-only
./bac start --keep-data
```

| Action | Command |
| --- | --- |
| Check services / recent logs | `./bac status` / `./bac logs` |
| Stop, preserving data | `./bac stop` |
| Prepare a configured local model separately | `./bac vllm` |
| Stop the managed model and reset app data and OpenShell policies | `./bac stop --all` |
| Uninstall BaC and its data | `./bac remove` |

Only one browser session uses the demo at a time. Tabs in the same browser at the same address share its agents. Browser-entered API keys need reconnecting after refresh; a validated host-saved `api.cfg` key remains available. [Connection details](docs/runtime-settings.md).

## Help and details

For an issue, use **Settings → Reset → Issue report → Copy diagnostics**, with your reproduction steps and approximate time. [Diagnostics](docs/diagnostics.md).

- [Presenter runbook](docs/demo-runbook.md) · [Demo goals](DEMO_WORKFLOW.md) · [Example scenarios](README_POSSIBLESCENARIOS.md)
- [Docker installation](docs/docker-setup.md) · [Local model helper](docs/local-model.md) · [Model settings](docs/runtime-settings.md)
- [Architecture](docs/architecture.md) · [Runtime behavior](docs/live-studio.md) · [Development and tests](docs/development.md)

# Studio settings

Open the Settings gear at the top right on localhost or the host’s LAN IP and select **Model**. Configure Local and/or External Endpoint, search for a text model with tool calling, then select a connection for Hiring/Lounge, Event Brief and Open Task. Open Task also supports per-agent NVIDIA model choices in its specialist roster. Each agent retains its own persona, tools, memory and protection settings. Pending missions must finish or be cancelled before shared settings change.

| Provider | Default base URL | Native OpenClaw API |
| --- | --- | --- |
| NVIDIA Inference (Employee only) | `https://inference-api.nvidia.com/v1` | `openai-completions` |
| OpenAI | `https://api.openai.com/v1` | `openai-responses` |
| Anthropic | `https://api.anthropic.com` | `anthropic-messages` |
| Local / on-prem | `http://127.0.0.1:8000/v1` | `openai-completions` |

NVIDIA keys come from [key management](https://inference.nvidia.com/key-management). Model IDs depend on the key's entitlement, so the app retrieves them instead of hardcoding a model catalogue. The explicit NVIDIA endpoint alias `https://inference.nvidia.com/v1` can also be entered under Connection options. Credentials never follow HTTP redirects. Local endpoints accept localhost or a private IP, ending in `/v1`; local/private app requests bypass environment HTTP proxies. Ollama normally uses `http://127.0.0.1:11434/v1` with no key. Its model ID must match an installed model returned by Load models. See [Ubuntu setup](ubuntu-setup.md).

The context limit defaults to 32,768 tokens and must match the chosen model server. It declares capacity to OpenClaw; it does not configure Ollama’s server-side `num_ctx`. Model listing checks access without generating a completion; it does not guarantee that every listed model supports the agent's tool calls. The readiness check currently requires the selected ID to appear in the model list. Anthropic lists up to 1,000 models; the dialog indicates if more exist.

Set the default city in Settings → Location. Supply task-specific requirements in Casey's Open Task `/plan` message. Event Brief uses its own Plan an event form for dates, venue and event requirements.

## Stage 3 connection and models

`./bac start` optionally loads the NVIDIA inference key from `api.cfg`. Empty, rejected or unreachable credentials do not block Studio from starting; configure Local or External Endpoint in Settings instead. Valid keys are checked with a small inference request and saved on the host. Browser refreshes do not clear this host key. To replace it, edit `api.cfg` and restart with `./bac start --keep-data` if existing runtime data should be preserved.

Stage 3's **Models & connection** opens the shared Model settings. Event Brief uses its selected connection model for the entire team. For Open Task with NVIDIA, click the model beside each agent in **Standby specialists** to search and save a different model. Other external providers and Local use the selected connection model. Model changes apply to new requests.

The Git clean filter installed by startup keeps the tracked `api.cfg` empty while preserving its local contents. Configure it with `bash scripts/setup-key-filter.sh` before editing the key if you plan to use Git before the first startup. Release packages contain an empty placeholder.

## Storage and access

Non-secret preferences live at `$BAC_DATA_DIR/host-settings.json`. Stages 1 and 2 API keys exist only in the app process memory, leased to the owning browser document. OpenClaw uses a loopback proxy with a non-secret placeholder; real provider credentials are never written to native config. Reload, tab closure, lease expiry or server restart requires reconnecting. See [session credentials](session-credentials.md).

Localhost and trusted-LAN visitors have the same Settings access, including shared model and location changes. The API still requires a browser session, a supported Host header, matching request origins and CSRF protection for writes. An SSH tunnel is optional. The demo does not distinguish remote attendees from presenters. Hosted inference sends model requests to the selected provider; OpenShell controls for agent tools remain separate.

For the Docker release, `./bac start` prepares a fresh runtime and clears saved runtime data. Use `./bac start --keep-data` to refresh existing services without clearing agents, work, context or usage. For host/development installations only, install once with `./bac dev setup`; Linux user services use `./bac dev start --model external`, and copied/edited source or macOS uses `./bac dev preview`. Save starts the installed runtime if it is offline. Start agents can start it explicitly. On Linux with systemd, Settings starts the same managed gateway service as the CLI. Without systemd (including macOS), the gateway runs as a detached process and logs to `$BAC_DATA_DIR/openclaw/gateway.log`; the app never installs runtime software from a browser request.

## Evidence and focused checks

Endpoint references:
- [NVIDIA Inference Hub — OpenAI-style API](https://nvidia.atlassian.net/wiki/spaces/NVEXAPJ/pages/3654919692): internal Glean search excerpts confirm the inference-api endpoint, bearer authorization and model discovery. Full page retrieval was unavailable.
- [NVIDIA models in Cursor guide](https://docs.google.com/document/d/1QfIUP5zgpz9oQWrmu_bw3rWMkmssdWl2FFeZUrzaCBw): internal search excerpts show the alternate inference.nvidia.com endpoint.
- [OpenAI model listing](https://developers.openai.com/api/reference/resources/models/methods/list).
- [Anthropic model listing](https://platform.claude.com/docs/en/api/models/list).
- [Pinned OpenClaw provider documentation](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/concepts/model-providers.md).

Focused checks cover provider isolation, key masking and file permissions, pending-job protection, authorization headers, localhost/LAN access, settings persistence and event defaults. All four native provider configurations were accepted by the installed OpenClaw 2026.9.4 validator. Provider-format checks use fixtures; rehearse live completions and tool calls with the actual target model. The Ubuntu porting audit also exercises local model discovery, streamed completions, provider errors and key handling through a real HTTP fixture, without claiming GPU inference.

```bash
python3 -B -m unittest discover -s tests -p test_runtime_settings.py
# Disposable browser fixture; never use the attendee database for these checks:
python3 -B tests/fixture_settings.py
# In another terminal, with Playwright and Chrome installed:
node tests/settings.cjs
```

Settings has Model, Location, Telegram and Reset tabs. Settings → Reset provides Remove agents (Stages 1 & 2), Reset scenario (the selected Stage 3 scenario), and Reset all (both scenarios and hired agents). Model and connection settings are preserved. The separate Reset button beside Mission Control clears only the selected scenario after confirmation. The Model search loads the model list automatically; connection errors appear beside the controls.

Remote HTTP regression checks cover Settings, model selection, Usage, file previews/downloads, Copy and fullscreen using a disposable server:

```bash
python3 -B -m unittest discover -s tests -p test_remote_settings.py
python3 -B tests/fixture_scenarios.py
# In another terminal, with Playwright and Chrome installed:
node tests/remote-access-browser.cjs
```

## Location

Location accepts one city (default Zurich), stored under `location.city` in host settings. It is independent of the legacy event defaults and the current BaC brief. Saving is allowed while work is pending: existing work continues; future model calls receive the new default.

Only the managed location block in each existing agent/crew `USER.md` is replaced; custom notes and MEMORY.md remain. Newly hired agents inherit the same setting. The native adapter also sends the latest location on every model request so a reused OpenClaw session or sandbox cannot rely solely on a stale bootstrap file. Explicit task/event locations take precedence. Location changes do not restart services, change permissions or clear model credentials.

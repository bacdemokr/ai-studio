# Studio settings

Open the small Settings gear at the top right on localhost and select **Lounge model**. Select a provider, enter its API key, load the available model IDs and choose a text model that supports tool calling. These settings apply to hired agents in Stages 1 and 2. Stage 3 has a separate connection and per-agent models. Each agent retains its own persona, tools, memory and protection settings. Pending missions must finish or be cancelled before shared settings change.

| Provider | Default base URL | Native OpenClaw API |
| --- | --- | --- |
| NVIDIA Inference (Employee only) | `https://inference-api.nvidia.com/v1` | `openai-completions` |
| OpenAI | `https://api.openai.com/v1` | `openai-responses` |
| Anthropic | `https://api.anthropic.com` | `anthropic-messages` |
| Local / on-prem | `http://127.0.0.1:8000/v1` | `openai-completions` |

NVIDIA keys come from [key management](https://inference.nvidia.com/key-management). Model IDs depend on the key's entitlement, so the app retrieves them instead of hardcoding a model catalogue. The explicit NVIDIA endpoint alias `https://inference.nvidia.com/v1` can also be entered under Connection options. Credentials never follow HTTP redirects. Local endpoints accept localhost or a private IP, ending in `/v1`; local/private app requests bypass environment HTTP proxies. Ollama normally uses `http://127.0.0.1:11434/v1` with no key. Its model ID must match an installed model returned by Load models. See [Ubuntu setup](ubuntu-setup.md).

The context limit defaults to 32,768 tokens and must match the chosen model server. It declares capacity to OpenClaw; it does not configure Ollama’s server-side `num_ctx`. Model listing checks access without generating a completion; it does not guarantee that every listed model supports the agent's tool calls. The readiness check currently requires the selected ID to appear in the model list. Anthropic lists up to 1,000 models; the dialog indicates if more exist.

Set the default city in Settings → Location. Supply dates, venue and other task-specific requirements in your `/plan` message. The old Plan a BaC form is retired. Existing saved event defaults remain readable for compatibility.

## Stage 3 connection and models

Run `./bac start` to validate the NVIDIA inference key in `api.cfg`. Empty or rejected keys stop startup with instructions to edit the file and rerun the command; no key is requested interactively. Startup verifies model access and a small inference request, then saves the connection on the host for Stage 3. Browser refreshes do not clear this key. To replace it, edit `api.cfg` and run `./bac start` again.

Stage 3’s **API & models** panel displays connection status and terminal setup instructions. It has no key-entry form. Choose models for Casey and the specialists, then use the single **Apply changes** button. Model changes apply to the next request.

The Git clean filter installed by startup keeps the tracked `api.cfg` empty while preserving its local contents. Configure it with `bash scripts/setup-key-filter.sh` before editing the key if you plan to use Git before the first startup. Release packages contain an empty placeholder.

## Storage and access

Non-secret preferences live at `$BAC_DATA_DIR/host-settings.json`. Stages 1 and 2 API keys exist only in the app process memory, leased to the owning browser document. OpenClaw uses a loopback proxy with a non-secret placeholder; real provider credentials are never written to native config. Reload, tab closure, lease expiry or server restart requires reconnecting. See [session credentials](session-credentials.md).

The Settings API requires an existing browser session, CSRF protection for writes, a loopback peer and a localhost Host header. LAN participants do not see the button and cannot call these routes. For a remote host, forward port 8080 through SSH. Treat the local operating-system account as trusted. Hosted inference sends model requests to the selected provider; OpenShell controls for agent tools remain separate.

For the Docker release, `./bac start` prepares the runtime or refreshes existing services while preserving saved data. For host/development installations only, install once with `./bac dev setup`; Linux user services use `./bac dev start --model external`, and copied/edited source or macOS uses `./bac dev preview`. Save starts the installed runtime if it is offline. Start agents can start it explicitly. On Linux with systemd, Settings starts the same managed gateway service as the CLI. Without systemd (including macOS), the gateway runs as a detached process and logs to `$BAC_DATA_DIR/openclaw/gateway.log`; the app never installs runtime software from a browser request.

## Evidence and focused checks

Endpoint references:
- [NVIDIA Inference Hub — OpenAI-style API](https://nvidia.atlassian.net/wiki/spaces/NVEXAPJ/pages/3654919692): internal Glean search excerpts confirm the inference-api endpoint, bearer authorization and model discovery. Full page retrieval was unavailable.
- [NVIDIA models in Cursor guide](https://docs.google.com/document/d/1QfIUP5zgpz9oQWrmu_bw3rWMkmssdWl2FFeZUrzaCBw): internal search excerpts show the alternate inference.nvidia.com endpoint.
- [OpenAI model listing](https://developers.openai.com/api/reference/resources/models/methods/list).
- [Anthropic model listing](https://platform.claude.com/docs/en/api/models/list).
- [Pinned OpenClaw provider documentation](https://github.com/openclaw/openclaw/blob/v2026.9.4/docs/concepts/model-providers.md).

Focused checks cover provider isolation, key masking and file permissions, pending-job protection, authorization headers, localhost access, settings persistence and event defaults. All four native provider configurations were accepted by the installed OpenClaw 2026.9.4 validator. Provider-format checks use fixtures; rehearse live completions and tool calls with the actual target model. The Ubuntu porting audit also exercises local model discovery, streamed completions, provider errors and key handling through a real HTTP fixture, without claiming GPU inference.

```bash
python3 -B -m unittest discover -s tests -p test_runtime_settings.py
# Disposable browser fixture; never use the attendee database for these checks:
python3 -B tests/fixture_settings.py
# In another terminal, with Playwright and Chrome installed:
node tests/settings.cjs
```

Settings has Lounge model, Location, Telegram and Reset tabs. Settings → Reset removes hired Lounge agents and their data. The separate Reset button beside Mission Control stops Stage 3 work and clears team data after confirmation. Switching tabs preserves model drafts. Load models displays a visible list (manual model IDs remain supported); missing keys, empty responses and errors appear next to the model controls.

## Location

Settings has Model, Location and Reset tabs. Location accepts one city (default Zurich), stored under `location.city` in host settings. It is independent of the legacy event defaults and the current BaC brief. Saving is allowed while work is pending: existing work continues; future model calls receive the new default.

Only the managed location block in each existing agent/crew `USER.md` is replaced; custom notes and MEMORY.md remain. Newly hired agents inherit the same setting. The native adapter also sends the latest location on every model request so a reused OpenClaw session or sandbox cannot rely solely on a stale bootstrap file. Explicit task/event locations take precedence. Location changes do not restart services, change permissions or clear model credentials.

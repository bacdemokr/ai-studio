# Studio settings

Open the Settings gear on localhost or the host's trusted LAN address. **Model**, **Location**, **Telegram** and **Reset** share one dialog. Switching tabs with the mouse or keyboard preserves unsaved drafts.

## Model connections

1. Enable **Local** and/or **External Endpoint**, then choose **Configure**.
2. Select the provider and search the **Model** field. The catalogue loads automatically; there is no separate Load models button.
3. Choose **Connect & enable**.
4. Under **Stage connections**, choose a connection for Hiring & Agent lounge, Event Brief and Open Task, then **Save changes**.

With both connections ready, the initial defaults prefer Local for Stages 1/2 and External for Stage 3. Saved manual choices take precedence. When upgrading a data directory that predates shared connections, the selected host provider is retained. If the preferred connection becomes unavailable, new requests use the other ready connection. If neither is ready, the app shows **Model not connected**. Active model requests are not replayed on another connection.

Open Task shows a warning when using Local because complex tasks may take longer or produce less reliable results. Event Brief supports Local without that warning. Starting Studio or selecting Local does not start a model server; use `./bac vllm` or an existing server first.

The demo manages its own skill files. Native skill file watching and autonomous skill reviews are disabled: repeated file-change notifications can rebuild metadata for every retained agent and delay the gateway. Unchanged files are left untouched; registration publishes an instruction revision when content changes. After editing skill files directly outside the app, re-prepare the agent or restart the runtime.

| Provider | Default endpoint | OpenClaw API format |
| --- | --- | --- |
| NVIDIA Inference (Employee only) | `https://inference-api.nvidia.com/v1` | `openai-completions` |
| OpenAI | `https://api.openai.com/v1` | `openai-responses` |
| Anthropic | `https://api.anthropic.com` | `anthropic-messages` |
| Local / on-prem | `http://127.0.0.1:8000/v1` | `openai-completions` |

External endpoints are fixed in the editor. A verified reusable key is disabled and labelled with its source, such as **API key verified · api.cfg**. New keys entered in Settings last for the browser tab's credential lease. A validated host-saved NVIDIA key can supply all stages after refresh. See [credential storage](session-credentials.md).

Local endpoints must be reachable from the app/OpenClaw host, not from the presenter's browser computer. Use localhost or a private IP ending in `/v1`. Ollama normally uses `http://127.0.0.1:11434/v1`. The selected model must appear in the server's catalogue and support the tools needed by the demo. Readiness verifies model availability, not successful completion of every task.

## Scenario models

- **3-1 Event Brief:** Riley, Dylan, Alex and Morgan all use the selected connection model.
- **3-2 Open Task:** an external NVIDIA connection supports per-agent model choices. Expand **Standby specialists**, click an agent's model, search and select. Changes save immediately. Local and other providers use the shared connection model for the whole team.

**Models & connection** opens these shared settings. Connection changes are blocked while queued or active work is present; per-agent choices are locked while the team is busy or resetting. See [Open Task models](plan-team-models.md).

## Context and output budgets

- **Context: 32,768 tokens by default.** This is the capacity the demo configures for one agent session: instructions, conversation, tool results and room for the reply. Agents have separate sessions even when they use the same model.
- **Output: at most 16,384 tokens per response.** Shared connections use `min(16,384, context / 2)`. For example, a 16K context allows at most 8K output. This is a cap, not a target reply length.
- These are application settings, not fixed OpenClaw or OpenShell limits. The model server must support the configured context and output. A larger-capacity model does not require increasing the demo budget.

Open **Configure → Advanced → Context limit** to inspect or change the budget. Advanced options start collapsed. The editor retains an existing provider context value or uses 32K for a new provider; it does not infer the model's capacity from its name. Set up local servers with sufficient context before presenting. This setting does not resize Ollama's `num_ctx` or vLLM's server context.

The runtime bounds web excerpts and enables context compaction with a pre-call check. These reduce growth during research but cannot guarantee that every request fits. A large document, accumulated conversation or model-specific limit can still cause a failure. Dylan gets one fresh-context recovery for an Event Brief context overflow: validate saved themes first, reuse successful research and repair only missing work. This shares the existing one-retry allowance with output-limit recovery; a second failure stops. Other context failures still require inspecting saved work, narrowing the task or resetting the appropriate conversation/scenario before trying again. See `scripts/runtime_settings.py` for the current limits.

## Optional api.cfg

`api.cfg` contains one NVIDIA key beside `bac`. Startup validates it with model discovery and a small inference request before saving it on the host. Missing, rejected or unreachable keys do not block opening Settings. To replace the key while keeping runtime data, edit the file and run `./bac start --keep-data`.

Startup installs a Git clean filter that stages an empty `api.cfg` while preserving its local contents. If editing the key before the first start, run `bash scripts/setup-key-filter.sh` first. Release packages contain an empty placeholder.

## Location, Telegram and Reset

**Location** sets the default city, initially Zurich. Explicit locations in a task or event brief take precedence. Saving updates the managed location for hired agents and every prepared specialist in both scenarios without changing memory, permissions or credentials.

**Telegram** sends new summaries from agents with the Tech Radar skill only. Ordinary chat and Multi-Agent results are not sent. See [Heartbeat and Telegram](heartbeat.md).

**Reset** offers Remove agents for Stages 1/2, separate Reset scenario buttons for Event Brief and Open Task from any room, and Reset all for both scenarios and hired agents. Model and connection settings remain. The Reset button beside Mission Control also clears only the selected scenario.

## Access and verification

Localhost and trusted-LAN visitors have the same controls. The server still checks browser sessions, agent ownership, request origins and CSRF tokens. The demo does not distinguish remote attendees from presenters. Model inference and OpenShell tool permissions are separate.

Provider-format, key isolation and connection checks use fixtures; rehearse tool calls with the actual target model. Focused checks:

```bash
python3 -B -m unittest discover -s tests -p test_model_connections.py
python3 -B -m unittest discover -s tests -p test_remote_settings.py
# Disposable server; run the browser scripts in another terminal:
python3 -B tests/fixture_scenarios.py
node tests/connection-editor-browser.cjs
node tests/remote-access-browser.cjs
```

Browser checks require Playwright and Chrome/Chromium. See [development and verification](development.md).

## Demo session cleanup

Only one browser session can use the demo at a time. Other browsers, private windows and devices show **The demo is already open** before creating a session or preparing agents. Tabs in the same browser at the same address share the existing session and agents; refreshes preserve them. Close all demo tabs in that browser, then select **Try again** in the new browser. A lost connection or browser crash releases access after 90 seconds without requests, once running work finishes. This access timeout does not delete data.

Each browser session owns its personal agents and its separate Stage 3 teams. Open tabs renew activity automatically. After 60 minutes without authenticated requests, the app cancels pending requests and scheduled follow-ups, then removes that session's agents, native runtime registrations, sandboxes, conversations and workspaces. Running tasks, artifact writes and policy updates finish before cleanup starts. Active browsers and their standby teams are unaffected.

Cleanup runs in the background, records completed targets, and resumes after partial failures or a server restart. A returning expired browser starts a new empty session; model requests are never replayed. Model connections and host settings are not part of session cleanup.

`./bac start` on the Docker deployment still starts fresh by default. `./bac start --keep-data` and the Mac source preview preserve data on restart, giving saved browsers 60 minutes to reconnect; abandoned sessions are then retired. The Mac preview runs `./bac dev preview` (or `scripts/serve.py`), so it does not execute Docker's fresh-start reset.

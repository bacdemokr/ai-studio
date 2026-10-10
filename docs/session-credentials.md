# External credentials

Credential lifetime depends on how the key was supplied, not on the stage using it.

| Source | Lifetime | Available to |
| --- | --- | --- |
| Key entered in Settings | Current browser tab's credential lease | Stages using the shared External Endpoint |
| Validated NVIDIA key from `api.cfg` | Saved on the app host | All stages through the NVIDIA connection |
| Telegram bot token | Current browser tab's credential lease | That participant's Tech Radar delivery |
| Keyless local server | No credential needed | Stages using Local |

`./bac start` optionally validates `api.cfg` with model discovery and a small inference request. A valid key is stored at `$BAC_DATA_DIR/credentials/stage3.json` (directory mode 0700, file mode 0600). The filename is historical: this saved NVIDIA key can also supply Hiring and Lounge. Empty, rejected or unreachable credentials do not block opening Settings and are not saved. Use `./bac start --keep-data` when replacing the key while preserving runtime data.

The browser shows **API key verified · api.cfg** or the applicable saved-key status without returning the key itself. Keys entered in Settings are held in process memory, never in host settings, browser storage, jobs or OpenClaw configuration. Model, endpoint, context budget and stage choices are saved separately. Refreshing or closing the tab requires re-entry unless a valid host-saved NVIDIA key supplies the connection.

Each browser document has its own credential session. Authenticated activity renews a 90-second lease every 20 seconds. Teardown revokes the session; if that signal is lost, expiry prevents new calls and the five-second sweeper releases stored references. Another tab cannot reuse a session-only key by leaving its key field blank. Already submitted model calls can finish.

OpenClaw connects through a loopback proxy with a non-secret placeholder. The proxy adds the provider key, forwards supported API paths and streamed responses, and does not follow redirects or log credentials. Host-saved NVIDIA credentials survive browser refresh and preserving restarts; session-only credentials do not.

Startup removes legacy external keys from app-managed settings and OpenClaw configuration copies, and redacts discovered old key values in app-owned runtime logs/state. This does not revoke provider keys or erase copies outside the app. Internal gateway authentication tokens remain separate.

Scout uses keyless Parallel Search; no separate search API key is required. Telegram credentials never enter model prompts. See [Heartbeat and Telegram](heartbeat.md).

Verification: `tests/test_session_secrets.py` covers storage, proxy forwarding, expiry, isolation and migration using fake credentials. `tests/connection-editor-browser.cjs` covers saved-key reuse and provider changes with a disposable fixture.

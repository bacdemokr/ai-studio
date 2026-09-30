# External credentials

Stage 1/2 model API keys are held only in the app process memory. They are never written to host settings, OpenClaw model configuration, browser storage, or job payloads. Model, endpoint, context limit and event preferences remain persistent.

Stage 3 uses a host-persisted team credential at `BAC_DATA_DIR/credentials/stage3.json`, with directory mode 0700 and file mode 0600. Its connection survives tab refresh, lease expiry and restart. Only the server-side team proxy reads this key; it is never returned to the browser or placed in agent configuration or prompts. The Stage 3 setup form validates and replaces it. The session-only lifecycle below applies to Stage 1/2 and Telegram.

Connect model makes a fresh authenticated model-list request before replacing the saved connection. During verification the button shows Connecting; a failure keeps the typed key and model and displays the provider error. The password field clears only after successful connection, or when the dialog closes. This checks access to the selected model, without generating a response. Background availability checks cache success for 60 seconds and failure for five seconds; explicit Connect never reuses that cache.

Each loaded browser document has a random credential session ID. Authenticated requests bind it to the participant; another tab cannot retain a blank key from this session. A heartbeat every 20 seconds renews a 90-second lease. Page teardown (including refresh) revokes its credentials with a keepalive request. If that notification cannot arrive, expiry rejects new calls after 90 seconds and the five-second sweeper releases stored references. A closed session cannot be resurrected by a late save. A request already sent upstream can finish; this is not a remote request cancellation mechanism. Python cannot guarantee secure erasure of freed memory or OS swap.

OpenClaw connects to a loopback-only, ephemeral-port proxy using a non-secret `session-only` placeholder. The proxy looks up a valid in-memory credential, injects the upstream authentication header and forwards model responses, including SSE. It allows only recognized provider paths, does not follow redirects, does not log requests, and never returns upstream error bodies containing possible credentials. Real API keys do not enter OpenClaw, so its configuration copies and session stores cannot persist them. Saved gateway endpoints become unusable after an app restart until the model is reconnected.

At normal app startup the migration removes old external `apiKey` fields from app settings and OpenClaw JSON/config copies, drops prior Telegram credential files, and redacts discovered old key values from app-owned runtime logs and state copies. This does not revoke keys at the provider or erase copies outside this app. Internal generated gateway authentication tokens remain part of local runtime access control; they are not external API keys.

Persistent CLI search-key configuration is disabled. Public-URL reading still works without a search API key; a session-only search-provider integration is not implemented.

Checks: `test_session_secrets.py` covers disk absence, loopback forwarding with a fake upstream, expiry, isolation, teardown and migration. Settings browser checks verify refreshing requires the key again. No real provider key is used in these tests.

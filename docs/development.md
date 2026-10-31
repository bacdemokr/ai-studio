# Development and verification

## Branches and versions

Development stays on `preview/visitor-agent-teams`. Event snapshots and regional branches are separate:

- `bac/1023-kazakhstan`: frozen at `0e4dc58dbb8bb05a28559281ba3f8203210cec3f` (v0.2.3).
- `bac/1102-uae` and `bac/1109-korea`: event branches; visitor development does not update them automatically.
- `archive/event-brief-final-2026-10-15`: final Event Brief source before retirement.

Do not update event snapshots, other development branches, release tags or external mirrors without an explicit publication request. Change `VERSION` only when a new version is requested; publication alone does not bump it. After committing, rebuild so build information identifies the delivered source even if the version is unchanged.

For visitor development, use `git switch preview/visitor-agent-teams`, then `git pull --ff-only`. Use `./bac start --keep-data` to preserve rehearsal data; plain `./bac start` clears it. Do not switch or merge branches while a demo is running.

Promote a tested preview only after target-hardware rehearsal and review. A release tag can point to the approved commit on any branch; it does not require first merging to `main`. Tags preserve code, not runtime data. Keep published tags and event snapshots unchanged.

The normal installation path is the [Git + Docker setup](docker-setup.md). Host development is separate:

```bash
./bac dev setup
./bac dev preview
```

`./bac dev --help` lists advanced commands. `launch.sh` is a development shortcut for `./bac dev preview`. See [host Ubuntu setup](ubuntu-setup.md) or [managed Spark model](spark-operations.md) only for those development paths.

The source preview preserves data on restart; it does not run Docker's fresh-start reset. In both modes, [abandoned browser sessions are removed after 60 minutes](runtime-settings.md#demo-session-cleanup). A preserving restart gives browsers 60 minutes to reconnect. Use disposable fixtures for tests so test sessions never populate a presenter's runtime.

Edit `src/` and run `python3 -B scripts/build.py`; refresh for UI changes. Restart for Python changes. Do not edit generated `app/index.html` directly. Docker installations load changed source files with `./bac start --keep-data` when preserving runtime data.

## Tests

```bash
PYTHONPATH=scripts:tests python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Tests use temporary state and model adapters. Browser tests require Playwright and Chrome/Chromium. Use a separate fixture server, never live demo data:

```bash
# Terminal 1
BAC_TEST_PORT=8094 python3 -B tests/fixture_settings.py
# Terminal 2 (set CHROME_PATH if needed)
BASE_URL=http://127.0.0.1:8094 node tests/overview-entry.cjs
BAC_TEST_URL=http://127.0.0.1:8094 node tests/async-interactions.cjs
BAC_TEST_URL=http://127.0.0.1:8094 node tests/agent-reset.cjs
```

For shared connections and the current Settings dialog:

```bash
# Separate terminal
python3 -B tests/fixture_scenarios.py
# Browser checks
node tests/settings.cjs
node tests/connection-editor-browser.cjs
node tests/runtime-readiness.cjs
BAC_TEST_URL=http://127.0.0.1:8083 node tests/settings-resilience.cjs
```

Test URL variables differ in older browser scripts; inspect each before running it. Infrastructure checks and deterministic fixtures do not establish real model quality or Spark performance. Rehearse a personal task and a complete Open Task on the target PC/model. [OpenShell verification](openshell-verification.md) covers real sandbox scenarios.

Browser admission and expired-session recovery use a separate disposable fixture:

```bash
python3 -B tests/fixture_session_cleanup.py
# In another terminal; optional BAC_TEST_LAN_URL checks a private host address too.
node tests/browser-access.cjs
node tests/session-cleanup-browser.cjs
```

The UI sends a per-tab browser-view ID; the server admits one participant before creating its session state. All marked API requests renew/check access, and closing a tab releases only that view. Late requests from a closed view receive HTTP 410 and cannot reclaim the slot. Non-UI API clients (including host connection helpers) keep their existing authentication and do not occupy a browser slot. This is a duplicate-demo guard, not a security boundary. Simulated multi-participant tests should use their API clients or close one browser before opening the next. For consecutive browser tests, use fresh fixture processes or navigate the owning pages away before closing the browser; killing the browser can leave its 90-second grace period active.

Team creation registers its identities and writes the initial workspace definitions within the same transaction that guards session retirement. A failed setup rolls back its newly allocated directories; a retiring session cannot hire agents or create another team. `tests/test_crew_ownership.py` and `tests/test_session_cleanup.py` cover initialization failures and overlapping cleanup.

## Optional browser installation

Playwright automates browser checks on Windows, Linux and macOS. It is a development dependency only: BaC, its Docker services and the movable information windows run normally without Playwright, Node.js on the host, or any Playwright-managed browser. In a source checkout, `./bac start` reports when the optional local Playwright package is absent but does not delay or block startup.

To prepare Chromium, Firefox and Microsoft Edge for tests, run from the repository root:

```bash
npm install --save-dev playwright
npx playwright install chromium firefox msedge
```

On supported Linux systems, Playwright can install the required OS libraries too:

```bash
npx playwright install --with-deps chromium firefox msedge
```

Microsoft Edge availability depends on the operating system and CPU architecture; it may not be available on ARM64 Linux systems such as DGX Spark. Installing a browser does not automatically run every test against it: tests launch Chromium with `chromium.launch()`, Edge with `chromium.launch({channel: 'msedge'})`, or Firefox with `firefox.launch()`. Do not add Playwright to `docker/runtime/package.json`, which contains production runtime dependencies.

## Exploratory rehearsal

For the visitor branch, also use the [visitor-team regression checklist](visitor-regression.md). It covers both current team modes, per-hire models, role-or-skill suitability, explicit participants and the five in-app example goals. Use affected tests for focused maintenance; a full exploratory rehearsal is a separate step, with model and target-host coverage recorded explicitly.

For stability work, test complete journeys as well as individual fixes: first use, mixed skills, repeated questions, simultaneous Heartbeat and foreground work, connection loss/recovery, cancellation/reset, agent switching, and localhost versus LAN HTTP. Inspect the actual outputs and recovery, not just Ready indicators.

Use disposable participants or fixture data for destructive tests. Record which checks used real model responses, simulated endpoints or target Spark hardware. A Mac/API run does not establish local Spark performance.

Focused resilience coverage: `tests/test_lounge_resilience.py`, `tests/test_runtime_startup.py` and `tests/agent-switching-browser.cjs`. The browser switching test uses `tests/fixture_heartbeat.py`; pass its URL through `BASE_URL`.

## Twelve-agent scenarios

`tests/test_twelve_agents.py` exercises a full collection: concurrent hiring and chat,
policy isolation, location changes across 60 workspaces, restart recovery, deletion,
Heartbeat delivery and slow Telegram. Native services, model responses and Telegram
are simulated; application logic, SQLite and workspace files are real.

```bash
PYTHONPATH=scripts:tests python3 -B -m unittest discover -s tests -p test_twelve_agents.py
node tests/comparison-capacity.cjs
# Separate terminal; disposable HTTP server, no live demo data:
python3 -B tests/fixture_twelve_agents.py
# Requires Playwright. Set CHROME_PATH to your Chrome/Chromium executable:
BASE_URL=http://127.0.0.1:8092 node tests/twelve-agents-browser.cjs
```

The browser test creates 12 agents, checks the 3D lounge and selection, then sends
one question to all 12 through the real HTTP queue. Requests wait for one of the
three collection slots; rejected quota requests are retried, uncertain network
failures are not. This is a functional capacity test, not a real-model load benchmark.

## Heartbeat tests

`tests/test_tech_radar.py` covers unread article selection, feed caching/failures, deduplication, pause/resume, tenant isolation, failed delivery and session credentials. For UI testing, run `python3 -B tests/fixture_heartbeat.py`, then `BASE_URL=http://127.0.0.1:8087 node tests/heartbeat-browser.cjs` with Playwright. This fixture sends no external messages.

`python3 -B tests/heartbeat_protocol.py /path/to/bac-data/openclaw` uses the installed pinned runtime read-only with temporary configuration and random ports. It waits for a real 20-second native heartbeat and tests exec/read/write flow using a deterministic protocol fixture, not a real model. It does not touch the live gateway. Real-model summary quality and delivery to a real Telegram chat require a separate rehearsal.

## Retired code and compatibility

The active app does not ship the old Event Brief page renderer or its frontend-only handoff/social-draft tests. The archive branch retains that workflow. Keep stable role indexes, retired-route responses and migrations for old data and credentials: they support safe upgrades, ownership and cleanup. Current Open Task trace and handoff tests cover the active workflow.

## Further reference

For the hired-agent exec contract, run `node tests/visitor-exec-native.mjs /path/to/openclaw/package/node_modules/openclaw`. This uses the installed pinned tool with an isolated empty configuration and one harmless local command; it does not call a model or validate OpenShell enforcement. `node tests/visitor-protection-browser.cjs` checks Open Task policy feedback with injected native-log events and isolated demo data.

- [Architecture and responsibility boundaries](architecture.md)
- [Live runtime and workflow](live-studio.md)
- [Model and location settings](runtime-settings.md)
- [Credential storage](session-credentials.md)
- [Personal skills and persona formats](personal-agent-skills.md)
- [Telemetry](telemetry.md)

Historical prototype screenshots and design notes are not shipped as current documentation. Compatibility readers for saved jobs and policies remain intentional; they preserve existing data.

## Deferred discussion

Follow-up requests that revise a previously completed deliverable will be discussed separately. Existing behavior remains in place; repeated edits, handoff reuse and producer changes need a dedicated end-to-end review before stronger reliability claims. This is distinct from Casey’s single bounded repair within an active goal.

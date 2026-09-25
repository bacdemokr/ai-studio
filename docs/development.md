# Development and verification

## Branches and versions

- `main`: the stable demo used by normal installations.
- `v0.1`: a fixed tag for the baseline before Stage 3 OpenShell work. Keep released tags unchanged.
- `dev`: integrated development and testing, including Stage 3 OpenShell protection, connection visualization, Tech Radar, Telegram and Arxivbot.
- `heartbeat`: the original feature branch, now merged into `dev`. Continue development on `dev`.

For development, switch once with `git switch dev`, then use `git pull --ff-only` and `./bac start`. Normal users stay on `main`.

Merge `dev` into `main` through a reviewed GitLab merge request after relevant tests and a live demo rehearsal pass. Create a new version tag on `main` for each release. A tag preserves code, not a backup of application data.

The normal installation path is the [Git + Docker setup](docker-setup.md). Host development is separate:

```bash
./bac dev setup
./bac dev preview
```

`./bac dev --help` lists advanced commands. `launch.sh` is a development shortcut for `./bac dev preview`. See [host Ubuntu setup](ubuntu-setup.md) or [managed Spark model](spark-operations.md) only for those development paths.

Edit `src/` and run `python3 -B scripts/build.py`; refresh for UI changes. Restart for Python changes. Do not edit generated `app/index.html` directly. Docker installations load changed source files with `./bac start`.

## Tests

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Tests use temporary state and model adapters. Browser tests require Playwright and Chrome/Chromium. Use a separate fixture server, never live demo data:

```bash
# Terminal 1
BAC_TEST_PORT=8094 python3 -B tests/fixture_settings.py
# Terminal 2 (set CHROME_PATH if needed)
BASE_URL=http://127.0.0.1:8094 node tests/settings.cjs
BASE_URL=http://127.0.0.1:8094 node tests/overview-entry.cjs
BAC_TEST_URL=http://127.0.0.1:8094 node tests/async-interactions.cjs
BAC_TEST_URL=http://127.0.0.1:8094 node tests/agent-reset.cjs
```

Test URL variables differ in older browser scripts; inspect each before running it. Infrastructure checks and deterministic fixtures do not establish real model quality or Spark performance. Rehearse a personal task and a complete event on the target PC/model. [OpenShell verification](openshell-verification.md) covers real sandbox scenarios.

## Twelve-agent scenarios

`tests/test_twelve_agents.py` exercises a full collection: concurrent hiring and chat,
policy isolation, location changes across 60 workspaces, restart recovery, deletion,
Heartbeat delivery and slow Telegram. Native services, model responses and Telegram
are simulated; application logic, SQLite and workspace files are real.

```bash
python3 -B -m unittest discover -s tests -p test_twelve_agents.py
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

`python3 -B tests/heartbeat_protocol.py /path/to/bac-data/openclaw` uses the installed pinned runtime read-only with temporary configuration and random ports. It waits for a real 30-second native heartbeat and tests exec/read/write flow using a deterministic protocol fixture, not a real model. It does not touch the live gateway. Real-model summary quality and delivery to a real Telegram chat require a separate rehearsal.

## Further reference

- [Architecture and responsibility boundaries](architecture.md)
- [Live runtime and workflow](live-studio.md)
- [Model and location settings](runtime-settings.md)
- [Credential storage](session-credentials.md)
- [Personal skills and persona formats](personal-agent-skills.md)
- [Telemetry](telemetry.md)

Historical prototype screenshots and design notes are not shipped as current documentation. Compatibility readers for saved jobs and policies remain intentional; they preserve existing data.

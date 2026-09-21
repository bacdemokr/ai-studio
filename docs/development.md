# Development and verification

The normal installation path is the [Git + Docker setup](docker-setup.md). Host development is separate:

```bash
./bac dev setup
./bac dev preview
```

`./bac dev --help` lists advanced commands. `start.sh` is a compatibility alias for `./bac dev preview`. See [host Ubuntu setup](ubuntu-setup.md) or [managed Spark model](spark-operations.md) only for those development paths.

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

## Further reference

- [Architecture and responsibility boundaries](architecture.md)
- [Live runtime and workflow](live-studio.md)
- [Model and location settings](runtime-settings.md)
- [Credential storage](session-credentials.md)
- [Personal skills and persona formats](personal-agent-skills.md)
- [Telemetry](telemetry.md)

Historical prototype screenshots and design notes are not shipped as current documentation. Compatibility readers for saved jobs and policies remain intentional; they preserve existing data.

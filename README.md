# BaC Crew

An interactive prototype for planning a Build a Claw event with a crew of agents. Switch between **A · Crew village** and **C · Progress board**, inspect each persona and skill set, and build your own agent.

**Current status:** working browser UI with deterministic, simulated agent handoffs and an OpenShell approval example. The village is currently a CSS illustration. Real 3D, LLM inference, agent orchestration, OpenShell enforcement and email delivery are not connected yet.

## Run on DGX Spark

Requires Git, Python 3.8+ and a current Chrome, Edge or Firefox browser. No pip packages, Node.js, GPU drivers or model downloads are needed for this prototype.

```bash
git clone https://github.com/bacdemokr/tmp.git
cd tmp
./start.sh
```

Open **http://localhost:8080** in a browser on Spark. For a private repository, authenticate Git on Spark before cloning, or download the repository ZIP while signed into GitHub.

If you use Spark remotely, keep the server running and create a tunnel from your laptop:

```bash
ssh -N -L 8080:127.0.0.1:8080 YOUR_SPARK_USER@YOUR_SPARK_HOST
```

Then open **http://localhost:8080** on your laptop. To make the UI available directly on a trusted local network instead:

```bash
./start.sh --host 0.0.0.0 --port 8080
```

Open `http://SPARK_IP:8080`. This development server has no authentication. Stop it with Ctrl+C. Use `--port 8081` if port 8080 is occupied. The generated `app/index.html` also works directly as a local file.

## Try the demo

1. Keep **Europe (EMEA) / Zurich / English**, or change the event brief. Defaults are 120 attendees, 180 minutes, groups of 5 and 15-minute sessions.
2. Submit the brief and advance the handoffs. Each attendee is assigned to one interest-based topic.
3. Compare A and C. Both show the same crew and shared brief version.
4. Operations detects a device shortage. Extend the event to **210 minutes** or mark additional devices as pending.
5. Inspect demo runbooks, equipment/staffing calculations, invitation copy, promotional copy and the consistency review.
6. Approve or deny the simulated policy request. Neither option sends a message or performs an external action.
7. Select **Build your agent**, choose a name, role, persona and skills, try a solo task, then join the crew. This replaces the existing agent in the selected role.

The interface is English. Generated template examples support English, Korean and Japanese. Inputs stay in browser memory; refreshing resets the demo. Venue details, event dates and registration links remain placeholders.

## Equipment planning

The default topic split is 50% / 30% / 20%. These are editable planning assumptions, not measured GPU throughput or official hardware sizing guidance.

| Default brief | Spark stations | Workstations | Staff |
|---|---:|---:|---:|
| 120 attendees, 180 minutes | 3 | 1 | 8 |
| Same brief, extended to 210 minutes | 2 | 1 | 7 |

Staff includes one presenter per station, one floor assistant per 40 attendees (rounded up), and one event lead. Open **Calculations and assumptions** for the formulas. The hardware counts describe equipment at the planned event; they are independent of the single Spark hosting this demo.

## Project files

- `src/bac-planner.html`: editable UI, styles, planning rules and simulated workflow.
- `scripts/build.py`: creates a standalone page without CDN or Codex dependencies.
- `app/index.html`: generated runnable page; committed for convenient preview.
- `start.sh` / `scripts/serve.py`: local server using only Python's standard library.
- `docs/architecture.md`: current behavior and the intended live integration.
- `tests/smoke.cjs`: optional browser smoke test.

After editing `src/bac-planner.html`, run `python3 scripts/build.py` or restart `./start.sh`, then refresh the browser.

## Optional browser validation

The application does not need these dependencies. Install them only to run the smoke test:

```bash
npm install --no-save --package-lock=false playwright
npx playwright install chromium
node tests/smoke.cjs
```

On Linux, Playwright may also require OS browser libraries (`npx playwright install-deps chromium`). Alternatively set `CHROME_PATH` to an existing Chrome/Chromium executable.

The prototype was validated on macOS Chromium, including the full workflow, both policy choices, onboarding and small-screen layouts. DGX Spark hardware execution has not yet been verified.

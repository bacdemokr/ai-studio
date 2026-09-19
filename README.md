# NVIDIA Build a Claw — Agent Studio

Create your own agents, give each useful skills, and choose who joins your crew. The NVIDIA-inspired dark interface surrounds a miniature 3D workshop: five robot specialists work at distinct desks around one shared brief. Active workbenches light up and document packets illustrate observed handoffs. Small buttons on the library, maker desk, weather instrument and shared brief open the actual experiences. Switch between **Agent campus** and **Mission control**, or expand the world without changing the rest of the interface.

![Agent Studio](docs/agent-studio.png)

[Preview: your agent collection](docs/agent-collection.png)

## What is implemented

- **My agents:** create and switch between up to 12 personal agents per browser session. Each has its own name, persona, skills, conversation, memory, files and mission board. The selected agent survives a page reload in the same tab.
- **Persistent onboarding:** name, persona and editable skill loadout; native OpenClaw identity/skill files are provisioned on the first mission. Memory, conversations, files and jobs survive app updates.
- **Useful solo missions:** live weather, reading public websites, optional Brave web search, document questions, HTML mini-app creation with an isolated playable preview, campaign drafts and explicit preference memory.
- **A real crew workflow:** your selected agent leads four specialists. Assign any of your other agents to demo production, operations, marketing or review; unfilled slots use Nova, Atlas, Momo and Pico. The workshop has five role stations, independently of your collection size. Separate OpenClaw agents receive a shared brief and previous deliverables; the reviewer checks the specialists. A real server-side decision stops the workflow if equipment is insufficient.
- **Visible evidence:** observed task states, role handoffs and actual saved files drive the scene and board. Character motion illustrates those states; it is not a model reasoning trace.
- **Phone continuity:** optional Telegram pairing routes a participant’s private messages to the same OpenClaw agent and conversation as the web. Pairing tokens expire and can only be used once. Switching agents in the browser does not reroute a paired phone. Pairing a different agent moves that private chat to the newly paired agent.
- **Persistent follow-ups:** scheduled jobs survive refresh/restart and run through the same queue. Results appear in the web workspace. This is the BaC scheduler, not OpenClaw cron.
- **Attendee controls:** stop after the active model call, reset your mission board while preserving memory/files, deliberate retry, labeled fallbacks and an evidence download for your facilitator.
- **Inspectable handoffs:** open each role’s shared inputs, prior deliverables, fingerprints and output files; download the selected mission’s evidence.
- **OpenShell Security lab:** an illustrative boundary walkthrough plus separately labeled host evidence. `./bac openshell prove` collects deny → narrow permission → allow → still-deny evidence in a dedicated temporary sandbox. This does not certify every agent’s traffic. See the [requirements and acceptance checklist](docs/cohort-requirements.md).
- **Cohort routing:** “Find your next demo” explains this Studio’s focus and the supplied NeMoReef brief’s persistent-work and policy/recovery focus.

All roles use **one shared `bac-local` model on one Spark**. Requests run sequentially to avoid loading a model per agent. This demonstrates role boundaries, dependencies and review; it does not claim a parallel speedup.

The separate **Local tools & samples** and **Workflow rehearsal** tabs retain the previous offline examples, real browser CSV analysis and downloadable poster generation. Those sample weather/search/Telegram responses remain explicitly fictional. The main Agent Studio never substitutes a sample answer for a failed live request.

## First setup on Spark

Clone this private repository using your authenticated Git account:

```bash
git clone https://github.com/bacdemokr/tmp.git
cd tmp
./bac llm setup qwen
./bac llm start qwen
./bac llm check
./bac runtime setup
./bac runtime start
./bac runtime check
./bac app start
```

Open **http://localhost:8080**. `runtime setup` installs a private Node.js 24.16.0 and OpenClaw 2026.9.4; it does not change system Node. For another model, install `gemma` once and use `./bac llm start gemma`. This switches the shared endpoint for every agent.

For remote access, keep the app bound to loopback and forward port 8080 from your laptop:

```bash
ssh -N -L 8080:127.0.0.1:8080 YOUR_SPARK_USER@YOUR_SPARK_HOST
```

For a trusted workshop LAN, use `./bac app start --host 0.0.0.0`. This is a workshop server with browser-session isolation, **not an authenticated public service**. Keep the OpenClaw gateway and vLLM ports on loopback.

## Repeated review and cleanup

```bash
./bac update                     # update the app, preserve model/runtime/user data
./bac rollback                   # return to the previous app release
./bac llm remove qwen --yes       # remove only Qwen weights
./bac llm remove gemma --yes      # remove only Gemma weights
./bac llm remove-runtime --yes    # remove the managed vLLM environment
```

Model removal supports a preview by omitting `--yes`. Runtime setup is independent from app releases; `./bac update` does not reinstall OpenClaw or restart the model. [Full Spark operations](docs/spark-operations.md).

Optional integrations:

```bash
./bac telegram configure         # hidden prompt for a dedicated bot token
./bac search configure           # hidden prompt for a Brave Search API key
./bac openshell enable           # requires an installed OpenShell CLI and active gateway
./bac openshell check
./bac openshell prove            # optional fixed network probes in a separate temporary sandbox
```

Website reading and the weather endpoint do not require a Brave key. Telegram uses the BaC transport adapter into OpenClaw, not a claim of native Telegram-channel configuration.

## Review the interface without a model

```bash
./start.sh
```

Only Python 3.9+ and a modern WebGL2 browser are needed for UI review. The runtime indicator stays offline, onboarding is saved, and live missions explain the setup requirement. Local CSV/poster tools and the explicit workflow rehearsal remain usable. Use the server rather than opening `app/index.html` as a file for Agent Studio functionality.

## A 15-minute attendee journey

1. Name an agent and choose its persona/skills.
2. Click **Maker workshop**, create a mini game and play the actual generated file.
3. Ask it to remember a preference. Refresh, then ask what it remembers.
4. Open **Knowledge library**, upload a document or use the labeled sample brief, and inspect the answer alongside the source.
5. Use **Create an agent** to make a second teammate with different skills. Switch between them to see separate memory and workspaces. Assign your teammates when launching a crew for **Zurich / Europe / English**. Defaults: 120 attendees, 180 minutes, groups of 5, sessions of 15 minutes; all are editable.
6. Watch role handoffs in the campus, switch to Mission control, approve the equipment assumption if needed, and open each deliverable.
7. If the host configured Telegram, pair a phone and continue the same conversation.
8. Open **Security lab** to explore the boundary, then use **Find your next demo** for the NeMoReef learning path. Open **Help & fallback** when a live dependency is unavailable.

Dates, venues and registration URLs stay unconfirmed unless supplied. Equipment counts are transparent event-station assumptions, not an inference-capacity benchmark. See the [presenter runbook](docs/demo-runbook.md).

## Validation and limits

The collection limit is 12 personal agents per attendee; a crew mission has five distinct roles. Attendees share a limit of three pending missions across their collection, and the server executes one task at a time on the shared model. Crew assignment does not add tools to an agent’s skill loadout. Crew inputs and outputs are shared explicitly, while the combined package stays in the lead’s workspace. A specialist assigned to a pending crew has a shortcut back to that crew’s board. The update migrates existing single-agent state in place, preserving native identity, memory, files, phone pairing and board history.

The pinned **real OpenClaw gateway** was installed and tested locally with a clearly identified protocol fixture as its model: native agent registration (including immediate first use), write/read tools, persistent memory, HTTP conversation continuity and the complete five-role crew workflow worked. Python and browser tests cover lifecycle/update isolation, participant and agent boundaries, multi-agent creation/switching, custom crew assignments, migration, scheduling, equipment approvals, file handling, onboarding and 3D controls. Collection and custom-assignment tests use explicit adapter/browser fixtures; Spark inference still needs host verification. Fixtures are test-only and never loaded by the production app.

**Still requires Spark verification:** Qwen/Gemma inference quality and latency, actual NVIDIA GPU setup, real Telegram credentials, Brave credentials and OpenShell sandbox enforcement. No live Telegram message or promotional email was sent during development.

```bash
python3 -m unittest discover -s tests -p 'test*.py'
# Optional browser tests; requires Playwright + Chromium, or CHROME_PATH
python3 tests/fixture_studio.py   # separate terminal, port 8082
node tests/studio.cjs
node tests/smoke.cjs
node tests/playground.cjs
node tests/campus.cjs
```

## Editable source

- `src/studio.*`: attendee journey, mission control and API client.
- `src/world-scene.js`, `src/campus.*`: Three.js world, characters and accessible hotspots.
- `scripts/studio.py`, `scripts/serve.py`: durable queue, participant API, shared crew state.
- `scripts/agent_runtime.py`: native OpenClaw workspaces and gateway adapter.
- `scripts/ops_runtime.py`: pinned runtime, optional search, Telegram and OpenShell setup.
- `scripts/telegram_bridge.py`: private-chat pairing and transport continuity.
- `src/studio-safety.js`, `scripts/security_lab.py`: attendee controls, cohort routing and operator-only OpenShell evidence capture.
- `src/playground.*`, `src/skill-tools.js`, `src/bac-planner.html`: local tools and explicitly scripted rehearsals.
- `scripts/build.py`: rebuilds the bundled UI, with no runtime CDN requirement.

After UI changes: `python3 scripts/build.py`. All mutable state lives outside the checkout under `~/.local/share/bac-demo` (or `BAC_DATA_DIR`). Keep that directory private and do not commit or share it.

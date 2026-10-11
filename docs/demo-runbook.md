# Presenter runbook

## Before the demo

Use the intended branch on the target PC. This guide describes `preview/stage3-scenarios`; the Zurich snapshot has different controls.

1. For local inference, start the installed model with `./bac vllm`, or use an already-running compatible server.
2. Run `./bac start` for a clean demo, or `./bac start --keep-data` to retain agents and rehearsals. Studio does not start the model server automatically.
3. Open `http://localhost:8080` on the host or `http://SPARK_IP:8080` over the trusted LAN. Both provide Settings and the same demo controls.
4. In **Settings → Model**, configure Local and/or External Endpoint. A validated `api.cfg` supplies NVIDIA automatically; the file is optional.
5. Hired agents default to Local when connected; choose another model in Hiring or Edit agent. Under **Models**, select **Event Brief** and **Open Task** connections separately. Automatic prefers External; saved choices remain in effect.

Rehearse the selected tasks on the actual model and hardware. Use **Full screen** for presenting. Identify saved results as previous runs.

## 1 / 2. Hiring and Agent lounge

Let the audience choose a character, tone, role and skills. The editable prompt is the saved tone and role; **Apply prompt & suggest skills** selects matching skills for the user to adjust.

- **Instructions:** read or copy AGENTS.md, IDENTITY.md and SOUL.md side by side. Click the agent name or portrait for the full saved-file viewer, including skills and memory.
- **Files:** appears only when the selected agent has uploads or results. Open a file to preview or download it. Definition files use Copy instead of Download.
- **OpenShell Policy:** approve a blocked website, then resend the request. DNS or source failures are not fixed by granting more permissions. Rehearse actual enforcement on the demo host.

For manual chat, try a short document, weather or research request. Supported document formats are PDF, PPTX, XLSX, TXT, Markdown and CSV, up to 10 MB per file. Documents stay with the selected agent.

For autonomous behavior, equip **Tech Radar**. The first check waits at least 20 seconds; later checks follow the same cadence. Model work or runtime preparation can delay a summary. Chat, attachments and scheduled tasks stay disabled while this skill is equipped, even alongside other skills or while paused. Use **Pause / Resume**, or remove the skill to restore chat. Telegram sends only these summaries.

## 3-1. Event Brief

Riley coordinates Dylan (demo research), Alex (operations) and Morgan (event page and social draft). All use the connection model chosen for Event Brief.

Open **Plan an event**, enter the brief and choose the crew. Riley is required. **Prepare demo** checks the selected agents; once ready, **Give the brief to my crew** launches the event. Watch **Mission Control**, then inspect **Results** and the saved deliverables.

For an offline rehearsal, select Local and omit Dylan's live research, using Riley, Alex and Morgan. Rehearse this exact selection on the Spark beforehand. Fresh web research, live weather and Telegram still need internet access.

## 3-2. Open Task

Casey answers directly or selects up to three specialists:

| Specialist | Contribution |
| --- | --- |
| Scout | Public web research |
| Ada | Supplied-data analysis |
| Iris | Interface design |
| Cody | Webpages and small code prototypes |
| Vera | Independent review |

With NVIDIA, expand **Standby specialists** and click a model beside an agent to change it. Local and other providers use the shared connection model. **Models & connection** opens Settings.

Start with `/goal` in Casey's chat (`/plan` remains an alias). For example, attach a table and send:

```text
/goal Analyze this table and summarize the three most important findings.
Add an independent review of the calculations and conclusions before finishing.
```

Or try a compact coding request:

```text
/goal Build a self-contained desktop HTML savings calculator. Include amount,
interest rate and years, validate the inputs, and show the estimated total.
```

Use **Mission Control** for assignments and handoffs, **Results** for the answer and files, and **Usage & time** for recorded tokens and elapsed time. Agent time includes tools; parallel turns may sum to more than elapsed time. These are recorded responses, not provider billing totals.

Requested independent review must finish before the task can be complete. Reviews are static unless actual execution evidence exists. Open Task allows one shared recovery/repair attempt; incomplete work stays marked partial. Personal reactions from hired agents are opinions, not independent reviews.

## Recovery and cleanup

- **Waiting for model:** check that the selected connection is enabled and ready. **Waiting for runtime:** check OpenClaw. **Waiting for other agents:** foreground work is delaying Heartbeat.
- **Partial result:** inspect saved work and the error before retrying. A new request can repeat writes. Neither a saved file nor its preview proves correctness.
- **Context/output errors:** context defaults to 32K; output is capped at 16K per response and reduced for smaller contexts. These are demo settings, not a universal model limit. Narrow broad requests and keep inputs compact; see [model settings](runtime-settings.md#context-and-output-budgets).
- **Reset scenario:** stops and clears only the selected Stage 3 scenario. **Remove agents:** removes hired agents and their data. **Reset all:** clears both scenarios and hired agents. Model settings remain. Empty resets are disabled.
- `./bac stop` stops the app and preserves data. `./bac stop --all` also stops its managed model and removes the Compose stack and data volumes. Model weights remain.

[Example scenarios](../README_POSSIBLESCENARIOS.md) · [Installation and recovery](docker-setup.md) · [Model settings](runtime-settings.md)

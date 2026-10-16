# Presenter runbook

## Before the demo

Use the intended branch on the target PC. This guide describes `preview/visitor-agent-teams`; `preview/stage3-scenarios` and the Zurich snapshot have different Open Task controls.

1. For local inference, start the installed model with `./bac vllm`, or use an already-running compatible server.
2. Run `./bac start` for a clean demo, or `./bac start --keep-data` to retain agents and rehearsals. Studio does not start the model server automatically.
3. Open `http://localhost:8080` on the host or `http://SPARK_IP:8080` over the trusted LAN. Both provide Settings and the same demo controls.
4. In **Settings → Model**, configure Local and/or External Endpoint. A validated `api.cfg` supplies NVIDIA automatically; the file is optional.
5. Hired agents default to connected Local, otherwise the configured External Endpoint model; choose another model in Hiring or Edit agent. Under **Models**, select the **Open Task** connection. The selector shows the connection currently used; saved choices remain in effect.

Rehearse the selected tasks on the actual model and hardware. Use **Fullscreen** for presenting. Identify saved results as previous runs.

## 1 / 2. Hiring and Agent lounge

Let the audience choose a character, tone, role and skills. Use **How does an agent work?** for the component diagram and each skill’s **i** for its source instructions. The editable prompt is the saved tone and role; **Apply prompt & suggest skills** selects matching skills for the user to adjust.

- **Instructions:** read or copy AGENTS.md, IDENTITY.md and SOUL.md side by side. Click the agent name or portrait for the full saved-file viewer, including skills and memory.
- **Files:** appears only when the selected agent has uploads or results. Open a file to preview or download it. Definition files use Copy instead of Download.
- **OpenShell Policy:** approve a blocked website, then resend the request. DNS or source failures are not fixed by granting more permissions. Rehearse actual enforcement on the demo host.

For manual chat, try a short document, weather or research request. Supported document formats are PDF, PPTX, XLSX, TXT, Markdown and CSV, up to 10 MB per file. Documents stay with the selected agent.

For autonomous behavior, equip **Tech Radar**. The first check waits at least 10 seconds; later checks run every 20 seconds. Model work or runtime preparation can delay a summary. Chat, attachments and scheduled tasks stay disabled while this skill is equipped, even alongside other skills or while paused. Use **Pause / Resume**, or remove the skill to restore chat. Telegram sends only these summaries.

## 3. Open Task

Casey coordinates up to three specialists. Select a team before sending `/goal`:

- **Hired only** (default): at least one available hired agent is needed. Any role can participate; Casey matches the equipped skills, then checks permitted tools. Explicit names do not override a mismatch.
- **Hired + Standby**: Casey can also use the backups below, even if no agents have been hired.

Name an agent to request its participation when its equipped skills fit. If neither fits, Casey explains the missing expertise rather than forcing the assignment. A Programmer and Web researcher are a useful research-and-build pairing, not mandatory roles. Missing tools remain a limitation; an assignment does not grant new permissions.

Idle hires follow you into the room and wait on benches. Assigned agents move to workbenches; movement alone does not run a model. The built-in backups are:

| Specialist | Contribution |
| --- | --- |
| Scout | Public web research |
| Ada | Supplied-data analysis |
| Iris | Interface design |
| Cody | Webpages and small code prototypes |
| Vera | Independent review |

Change an idle hired agent’s model by clicking its model badge. Hires retain their model, identity and policy in either mode. On NVIDIA, **Hired + Standby → Standby specialists** lists Casey and the backups with editable model choices. Return to Hired only before starting if that is your intended team. Local and other providers use the shared Open Task model for Casey and backups. **Models & connection** opens Settings.

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

Independent review needs a different agent from the producer. In Hired only, hire a second suitable agent if you request this. Requested independent review must finish before the task can be complete. Reviews are static unless actual execution evidence exists. Open Task allows one shared recovery/repair attempt; incomplete work stays marked partial. Personal reactions from hired agents are opinions, not independent reviews.

The team choice is locked during work. Changing it after completion retains previous results; Reset Open Task first for a clean rehearsal. Reload and reset default new tasks to Hired only.

## Recovery and cleanup

- **Waiting for model:** check that the selected connection is enabled and ready. **Waiting for runtime:** check OpenClaw. **Waiting for other agents:** foreground work is delaying Heartbeat.
- **Partial result:** inspect saved work and the error before retrying. A new request can repeat writes. Neither a saved file nor its preview proves correctness.
- **Context/output errors:** context defaults to 32K; output is capped at 16K per response and reduced for smaller contexts. These are demo settings, not a universal model limit. Narrow broad requests and keep inputs compact; see [model settings](runtime-settings.md#context-and-output-budgets).
- **Reset Open Task:** stops and clears team work. **Remove agents:** removes hired agents and their data. **Reset all:** clears Open Task and hired agents. Model settings remain. Empty resets are disabled.
- `./bac stop` stops the app and preserves data. `./bac stop --all` also stops its managed model and resets the Compose stack, application data, and OpenShell policies. Model weights remain.

- **Connection lost after a contribution:** saved files remain available as a partial result. Restore the connection before asking Casey to continue; completed work is not automatically repeated.

[Example scenarios](../README_POSSIBLESCENARIOS.md) · [Installation and recovery](docker-setup.md) · [Model settings](runtime-settings.md) · [Visitor regression checklist](visitor-regression.md)

## Presenter shortcuts and build identity

- Click an **Example goals** chip below Casey’s introduction for one of five editable examples. The store example attaches BB’s fictional email. Selection does not send a request or change the team mode.
- In Casey’s chat or **Mission Control**, explain **Why this agent** and any **Not assigned** reasons. Scene bubbles only announce brief progress.
- Use **Settings → Reset → Issue report → Copy diagnostics** when reporting a problem. Note whether the report says Local changes.
- For OpenShell, expand **How OpenShell protection works** in Hiring. The nested runtime command is illustrative: the adapter selects `--detach -- sleep infinity` only when advertised, otherwise `-- true`. Show the actual policy decision and approval flow in the Lounge.
- Include Heartbeat in Stage 2: Tech Radar checks automatically, may wait for runtime capacity, and should not claim a result without retrieved evidence.

For an issue report, reproduce once, then use **Settings → Reset → Issue report → Copy diagnostics**. Include the steps and approximate time. Download provides a larger bounded report. See [diagnostics](diagnostics.md); do not attach raw gateway logs or the workspace database by default.


## OpenShell in the Lounge

Use a protected Web researcher and send a normal chat request, such as “Read https://example.com.” Role, skills and tool restrictions still apply.

1. With no website grant, inspect the actual blocked request in **OpenShell Policy**.
2. Approve `example.com` and resend the request. **Recent activity** identifies the destination, request method when available, outcome and time.
3. Optionally revoke `example.com` and resend to demonstrate that the same agent now has less access.

A connection being allowed is not proof that a webpage was retrieved. DNS failures, timeouts and an agent's explanation are not policy-denial evidence. Saved files prove useful workspace output, not that every filesystem boundary was exercised. The UI's website approvals grant HTTPS reads through `/usr/bin/curl`; they do not grant host-file access or expand the agent's role. **How this policy works** includes the effective policy and raw, sanitized decisions for deeper explanation.

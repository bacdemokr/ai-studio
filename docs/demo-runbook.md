# Presenter runbook

## Before the demo

On Spark, run `./bac start`, open the localhost SSH tunnel and connect the model in Settings. Do one real personal task and one complete event before the audience arrives. If demonstrating OpenShell, rehearse a protected file read and the approval flow on that host. Keep previous real Results available; do not present a sample or a stale result as a new successful run.

Use Settings → Reset → BaC to clear the event board and team conversations between demonstrations. Lounge Agent Reset removes hired agents; Reset all combines both. Agents and saved files otherwise survive refreshes and server restarts.

## Hiring and Lounge

Let the audience choose a character, interests, tone and skills. Create contrasting agents and try a short weather, document or research task. Compare how each persona approaches the same question. A weather specialist may care about arrival conditions; a skeptical agent may focus on weak evidence.

Show the actual reply and any written artifact. Click the name or portrait to inspect `SOUL.md` and equipped custom `SKILL.md` files. A Custom skill badge means the runtime actually read that file for the reply. Equipped skill chips alone do not prove execution.

If using OpenShell, start with a destination or supported file request that needs permission, approve the request, then retry. The approval UI reflects actual host checks. Unavailable paths are not solved by granting access. DNS failures also need a network fix, not another approval. See the [OpenShell verification guide](openshell-verification.md) for repeatable checks.

## Multi-Agent demo

Choose an event template, check its date/venue, set 3–6 themes, and launch. Casey is required. Preset event specialists run without OpenShell; personal guests keep their own setting.

Prepare the selected production crew before launch; this does not send a model request. Choose available personal guests for closing reactions, or proceed with none. Busy guests are excluded. Guest runtime and protection checks happen when their reaction runs; a failed guest check skips that reaction without blocking the event package. Errors preparing a selected production role block launch and remain visible. Preparation uses the shared queue, so a running Lounge request is not interrupted.

- Casey writes the shared brief and priorities.
- Dylan chooses research queries and proposes sourced, clearly named booth demos.
- Alex works in parallel using Booth-1, Booth-2, etc. He writes the presenter schedule and breaks, favoring topic continuity. The app binds Dylan’s final names to those IDs.
- Morgan receives their outputs and writes the actual event HTML plus a LinkedIn-style draft using the project skills.
- Hired agents briefly react in their saved tone/interests, show a small completion bubble, and return to the lounge. Read the full reactions in chat/Results.

Open Mission Control to show task order and handoffs. Open Results to show each saved contribution: Dylan’s demo proposal, Alex’s timetable, Morgan’s webpage and social post. The contributor links scroll through one page. Expand the proposal’s research details or scheduling decisions when explaining the choices; source and export JSON previews and downloads sit beside each contribution. Expand Activity to inspect observed searches, file reads and writes.

Explain the boundary plainly: agents research, choose, schedule and write; the app dispatches the known graph, checks files and renders validated data. This is a bounded demonstration, not an autonomous event organizer or a claim that multiple agents speed up one GPU.

## If something fails

Keep completed contributions and the actual failure visible. Inspect Activity, saved files and Download evidence. Check the relevant service logs. A deliberate retry may repeat file writes, so inspect existing output first. Never mask a failed real run with a generated success message.

Stop waits for the active model call boundary; it does not instantly cancel GPU work. After an app/gateway interruption, verify whether the previous call is still finishing before retrying. API keys may need reconnecting after a restart.

The [Docker guide](docker-setup.md) contains installation and recovery commands. The [runtime guide](live-studio.md) explains persisted state and access boundaries.

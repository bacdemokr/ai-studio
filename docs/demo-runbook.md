# Presenter runbook

## Before the demo

On Ubuntu or DGX Spark, put the NVIDIA inference key in `api.cfg` beside `bac`, then run `./bac start`. Startup validates the key and prepares the Stage 3 connection. Open localhost:8080, directly or through an SSH tunnel. For Stages 1 and 2, connect a model separately in **Settings → Lounge model**. If using local Qwen, prepare its existing installation with `./bac vllm` first; starting Studio does not start the model server.

Rehearse one real personal-agent task and one `/plan` task with the target models. If demonstrating OpenShell, also rehearse a protected file read and website approval on that host. Use a desktop browser and Enter for presentation mode. Keep previous results available, but identify them as previous runs.

Use **Reset beside Mission Control** to stop active Stage 3 work and clear team chats, attached team documents, generated files and the current plan after confirmation. **Settings → Reset → Lounge agents** removes hired agents and their data; **Reset all** resets both. Download anything needed before resetting. A normal `./bac start` preserves saved demo data.

## Hiring and Lounge

Let the audience choose a character, tone, role and skills. Try a short weather, document or research task and compare how different personas respond. Documents belong to the selected personal agent; other hired agents cannot read them. Add documents with the button or drag them into the chat. Supported formats are PDF, PPTX, XLSX, TXT, Markdown and CSV, up to 10 MB per file.

Show the actual reply and any saved artifact. A Custom skill badge means the runtime read that skill file for the reply; an equipped skill chip alone does not prove execution.

For OpenShell, approve a blocked website through **OpenShell Policy**, then resend the request. Individual approval, pending-request Approve all, and Pre-approve common tasks Approve all have separate scopes. DNS failures and unavailable pages are not solved by granting more permissions. A permission is active only after verification.

## Multi-Agent demo

The room starts with Casey. Use **API & models** to select models for individual team members, then **Apply changes**. These settings are separate from the Lounge model. Start a team task with `/plan`; a normal message goes to the selected agent directly.

Casey answers directly when appropriate or chooses up to three specialists:

| Specialist | Contribution |
| --- | --- |
| Scout | Public web research with source links and access limitations |
| Ada | Supplied-data analysis, calculations and interpretations |
| Iris | Interface design, user flows and usability guidance |
| Cody | Implementation of webpages and small code prototypes |
| Vera | Independent review of supplied work and concrete defects |

The selected specialists enter together and work in assignment order. The old event-template form and Dylan, Alex and Morgan are retired. There is no fixed research/schedule/LinkedIn workflow.

For a compact data-analysis demo, attach a table to Casey and try:

```text
/plan Analyze this table and summarize the three most important findings.
Add an independent review of the calculations and conclusions before finishing.
```

For an implementation demo:

```text
/plan Build a self-contained desktop HTML savings calculator. Include amount,
interest rate and years, validate the inputs, and show the estimated total.
```

Use **Mission Control** to show the trace: Casey's plan, each assignment and expected result, delivered contributions, subsequent decisions, and final response. **Results** shows the current plan's answer and saved files. Use **Preview webpage** for HTML output. Previewing a page does not prove it was tested, and a saved-file check does not prove its calculations are correct.

Explain the limits plainly:

- Explicitly requested review is required; Casey cannot skip it because the producer saved a file. Code reviews are static unless real execution evidence exists.
- Intermediate checkpoints decide whether to continue or return a partial result. General content rework is not repeated at every stage.
- At final synthesis, one already participating specialist may receive one targeted repair for a concrete unmet requirement. An earlier file/output recovery uses that allowance. No new specialist or automatic second specialist review follows a repair.
- Scout performs a short, bounded search and reports stale, blocked or missing evidence. Source excerpts are not full-page verification.
- The team cannot open or control the PC's browser, make purchases, deploy a site, or claim tool execution it did not perform.
- Hired agents may give short personal reactions afterward. These are opinions, not independent reviews.

Casey and the working specialist cannot receive another message while their plan work is active. Stop requests cancellation; a running runtime call may still need to settle. The plan's 600-second dispatch budget is not a guaranteed wall-clock completion time.

## If something fails

Keep saved contributions and the failure visible. Inspect observed Activity, Mission Control, and saved files. Run `./bac logs` for service errors. Inspect existing artifacts before retrying: a new request can repeat writes. Do not replace a failed real run with a sample success.

If required review or another requirement could not finish, describe the result as partial or unavailable. After the single repair, Casey states what changed and what remains unverified.

`./bac start` restarts the app services while preserving data; there is no `./bac restart`. `./bac vllm --restart` is separate and restarts the configured local model server. Stage 3 reloads the validated `api.cfg` connection at startup. API-key providers for Stages 1 and 2 need reconnecting after refresh or restart; keyless local endpoints need no key re-entry.

[Installation and recovery](docker-setup.md) · [Model settings](runtime-settings.md) · [Runtime details](live-studio.md)

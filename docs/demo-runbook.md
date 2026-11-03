# Presenter runbook

## Before presenting

Start the intended branch with `./bac start --keep-data` to retain your rehearsal data. Verify the enabled model connection in **Settings → Model**, set **Location**, and rehearse the chosen task on the presentation host. A model being connected does not guarantee task quality or speed.

## 1. Hiring

Let attendees choose a character, tone, role and skills. Tone and Role have separate editable fields. **Suggest skills** selects suggested skills for review; it does not hire the agent. Presets retain their core skill, and Tech Radar's role is fixed to its scheduled behavior. Extra skills can be added.

Use the room's **i** for the short guide, agent concepts and OpenShell explanation. After hiring, click the agent's name or portrait to inspect and edit its Markdown files. **Instructions** presents the three main instruction files together. Changes apply to subsequent work.

## 2. Agent Lounge

- Try a short chat, weather or document request. Substantial work requires a relevant equipped skill and permitted tools; a role name alone is not enough.
- **OpenShell Policy** shows website requests and observed decisions. Approve access, then resend the request. See the walkthrough below.
- **Tech Radar** demonstrates Heartbeat. Its first check waits at least 10 seconds, then checks run every 20 seconds when capacity is available. Preparation and model calls may delay delivery. Use Pause / Resume; manual chat is disabled while Tech Radar is equipped.
- Periodic Lounge chatter excludes Heartbeat agents and selects an available hire roughly every 30 seconds. It is separate from an agent's scheduled work.

Documents stay with the selected agent. Supported uploads include PDF, PPTX, XLSX, TXT, Markdown and CSV, up to 10 MB per file. Extracted text does not imply the model inspected document images or layout.

## 3. Open Task

Send `/goal` in Casey's chat. Without it, you are talking directly to Casey. Choose the team before sending:

- **Hired only** (default): use available hires with the required skills and tools.
- **Hired + Standby**: Casey may also call Scout (research), Ada (data interpretation), Iris (UX planning), Cody (coding) and Vera (review).

Casey decides who and how many to use, with up to three specialist assignments. Meaningful collaboration is encouraged; a single specialist is valid when others add no useful work. The examples specify tasks and outputs, not a compulsory team.

The example buttons fill editable drafts. Travel guide and Event page use Settings → Location. GPU portfolio and Store email review stage sample files locally; selecting another example replaces the unsent sample, and upload happens only on Send. Manually attached or already submitted files are retained.

An attendee can deliberately try an incomplete team. If the core result is impossible with the available skills, Casey should explain the missing capability before dispatch. Runtime failures or evidence gaps after work begins can produce an honest partial result. Explicit requests to do only the feasible part permit reduced scope.

Idle hires follow into Open Task and wait on benches. Click an idle hire to edit its role, skills, instructions or model. Entering the room does not start a task; Heartbeat is paused there. Lounge returns hires together, and entering Open Task again restores their waiting seats.

Hires retain individual models. On NVIDIA, Casey and standby model badges are editable while idle. Local and other external providers use the configured Open Task model for the built-ins. **Models & connection** opens Settings.

### Read the outcome

- **Mission Control:** assignments, handoffs, recorded decisions and final response, expanded by default. Total elapsed time appears beside Execution trace and freezes as Total time after completion.
- **Advanced reasoning:** provider-returned text or summaries, grouped by agent and call. It starts closed and adds no model request when opened. Availability depends on the model and connection. New updates offers an explicit jump to unseen content without moving the reader automatically.
- **Results:** the answer and saved files, including usable partial output.
- **Usage & time:** recorded tokens and elapsed time. Summed agent time may exceed elapsed time; it is not a billing statement.

Read panels close on outside click or Escape. Nested information panels close from the top. Markdown drafts remain available when the editor is reopened.

Independent review, when requested, needs a different suitable agent and cannot be replaced by a personal reaction. Reviews are static unless actual execution evidence exists. The team has one shared recovery/repair allowance and a five-minute execution budget. Optional polish should not delay a usable core result; hardware and runtime setup can add time.

## OpenShell in the Lounge

Use a protected Web researcher and a normal request such as “Read https://example.com.”

1. Inspect the actual blocked request in **OpenShell Policy**. A URL mentioned in chat may also appear as awaiting approval before a denial is observed.
2. Approve the website and resend. Recent activity shows observed destinations, outcomes and methods when available.
3. Revoke access and resend to demonstrate the change.

An allowed connection does not prove retrieval succeeded. DNS failures, timeouts and model explanations are not policy-denial evidence. Website approvals grant HTTPS reads through the configured tool; they do not grant host-file access or expand skills. Rehearse native enforcement on the actual host.

## Recovery and support

- **Waiting:** check the selected model connection, runtime readiness and any active work.
- **Partial result:** inspect saved output and stated limitations before retrying. Existing work is not replayed automatically.
- **Reset Open Task:** stops and clears team work and restores built-in model defaults. **Remove agents** removes hires and their data. **Reset all** clears both. Connections remain.
- **Issue report:** Settings → Reset → Issue report → Copy diagnostics. Include steps and time; Download includes a larger bounded history.

[Installation](docker-setup.md) · [Model settings](runtime-settings.md) · [Examples](../README_POSSIBLESCENARIOS.md) · [Regression coverage](visitor-regression.md)

# Open Task team and model selection

**03 Open Task** starts with Casey as coordinator. Send `/goal` to assign up to three specialists. `/plan` and `/plans` remain aliases. Leave out the command for a direct conversation.

## Choose a team

- **Hired only** (default): Casey uses your available hires. At least one is needed, and specialist assignments require relevant equipped skills. No particular role preset is required.
- **Hired + Standby**: Casey first assigns an available hire whose equipped skill matches the work. A matching hire takes priority over the equivalent standby specialist. Casey calls Scout (research), Cody (programming), Ada (analysis), Iris (design) or Vera (review) only when no matching unassigned hire is available, or when you explicitly request that standby specialist. This mode also works without hires.

Assignments use the actual tools and permissions of the selected agent. A substantial assignment must match the hire’s equipped skills. Naming an unsuitable hire does not force participation: Casey explains the missing expertise instead. Tool access alone is not suitability, and a skill does not bypass OpenShell policy. Independent review requires a different agent from the producer. Casey’s chat and Mission Control show **Why this agent** from the saved plan; **Not assigned** explains declined named participants. Speech bubbles remain short. Earlier plans may have no recorded selection reason.

Idle hires follow you into Open Task and wait on benches. Assigned agents move to workbenches and stay there after completion; the next confirmed plan moves replaced agents back to waiting seats. The selected mode is locked during a task. Changing modes afterward retains results; reload and Reset Open Task default new tasks to Hired only. Reset clears scenario results and restores Casey/standby default models, while preserving hired agents, their model choices and their own files.


## Choose models

1. Configure Local and/or External Endpoint in **Settings → Model**. Select the **Open Task** connection.
2. Hires use their individual **Model** choices from Hiring or Edit agent. While idle in Open Task, select a hire and click its model badge to search and change it. Unavailable connections are disabled; active or reserved hires cannot change models.
3. With an external NVIDIA connection, click Casey’s model badge in either mode. To configure backups, select **Hired + Standby** and expand **Standby specialists**. Choices save immediately for future work. Return to Hired only before starting if that is your intended team.

NVIDIA defaults are **Nemotron 3 Ultra** for Casey, Cody and Iris, and **Nemotron 3.5 Lightning** for Scout, Ada and Vera. Local and other external providers use the selected Open Task connection model for Casey and backups. Hires always keep their individual choices; changing a scenario connection does not switch them.

**Models & connection** opens the shared Settings panel. Team model choices are locked while work or a reset is in progress.

See [model settings](runtime-settings.md) and [credential storage](session-credentials.md).

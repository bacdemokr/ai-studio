# Open Task team and model selection

**3-2 Open Task** starts with Casey as coordinator. Send `/goal` to assign up to three specialists. `/plan` and `/plans` remain aliases. Leave out the command for a direct conversation.

## Choose a team

- **Hired only** (default): Casey uses your available hires. At least one is needed; no specific role or skill is required to join.
- **Hired + Standby**: Casey prefers suitable hires and can also call Scout (research), Cody (programming), Ada (analysis), Iris (design) and Vera (review). This mode also works without hires.

Assignments use the actual tools and permissions of the selected agent. Naming a hire requires its participation, even outside its usual role; it does not grant additional tools. Independent review requires a different agent from the producer.

Idle hires follow you into Open Task and wait on benches. Assigned agents move to workbenches and return to waiting seats after work. The selected mode is locked during a task. Changing modes afterward retains results; reload and Reset Open Task default new tasks to Hired only. Reset clears scenario results but preserves hired agents and their own files.

**3-1 Event Brief** keeps its fixed Riley, Dylan, Alex and Morgan team, with separate conversations, files and model choices.

## Choose models

1. Configure Local and/or External Endpoint in **Settings → Model**. Select the **Open Task** connection separately from Event Brief.
2. Hires use their individual **Model** choices from Hiring or Edit agent. While idle in Open Task, select a hire and click its model badge to search and change it. Unavailable connections are disabled; active or reserved hires cannot change models.
3. With an external NVIDIA connection, select **Hired + Standby** and expand **Standby specialists** to change Casey’s or a backup’s model. Choices save immediately for future work. Return to Hired only before starting if that is your intended team.

NVIDIA defaults are **Nemotron 3 Ultra** for Casey, Cody and Iris, and **Nemotron 3.5 Lightning** for Scout, Ada and Vera. Local and other external providers use the selected Open Task connection model for Casey and backups. Hires always keep their individual choices; changing a scenario connection does not switch them.

Event Brief uses its selected connection model for every fixed member. **Models & connection** opens the shared Settings panel. Team model choices are locked while work or a reset is in progress.

See [model settings](runtime-settings.md) and [credential storage](session-credentials.md).

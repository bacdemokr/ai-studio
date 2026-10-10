# Open Task team and model selection

**3-2 Open Task** starts with Casey. Send `/goal` to assemble up to three specialists from Scout, Ada, Iris, Cody and Vera. `/plan` and `/plans` remain aliases. Team commands work only in Casey's Open Task chat.

**3-1 Event Brief** has separate agents: Riley, Dylan, Alex and Morgan. Use **Plan an event** for that workflow. Switching scenarios preserves their separate conversations, files and model choices.

## Choose models

1. Open **Settings → Model** and configure Local and/or External Endpoint.
2. Under **Stage connections**, select the connection for Open Task and save.
3. With an external NVIDIA connection, expand **Standby specialists** in Open Task and click the model beside an agent. Search and select a model; the choice saves immediately.

NVIDIA defaults are **Nemotron 3 Ultra** for Casey, Cody and Iris, and **Nemotron 3.5 Lightning** for Scout, Ada and Vera. The picker lists models available to the configured key. Saved choices apply to new work and cannot change while the team is busy or resetting.

Local and other external providers use the selected connection model for the whole Open Task team. Event Brief always uses its selected connection model for every member. **Models & connection** opens the shared Settings panel; it is not a second connection setup.

The assigned Open Task team remains seated after completion or refresh. A new task may select different specialists; resetting Open Task returns to Casey alone.

See [model settings](runtime-settings.md) and [credential storage](session-credentials.md).

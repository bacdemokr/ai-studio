# /plan team and model selection

Open Task starts with Casey and three empty desks. Send `/plan` to Casey to assemble up to three specialists from Scout, Ada, Iris, Cody and Vera. Other chats do not support `/plan`. Event Brief has a separate fixed team (Casey, Dylan, Alex and Morgan), event form and results.

The assigned team stays seated after completion and after refresh. While Casey plans a new request, the previous team waits; substitutions begin when the new assignment is available. BaC reset returns the scene to Casey alone.

Standby specialists includes Casey and every eligible specialist, with an indicator for members currently seated. Each member can select Nemotron 3 Ultra or Nemotron 3.5 Lightning. Defaults are Ultra for Casey and Lightning for specialists. Choices belong to the participant's shared team, survive restart, and apply before the next request. Model changes are rejected while that team is busy or resetting.

The dedicated team API remains independent of Settings and its local model. Stage 3 stores its validated API key in `BAC_DATA_DIR/credentials/stage3.json` (directory mode 0700, file mode 0600), outside the checkout. Refreshing or restarting preserves the connection and model catalog. Replacing the key in Stage 3 setup validates it before saving. The browser, agent prompts and OpenClaw configuration never receive the saved key. Choosing a model does not create a native agent or sandbox.

Validation: `tests/test_team_models.py`, `tests/test_crew_ownership.py`, `tests/team-selection-browser.cjs`, and `tests/dynamic-plan-browser.cjs` cover isolation, busy fences, model badges, empty initial desks, retained teams, substitutions and reset.

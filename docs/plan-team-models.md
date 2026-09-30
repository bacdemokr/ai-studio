# /plan team and model selection

The Multi-Agent Demo starts with Casey and three empty desks. Send `/plan` to assemble up to three specialists. Alex and Morgan remain available in the roster; Dylan is excluded from this workflow. The previous event-template form and automatic event preparation are retired. Previously saved event results remain readable.

The assigned team stays seated after completion and after refresh. While Casey plans a new request, the previous team waits; substitutions begin when the new assignment is available. BaC reset returns the scene to Casey alone.

Standby specialists includes Casey and every eligible specialist, with an indicator for members currently seated. Each member can select Nemotron 3 Ultra or Nemotron 3.5 Lightning. Defaults are Ultra for Casey and Lightning for specialists. Choices belong to the participant's shared team, survive restart, and apply before the next request. Model changes are rejected while that team is busy or resetting.

The dedicated team API remains independent of Settings and its local model. Connect through **API & models**. The validated key is held only in process memory under the browser credential lease. Closing or refreshing that tab, lease expiry, or a server restart disconnects it. Legacy credential files are never read. Model selections persist separately and do not create native agents or sandboxes.

Validation: `tests/test_team_models.py`, `tests/test_crew_ownership.py`, `tests/team-selection-browser.cjs`, and `tests/dynamic-plan-browser.cjs` cover isolation, busy fences, model badges, empty initial desks, retained teams, substitutions and reset.

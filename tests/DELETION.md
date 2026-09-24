# Deletion regression checks

Run these on a development preview. Live tests create and delete their own test
accounts only. Keep other user work idle. Never interpret a timeout or missing UI
card alone as proof that resources were deleted.

| Boundary | Evidence |
| --- | --- |
| Registered / definitions only / legacy files / absent workspace | 64 combinations in `test_deletion_invariants.py`; pinned helper tests; live Reset |
| Completed and unfinished native deletion journals | `native-deletion.cjs`; live interrupted deletion |
| Runtime config unreadable, invalid or unexpectedly missing | Preserve files; injected tests |
| Ordinary and Heartbeat work still active | Verify stopped before sandbox cleanup; live lifecycle tests |
| Sandbox missing already, lost delete reply, registry failure | Verify real inventory before retiring the scoped registry |
| Crash after each native target / before app cleanup | Persist targets, fence new work, resume the saved plan |
| App restart during actual native deletion | `live-deletion-reset.cjs --restart-during-delete` |
| Concurrent/duplicate requests, stale name, different account | Persist concurrent requests; join duplicates; reject stale names and other accounts |
| Native success followed by app filesystem failure | Keep the agent fenced; retry without resurrecting resources |
| UI bulk Reset, reload, original and last agent | Actual Chrome Reset plus browser fixture tests |
| Preservation | Other agents' files, native entries and sandboxes must survive |

Fast fault tests (isolated temporary state; native responses are simulated):

```bash
python3 -B -m unittest discover -s tests -p 'test_*deletion*.py'
node tests/native-deletion.cjs
```

Real runtime tests require the running preview, pinned OpenClaw/OpenShell,
Playwright and Chrome. Set `BAC_DATA_DIR` to the preview's data directory.
The lifecycle suite additionally uses its existing in-memory model connection.
No user API keys are read or persisted by these tests.

```bash
python3 -B tests/live-deletion-cycles.py --run-live \
  --data-dir "$BAC_DATA_DIR" --report /tmp/deletion-lifecycle.json
node tests/live-deletion-reset.cjs --run-live
```

On this Mac development preview, the restart variant also needs
`PREVIEW_METADATA_PATH` pointing to `work/dev-deployment.json`. It checks the
listener's working directory and active work before stopping only the app server.
OpenClaw/OpenShell keep running. The accepted deletion must resume without another
request; the interrupted browser Reset can then continue the remaining agents.

```bash
node tests/live-deletion-reset.cjs --run-live --restart-during-delete
# Additional check: restart while a real native chat is running
node tests/live-deletion-reset.cjs --run-live --restart-during-chat
```

Retain the JSON reports. Report failure and diagnostic runs separately from final
passing runs, and state the OS actually tested. These checks do not certify
Ubuntu behavior unless run on Ubuntu, or promise success when storage permissions
or a runtime outage prevent cleanup.

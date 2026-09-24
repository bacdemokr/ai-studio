# Deletion regression checks

Run these on a development preview. Live tests create and delete their own test
accounts only. Keep other user work idle. Never interpret a timeout or missing UI
card alone as proof that resources were deleted.

| Boundary | Evidence |
| --- | --- |
| Registered / definitions only / legacy files / absent workspace | 64 combinations in `test_deletion_invariants.py`; pinned helper tests; live Reset |
| Batched unused-role inspection | `deletion-plan.cjs`: registration, any journal, sandbox records and orphan directories all require full cleanup; one registry read per plan |
| Completed and unfinished native deletion journals | `native-deletion.cjs`; live interrupted deletion |
| Runtime config unreadable, invalid or unexpectedly missing | Preserve files; injected tests |
| Ordinary and Heartbeat work still active | Verify stopped before sandbox cleanup; live lifecycle tests |
| Sandbox missing already, lost delete reply, registry failure | Verify real inventory before retiring the scoped registry |
| Crash after native deletion / before app cleanup | Persist the personal identity, fence new work, reconcile before removal |
| App restart during actual native deletion | `live-deletion-reset.cjs --restart-during-delete` |
| Concurrent/duplicate requests, stale name, different account | Persist concurrent requests; join duplicates; reject stale names and other accounts |
| Native success followed by app filesystem failure | Keep the agent fenced; retry without resurrecting resources |
| UI bulk Reset, reload, original and last agent | Actual Chrome Reset plus browser fixture tests |
| Preservation | Other agents' files, native entries and sandboxes must survive |

Fast fault tests (isolated temporary state; native responses are simulated):

```bash
python3 -B -m unittest discover -s tests -p 'test_*deletion*.py'
node tests/native-deletion.cjs
node tests/deletion-plan.cjs
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

Deletion requests now acknowledge a durable queue entry before native cleanup.
Acknowledgement is not completion. A dedicated cleanup worker preserves the
single-deletion lock, checks running work, and resumes the queued personal identity after restart.
The UI remains navigable and displays cleanup progress or an explicit retry state.
Bulk Reset queues all identities before releasing the dialog. Native cleanup can
still be slow; this change removes the UI/mission-worker wait, not native costs.

`test_agent_deletion.py` covers a stalled cleanup alongside another agent's task,
duplicate acknowledgements, persisted queues, and an individual cleanup failure.
`delete-pending.cjs`, `deletion.cjs`, and `agent-reset.cjs` cover navigation while
pending, post-deletion hiring, retry controls, and bulk Reset in Chrome.

## Personal agents and the BaC team

Hired agents own only their personal runtime. BaC jobs, crew chats, policies and result files belong to an account-owned crew context, so deleting the selected personal agent does not delete the built-in team. An agent explicitly participating as a crew member or reaction guest still fences that active job before removal.

Each current team has an explicit resource registry for its native identities, workspaces and chat sessions. There is one team per account. Startup does not discover or import old personal role folders, and personal deletion never scans for crew roles. `test_crew_ownership.py` covers stable registered resources, restart, 12-agent deletion, HTTP isolation, shared results and policy preservation.

## Permanent retirement

A completed personal-agent deletion removes its app profile, jobs/chat, uploaded
files, memory, results, policy/heartbeat state, native workspace/session database,
OpenShell sandbox/registry, rotated config entries and completed native deletion
journal. Account-owned BaC crew packages remain owned by the crew.

OpenClaw 2026.9.4 normally moves deleted files into the host Trash. The app-owned
`native_cleanup_loader.mjs` keeps the pinned native guards and rename/copy logic,
but routes receipt-marked BaC paths into `openclaw/deletion-staging/.Trash`.
It does not modify the runtime image or redirect unrelated native deletions.
Before moving each path, the native adapter records its exact destination and
filesystem identity. The app permanently removes only those recorded containers
and drops recovery receipts only after successful native finalization. It never
scans or empties the user's Trash. Restart the app and its managed runtime after
updating this integration; Docker startup uses it without an image rebuild.
Before invoking native deletion, the app verifies that the running gateway has
loaded the current cleanup adapter. An old or missing adapter pauses deletion
with restart guidance before any native files are removed.

Failure at any cleanup step leaves the identity fenced and retryable. Tests cover
partial removal after a marker disappears, replaced containers, symlink targets,
missing routing proof, finalization failure and repeated cycles. The app database
uses secure_delete; browser drafts/layout and in-memory status are discarded too.
This is application-data retirement, not forensic erasure of shared operational
logs, exported files, OS snapshots, or operator-created backups. Earlier files
already moved into the system Trash are not imported into this new cleanup path.

```bash
python3 -B -m unittest discover -s tests -p 'test_*deletion*.py'
node tests/native-deletion-staging.mjs /absolute/path/to/private/openclaw
```

## Lifecycle races

`test_lifecycle_races.py` uses controlled barriers to cover edits competing with
deletion or a new task, failed creation rollback, stale onboarding and policy
requests, repeated warmups, and heartbeat enable/disable ordering. It also checks
that preparation failures during cancellation settle the job and that late
callbacks cannot revive it. Missing owners and deleting owners cannot start
queued jobs.

```bash
python3 -B -m unittest discover -s tests -p 'test_lifecycle_races.py'
```

The live `lifecycle` scenario creates 12 disposable agents (six OpenShell), then
deletes ready agents, agents still preparing, and an agent during a model call.
It repeats deletion requests and checks native storage, config backups and
sandbox removal, as well as preservation of the pre-existing crew. See the live
test command above. Deletion during active work can take longer than idle
deletion because cleanup waits for the in-flight operation to stop safely.

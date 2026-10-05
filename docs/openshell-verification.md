# OpenShell verification

Use temporary agents for infrastructure testing. Never grant test destinations to a participant’s agent. The opt-in tests below delete only the synthetic agents they create. They use real OpenShell sandboxes, but replace the model-readiness gate; they do not establish LLM quality or end-to-end Spark acceptance.

## Regression checks

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
node tests/policy-activity.cjs
```

With Playwright and Chrome installed and the app running, run `tests/policy-recovery.cjs`, `tests/policy-states.cjs`, `tests/policy-bulk.cjs` and `tests/policy-pending.cjs`. The recovery/pending fixtures use port 8080; the states/bulk fixtures accept `BAC_TEST_URL`. They mock policy API responses and do not change real approvals.

Coverage includes:

- OpenShell-on hiring queues model-free workspace preparation immediately. The hiring response does not wait for provisioning. An immediate chat reuses or takes over that preparation; it adds no approvals.
- Preparation stays out of personal missions and Busy labels. The Policies panel updates automatically; No manual preparation button is shown during automatic setup or after it succeeds; Retry is available when the workspace is still unavailable.
- Chat, policy changes and deletion remain fenced during native preparation; a failed warmup leaves the agent available for a protected retry.
- Exact-host approval, revoke, bulk approval, per-agent isolation and app-state reload.
- Busy/deleting agents, concurrent policy updates and queued work fencing.
- Timeout before activation, lost acknowledgement after activation, stale revisions and partial application across multiple owned sandboxes.
- Filesystem-policy drift, malformed native responses, unavailable logs and scoped native lookup.
- Removed host-file approvals are rejected; upgrades retire old grants and managed transfer copies without touching original files or uploads.
- Interrupted deletion, idempotent cleanup, preparation and optional BaC guests.

## Real host checks

Point `BAC_DATA_DIR` at the host’s configured data directory:

```sh
BAC_LIVE_POLICY_TEST=1 BAC_DATA_DIR=/path/to/data python3 -u -B tests/live_policy_flow.py
BAC_LIVE_POLICY_TEST=1 BAC_DATA_DIR=/path/to/data python3 -u -B tests/live_crew_research.py
```

The network test verifies default deny, approval persistence, a successful public GET, Zurich geocoding and a live Open-Meteo forecast, denial of an unrelated destination, revocation and native cleanup. It also verifies that geocoding approval does not grant forecast access, and revoking the weather bundle preserves a separately approved geocoding host. It exits unsuccessfully if an approved GET fails, even when activation succeeded.

## Interpreting failures

“Applied” means that the running sandbox loaded the expected network, filesystem and Landlock compatibility settings. It does not promise that a remote site, DNS or the network works, nor does it claim kernel-level filesystem enforcement on a host lacking Landlock support.

Do not infer a missing permission from HTTP 403 or `CONNECT tunnel failed` alone. Read the native event:

- `engine:opa` with “network connections not allowed by policy”: review the exact destination approval.
- “DNS resolution failed”: check the host network/VPN and the VM resolver; granting access again cannot repair DNS.
- Other `engine:ssrf` denials: inspect the destination address; do not widen permissions as a workaround.
- Missing or malformed native responses: leave the policy unverified. Never fall back to unprotected execution.

`openshell gateway info` checks the gateway, but a healthy gateway does not verify outbound DNS. After repairing the host network, rerun the real network test before demonstrating weather or research.

## Protected Demo Producer - 2026-09-22

On the development Mac with OpenClaw 2026.9.4 and OpenShell 0.0.116:

- Two independent sandbox runs each completed three research missions: six search queries and six article reads per run, with JSON saved inside the sandbox. Only `blogs.nvidia.com:443` needed approval.
- Native policy logs confirmed an unrelated destination was denied. The loaded policy remained read-only. A captured L7 write-denial log exposed a parser bug (HTTP logs without an arrow), now covered by regression tests.
- A deterministic local protocol fixture exercised the actual OpenClaw skill read, sandbox exec, search, article read, native write/read and mirror synchronization. Every tool completed and the resulting files were checked. This fixture is not an LLM.
- 365 Python tests, the policy-activity JavaScript check and the UI build passed.

Real-model generation could not be verified: the existing model proxy endpoint refused connections. Reconnect the model and rehearse a complete event before presenting. These Mac results do not establish Ubuntu/DGX Spark acceptance; run `live_crew_research.py` on the target host too.

## Local verification record - 2026-09-21

The final Python regression run passed 256 tests. Browser checks cover recovery, pending approval, bulk approval and failure states.

On this macOS host with OpenShell 0.0.116, synthetic sandbox creation, loaded-policy verification, app-state reload, protected file read/write boundaries and deletion were exercised against the actual runtime. Approval timeout and malformed-response cases use failure injection.

The initial approved public GETs failed with native DNS-resolution denials. The same failure was later reproduced for Scout's approved `geocoding-api.open-meteo.com` request, while the host returned HTTP 200 for the identical URL. The sandbox returned a proxy CONNECT 403 before contacting the weather service; it was not a weather-service rejection or a missing geocoding approval.

### macOS VM DNS repair

In [OpenShell v0.0.116's VM initialization](https://github.com/NVIDIA/OpenShell/blob/v0.0.116/crates/openshell-driver-vm/scripts/openshell-vm-sandbox-init.sh), a guest without `udhcpc` falls back to static networking and public Google DNS. This host's VM logged `no DHCP client, using static config` and used `8.8.8.8` / `8.8.4.4`, which failed in the current network environment. The same source defines the VM's built-in gvproxy DNS relay at `192.168.127.1`.

The local repair sets guest `/etc/resolv.conf` to:

```text
nameserver 192.168.127.1
options timeout:2 attempts:2
```

The running participant VM was stopped while idle, its overlay was backed up, and the resolver was changed on a cloned disk before an atomic replacement and native restart. The existing approval policy and revision were verified unchanged. The empty VM overlay template was updated separately so newly created VMs inherit the resolver. No host DNS settings, gateway binaries, endpoint approvals or sandbox enforcement rules were changed.

This is a **local workaround for the macOS 0.0.116 VM driver**, not application logic or a Linux/DGX Spark configuration. Do not modify a running VM disk. An offline ext4 edit must first replay the stopped VM's journal on the copy (`e2fsck -p`); otherwise the next boot can silently replay the old resolver over the edit. Keep a backup, verify the written file and filesystem, and reject unexpected existing DNS settings rather than overwriting them. The empty template contains no participant data; never seed a template from a participant overlay.

An OpenShell upgrade, cache reset or different overlay size can replace that template. Re-run the real network acceptance test afterward; do not treat a healthy gateway or a loaded policy as proof of working outbound requests. Prefer a supported upstream fix when available rather than applying this version-specific workaround to another runtime.

After the repair, Scout's existing exact-host approval returned HTTP 200 for Zurich geocoding and an unrelated destination remained denied. A fresh synthetic agent passed the full network acceptance test above, including live forecast retrieval, separate-host denial, weather-bundle revoke, retained geocoding approval, unrelated-host denial, GitHub revoke and native deletion. The 28 policy tests and 7 native-response resilience tests also passed. Participant approvals were not expanded; Scout still needs forecast-host approval (or the explicit Weather & city lookup preset) before it can retrieve weather. The app and model gateway did not need restarting.

## Native deletion performance check (2026-09-21)

Using a disposable OpenClaw 2026.9.4 gateway on this macOS host, deleting three synthetic **standard** agents took 5.26 seconds with the previous helper and 3.15 seconds with the gateway-first helper. This measures native cleanup, excluding active model calls and OpenShell sandbox teardown; it is not a latency guarantee. A second gateway run confirmed that a shared workspace remains intact and is not reported as a successful app deletion. With the gateway stopped, the native local fallback removed all three test workspaces and preserved the unrelated agent.

`node tests/native-deletion.cjs` checks gateway routing, offline/journal fallback, retained storage, malformed results, and that timeouts or ambiguous disconnects do not trigger another deletion attempt. `python3 -B -m unittest discover -s tests -p 'test_agent_deletion.py'` also checks active-job fences, retries, and a single authoritative absence check after a committed OpenShell delete timeout.

### Inspect Dylan in the app

Select Dylan in Multi-Agent demo, then **OpenShell Policy**. Lounge agents and Dylan use the same policy panel and approval/revocation implementation. Dylan starts with NVIDIA Blog read access as a default; edits are saved for his identity separately from personal-agent approvals. Revoking access stays revoked across preparation, subsequent tasks, and server restarts. **Approve** restores access explicitly. Before a sandbox exists, saved access is shown as unverified. Opening the panel never provisions or changes permissions. OpenShell is an execution protection setting, not a custom skill.

A disposable native Dylan sandbox verified the shared controls: the default NVIDIA Blog request returned HTTP 200; revocation removed access, and another preparation kept it blocked (curl exit 56 with an OpenShell deny record); explicit approval restored HTTP 200. The test sandbox was removed afterward. Browser fixtures also cover revocation before the first task, re-approval, and separation from personal-agent policies.

### Live shield and external connection feedback

A fresh native **allow** record shows an outbound packet following a dashed path from the agent to a rotating globe, labeled **Request allowed** with the destination. This works for Dylan and protected Lounge agents. Approval alone never triggers the effect; the agent must make a request. The label represents OpenShell's permission decision, not a guarantee that the website returned HTTP 200. Allowed requests do not delay chat replies. Reduced motion shows a static globe, path and direction arrow. A simultaneous denial takes visual priority. Browser fixtures verify both outcomes, correct targets, rotation, expiry and deduplication; they do not claim a live network request.

Protected tool runs sample their own native OpenShell network logs in the background. A confirmed policy denial shows the matching agent’s outbound request striking the inside of a translucent hex-pattern shield, spreading a surface ripple and sparks, and returning inward. The packet never crosses the shield. A short Request blocked label names the destination. Upstream HTTP errors and bare model claims do not trigger it. Repeated log entries are deduplicated, old events expire, and paused/reduced motion shows a steady shield and label. Native log timestamps tolerate one second of host/sandbox clock skew. No model call or policy change is made by the animation observer. When the shield is shown, the matching agent’s chat reply and Lounge completion bubble wait until three seconds after the effect starts. Model execution continues normally; a reply arriving later appears immediately. Repeated polling does not restart this display delay.


## Website-only controls

The Approved websites panel manages HTTPS network destinations only. File-grant APIs, path preflight, protected-copy import, host write-back and file-approval shield events have been removed. Native OpenShell workspace isolation remains. Use uploads for input documents and workspace artifacts for results.

On upgrade, the app removes old `file:` approvals and only its managed `inbox/approved-<hash>.txt` transfer copies (including quarantined directory copies). Original host files, ordinary uploads and event artifacts are preserved. OpenClaw mirror mode replaces the remote workspace from the cleaned local workspace before the next protected run. Existing chat history remains historical data; runtime instructions explicitly state that file grants are no longer available.

## CLI capability compatibility

Sandbox preparation probes `sandbox create --help` before sending a create request. It uses `--detach -- sleep infinity` only when advertised; otherwise it uses `-- true`, matching the pinned OpenClaw plugin. OpenShell 0.0.106 keeps the sandbox after that initial command exits ([upstream implementation](https://github.com/NVIDIA/OpenShell/blob/v0.0.106/crates/openshell-cli/src/main.rs#L2839)). Creation is never retried with different arguments after a failure. Both paths retain the ownership label, default-deny policy and `--no-auto-providers`.

Policy inspection and application use the same inventory filtering: registry entries confirmed absent by a successful complete inventory are excluded, while stopped/existing sandboxes still require verification. An unavailable inventory remains a failure. This does not delete registry records or sandbox data.

On 2026-09-30, the development host's selected CLI was 0.0.106. A protected Orbit sandbox was prepared through the fallback, verified Ready with a loaded policy, and executed a harmless command. Unapproved `www.google.com` returned 403; restoring the user's already-saved exact `google.com` grant returned HTTP 301 without following the redirect. No extra destination was approved. CLI capability and stale-registry behavior also have failure-injection regression tests.

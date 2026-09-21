# OpenShell verification

Use temporary agents for infrastructure testing. Never grant test destinations to a participant’s agent. The opt-in tests below delete only the synthetic agents they create. They use real OpenShell sandboxes and file transfers, but replace the model-readiness gate; they do not establish LLM quality or end-to-end Spark acceptance.

## Regression checks

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
node tests/policy-activity.cjs
```

With Playwright and Chrome installed and the app running, run `tests/policy-recovery.cjs`, `tests/policy-states.cjs`, `tests/policy-bulk.cjs` and `tests/policy-pending.cjs`. The recovery/pending fixtures use port 8080; the states/bulk fixtures accept `BAC_TEST_URL`. They mock policy API responses and do not change real approvals.

Coverage includes:

- Creation before the first model turn; retries preserve the saved approval set.
- Exact-host approval, revoke, bulk approval, per-agent isolation and app-state reload.
- Busy/deleting agents, concurrent policy updates and queued work fencing.
- Timeout before activation, lost acknowledgement after activation, stale revisions and partial application across multiple owned sandboxes.
- Filesystem-policy drift, malformed native responses, unavailable logs and scoped native lookup.
- Unsupported paths, symbolic links, protected file copies, read-only versus read/write, and revoked copies.
- Interrupted deletion, idempotent cleanup, preparation and optional BaC guests.

## Real host checks

Point `BAC_DATA_DIR` at the host’s configured data directory:

```sh
BAC_LIVE_POLICY_TEST=1 BAC_DATA_DIR=/path/to/data python3 -u -B tests/live_policy_flow.py
BAC_LIVE_POLICY_TEST=1 BAC_DATA_DIR=/path/to/data python3 -u -B tests/live_file_access.py
```

The network test verifies default deny, approval persistence, a successful public GET, Zurich geocoding and a live Open-Meteo forecast, denial of an unrelated destination, revocation and native cleanup. It also verifies that geocoding approval does not grant forecast access, and revoking the weather bundle preserves a separately approved geocoding host. It exits unsuccessfully if an approved GET fails, even when activation succeeded. The file test checks host-path isolation, protected copies, write-back boundaries and revoke cleanup using a temporary file.

## Interpreting failures

“Applied” means that the running sandbox loaded the expected network, filesystem and Landlock compatibility settings. It does not promise that a remote site, DNS or the network works, nor does it claim kernel-level filesystem enforcement on a host lacking Landlock support.

Do not infer a missing permission from HTTP 403 or `CONNECT tunnel failed` alone. Read the native event:

- `engine:opa` with “network connections not allowed by policy”: review the exact destination approval.
- “DNS resolution failed”: check the host network/VPN and the VM resolver; granting access again cannot repair DNS.
- Other `engine:ssrf` denials: inspect the destination address; do not widen permissions as a workaround.
- Missing or malformed native responses: leave the policy unverified. Never fall back to unprotected execution.

`openshell gateway info` checks the gateway, but a healthy gateway does not verify outbound DNS. After repairing the host network, rerun the real network test before demonstrating weather or research.

## Local verification record — 2026-09-21

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

# Prepare a local model

`./bac vllm` starts or reuses **Qwen by default**, then waits for the exact model
ID and a small inference request to succeed. This command runs independently of
Docker, Studio, and the host-saved NVIDIA API key. Ordinary `./bac start` never starts or
waits for a local model, even if model configuration exists or model files are
missing. `./bac stop` stops the BaC services and their OpenShell sandboxes, but leaves the host model server running and preserves saved data. Use `./bac stop --all` to also stop the local model launched by this installation, remove the Compose stack, and reset its application data and OpenShell policies. Externally managed model servers and model weights are preserved.

```bash
./bac vllm                # Prepare Qwen, default wait: 600 seconds
./bac vllm --model qwen   # Same, explicit selection
./bac vllm --model gemma  # Only if a Gemma installation is configured
./bac vllm --restart      # Stop the configured server, restart and wait
./bac vllm --status       # Inspect the local model
./bac vllm --logs         # Show the managed model service journal
./bac vllm --stop         # Stop only a model this helper launched
./bac start               # Start Studio separately
```

When Studio is inside a `build-a-claw` installation, `./bac vllm` automatically
reads the selected model's launch settings from the immediate parent's `config.json` if
`local-model.json` is absent. It resolves the weight path relative to that
installation and reuses its executable and environment settings. This does not
invoke the parent demo or enable local models during ordinary Studio startup. The parent directory must be named `build-a-claw`. For example, a parent model path of `models/qwen` corresponds to `../models/qwen` from the Studio checkout; the helper resolves it to an absolute path.

For a standalone installation or to override those settings, put a
machine-specific `local-model.json` beside `bac`. It contains a `models`
object and optional `wait_seconds` (1–3600). Each model specifies its `model_id`,
`model_path`, `base_url`, `context_window`, exact `argv` list, and `env` object.
Qwen remains the command default regardless of `default_model` or `enabled` in
this file. `model_path` must be an **absolute path**, not a literal `../models/qwen`.
Use the installed executable and actual weight path in `argv` too. These paths
can point anywhere on the host PC; a `build-a-claw` parent is not required when
this file is present. No model files or runtime packages are downloaded.
If paths are missing, `vllm` explains the problem; `start` is unaffected.

After starting Studio, connect Local in **Settings → Model → Local**
using the model ID and endpoint printed by `vllm`. Open Task prefers the
External Endpoint by default and can be routed to Local. Model preparation does not change Studio's
saved provider settings.

The helper requires host Python 3.9+ and a systemd user session to launch a new
background model service. It displays loading progress every 15 seconds, fails
early if the service exits, and times out with a useful error. An unexpected
listener is rejected. Normal `./bac vllm` startup reuses a healthy external server without stopping it.
A newly launched model is stopped if readiness fails. Logs remain in the user
journal; model files are preserved. Changing a managed model's launch settings
requires `./bac vllm --stop` first.

If the service launch record is missing or its invocation ID has changed,
`./bac vllm` can still reuse the endpoint after checking the configured model,
context limit and successful inference. It does not adopt or stop that service.
If the endpoint is not ready, inspect `./bac vllm --status` and `./bac vllm --logs`
and retry when loading finishes. `--restart` refuses an active service with an
unmatched launch record before signalling any processes.

Machine-specific configuration and service identity under `.local-model/` are
ignored by Git. Do not put API credentials in this unauthenticated local model
configuration. BaC removal does not delete the external weights or vLLM runtime;
stop a helper-owned model explicitly before removing Studio.

`./bac vllm --restart` is the demo recovery command. It checks the replacement
installation first, stops the helper-owned service (or the exact configured
external vLLM command and its captured workers), restarts Qwen, and waits for
successful inference. It sends TERM first and uses KILL if workers do not exit.
It never uses a broad process-name kill. If an occupied port cannot be tied to
the configured command, restart fails without killing that listener. Explicit
restart may interrupt other applications using this same model server.

Missing-installation errors list the required executable and weights paths, explain
how to update local-model.json, and remind you that ./bac start still works
independently. Failed new launches print the final startup-log lines automatically.

See [model settings](runtime-settings.md), [Qwen with vLLM](qwen3-vllm.md), and [installation](docker-setup.md).

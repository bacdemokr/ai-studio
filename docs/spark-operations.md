# Set up once, review many application updates

Use one checkout of `bacdemokr/tmp` on Spark. Keep large model files and the Python serving environment outside that checkout. Application updates never run model setup or restart the LLM service.

**Scope:** the management commands prepare a separate model server and manage the current UI prototype. The UI's agents and tools are still simulated; installing a model does not connect them to inference. Model startup and performance still require validation on your Spark.

## 1. First-time prerequisites

Use your normal Linux user on DGX Spark with its NVIDIA driver installed. Do not run `./bac` with sudo. The managed services require a working systemd user session.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv ffmpeg

git clone https://github.com/bacdemokr/tmp.git
cd tmp
./bac doctor
```

The repository is private, so Git on Spark must be authenticated. If you already cloned it for the earlier preview, run `git pull --ff-only` once to obtain the new `bac` command.

If the foreground `./start.sh` server is still running on port 8080, stop it with Ctrl+C before starting the managed app.

For services to keep running after your last SSH session closes and start after a reboot, enable lingering once:

```bash
loginctl enable-linger "$USER"
```

Depending on Spark's local policy, this command may require administrator help. Without lingering, keep a logged-in user session while reviewing the demo. Service units are installed under `~/.config/systemd/user/` and enabled for that user; no system-wide service is installed.

## 2. Install a shared model server

### Qwen (default choice)

```bash
./bac llm plan qwen       # inspect packages, pinned model revision and launch options
./bac llm setup qwen      # install the environment and download this model once
./bac llm start qwen      # start the background model service
./bac llm check           # succeeds after the endpoint becomes ready
./bac llm logs            # recent startup output, including failures
```

Setup reuses `uv` if available; otherwise it installs `uv` in a private bootstrap environment. `uv` supplies Python 3.13 for the serving environment. The runtime uses `vllm==0.28.0`, `flashinfer-python==0.6.16.post3` and `nvidia-cutlass-dsl>=4.6.2`, following the supplied [Build-a-Claw guide](https://hackmd.io/@anushapant/BJDdpPHNzl). The full resolved package list is saved on Spark in `runtime/resolved-requirements.txt`; the CUTLASS lower bound and transitive dependencies are not a complete cross-machine lockfile.

Before downloading weights, setup checks CUDA capability and the b12x GEMM/MoE kernels. If that check fails, setup stops instead of treating a fallback as a successful NVFP4 setup. Initial downloads and first-start kernel compilation can take time. `llm start` reports that startup was requested; `llm check` separately verifies readiness.

### Optional Gemma

```bash
./bac llm setup gemma
./bac llm start gemma
./bac llm check
```

Starting Gemma stops the managed Qwen service first, and vice versa. Both sets of weights may stay on disk, but only one managed LLM runs at a time. An unrelated server occupying port 8000 is never killed; stop or reconfigure it yourself before using the managed service.

Both profiles expose the same endpoint and model alias:

```text
base_url = http://127.0.0.1:8000/v1
model    = bac-local
```

The selected original model ID and revision are recorded in `~/.local/share/bac-demo/llm.json`. A future agent backend can use that one endpoint for every role. Gemma's tool template is fetched from vLLM `v0.28.0` and checked against a committed SHA-256.

### Changes relative to the reference guide

- Only Qwen/Gemma are included; no second vision model is launched.
- The endpoint binds to loopback, uses the stable `bac-local` alias and reads a dedicated local weights directory.
- Model revisions are pinned in `runtime/profiles.json` rather than following the Hugging Face repository's moving default branch.
- Gemma's context length is explicitly set to 262144, matching the guide's model table.
- `CUTE_DSL_ARCH=sm_121a` and `MAX_JOBS=8` are set for the managed runtime.
- The scripts do not change drivers, drop Linux filesystem caches, install OpenClaw/Hermes, or modify their existing configuration.

The Qwen profile retains the reference's 0.6 memory utilization and 4 maximum sequences; Gemma retains 0.7 and 8. These are source-based starting configurations, not a benchmark from this repository. Adjustments should be validated on the target Spark.

If you already have the guide's model server running, the app can be reviewed without installing another one. The managed setup intentionally uses its own weight directories and may download a separate first copy; it does not take ownership of your global Hugging Face cache or existing environments.

## 3. Start the application

```bash
./bac app start
./bac status
```

Open `http://localhost:8080` on Spark. From a laptop, keep this tunnel open:

```bash
ssh -N -L 8080:127.0.0.1:8080 YOUR_SPARK_USER@YOUR_SPARK_HOST
```

Then open `http://localhost:8080` on the laptop. A direct trusted-LAN preview is also available:

```bash
./bac app start --host 0.0.0.0 --port 8080
```

Open `http://SPARK_IP:8080`. This prototype server has no authentication. LLM serving remains on loopback regardless of the app's host setting.

## 4. The everyday review loop

After a new version has been pushed to GitHub, run this from the existing checkout:

```bash
./bac update
```

The command fetches `origin/main`, accepts a fast-forward update, builds an immutable application snapshot, switches the current release, and restarts the app if it was running. It then checks that the app reports the expected commit. The LLM stays loaded; its environment, weights and selected profile are not changed. If the app was stopped, the new release is prepared but remains stopped until `./bac app start`.

Refresh the browser to see the new UI. The header's **Build** label shows the deployed commit prefix. Automatic refresh is intentionally avoided because the current prototype stores its in-progress brief and agent customization only in browser memory; a refresh clears that session.

No model downloads, Python package installs or GPU warmup happen as part of `./bac update`. A checkout with local edits or diverged commits is rejected; the command does not stash, reset or overwrite those edits.

Running update again on the same version leaves the current and rollback releases unchanged.

### If a version does not look right

```bash
./bac rollback
```

This restores the previous successful application release, leaving the model server and Git checkout alone. Refresh the browser again. A build failure keeps the old release; a failed health check attempts to restore and restart it automatically. Logs are available through `./bac app logs`.

Release snapshots are retained under `demo/releases/`. They are small application copies, not model copies. There is no automatic release pruning yet.

## 5. Stop or delete only what you intend

```bash
./bac llm stop                 # release GPU memory, retain downloaded model files
./bac llm remove qwen          # preview the exact managed directory to delete
./bac llm remove qwen --yes     # remove Qwen weights; retain Gemma and shared runtime
./bac llm remove gemma --yes    # remove Gemma weights
./bac llm remove-runtime --yes # remove the private vLLM environment; retain models
./bac app stop                 # stop only the web demo
```

Deleting the selected model also stops and disables its managed LLM service. Deletion does not touch global Hugging Face caches, unrelated models, driver packages, OpenClaw/Hermes, the Git checkout or the app. `remove-runtime` preserves the recorded dependency list, bootstrap tools, Python installation and download/kernel caches. No deletion command recursively removes your home directory or the whole data root.

To recover after deleting only a runtime, run `./bac llm setup qwen` (or `gemma`) again. Already installed, unchanged model files are reused. If runtime pins or an installed model profile change in a later repository version, setup asks for an explicit remove/setup cycle; regular app updates do not migrate them silently.

## Files that change independently

```text
~/tmp/                                  Git checkout: UI, agents, scripts, docs
~/.local/share/bac-demo/
  runtime/vllm-env/                      Slow-changing shared Python environment
  runtime/resolved-requirements.txt      Record of the installed versions
  models/qwen/                          Pinned Qwen weights and installed profile
  models/gemma/                         Pinned Gemma weights and tool template
  cache/                                Private download / compilation caches
  llm.json                              Shared endpoint and selected model
  demo/releases/<commit>-<id>/           Small application snapshots
  demo/current -> releases/...          Active review version
  demo/previous -> releases/...         Rollback target
```

Set `BAC_DATA_DIR` before your first setup if you need another disk, and keep using the same value for every command. The path must be a dedicated directory outside the checkout. No personal tokens are stored in Git; an optional `HF_TOKEN` may be supplied through your shell during setup.

## Validation performed here

Host-side tests cover model-scoped deletion, symlink protection, single-service model switching, immutable installed profiles, clean Git updates, application rollback, build failure recovery, health failure recovery and refusal to overwrite unrelated service units. The web workflow tests also pass.

The generation machine is macOS. Actual Linux systemd execution, ARM64 package resolution, weight loading and NVFP4 kernel performance have not been run on Spark yet. Use `doctor`, `llm logs`, `llm check`, `app logs` and the Build label during the first Spark review.

Implementation references: [vLLM 0.28.0 argument handling](https://github.com/vllm-project/vllm/blob/v0.28.0/vllm/engine/arg_utils.py), [b12x availability checks](https://github.com/vllm-project/vllm/blob/v0.28.0/vllm/utils/flashinfer.py), [Gemma tool template](https://github.com/vllm-project/vllm/blob/v0.28.0/examples/tool_chat_template_gemma4.jinja), [uv CLI](https://docs.astral.sh/uv/reference/cli/), [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli).

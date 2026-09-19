# Bundled renderer

- Project: Three.js
- Version/tag: r180 (0.180.0)
- Source: https://github.com/mrdoob/three.js/blob/r180/build/three.cjs
- Local source: `three-r180.cjs`, upstream build with one indentation-only whitespace fix
- License: MIT, retained in `three-LICENSE.txt`

The build script wraps CommonJS exports in a private scope and embeds the renderer in the standalone page. No remote module or asset request occurs at runtime.

## OpenShell policy reference

`scripts/security_lab.py` adapts the policy fields from NVIDIA/OpenShell's Apache-2.0 sandbox-policy-quickstart example at commit `fa0bfa490e42c87a74a70be6ebb40faee7fb8faa`. Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. The upstream license is retained in `OpenShell-LICENSE.txt`. The probe controller is BaC code; no OpenShell binary is bundled here.

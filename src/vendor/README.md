# Bundled renderer

- Project: Three.js
- Version/tag: r180 (0.180.0)
- Source: https://github.com/mrdoob/three.js/blob/r180/build/three.cjs
- Local source: `three-r180.cjs`, upstream build with one indentation-only whitespace fix
- License: MIT, retained in `three-LICENSE.txt`

The build script wraps CommonJS exports in a private scope and embeds the renderer in the standalone page. No remote module or asset request occurs at runtime.

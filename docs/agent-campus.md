# A campus you can explore

The default screen now renders a real WebGL workspace using bundled [Three.js r180](https://github.com/mrdoob/three.js/tree/r180). It uses generated geometry and local Canvas textures, so Spark does not need Node, an asset server, a CDN or a second model. Your browser renders the scene. A laptop viewing Spark's web page renders it on the laptop, not on the model-serving Spark.

## A quick walkthrough

1. Open the demo. Five robots move around their workstations. Click an agent or the name bar to inspect its persona, skills, current task and access.
2. Choose **Create your agent**, change its identity and equip skills. **Join the BaC crew** places it in one of the existing roles. Return to the campus to see the updated robot label and passport.
3. **Run the crew** starts the current form's brief (Zurich / English by default). Handoffs carry a small document from one role's workstation toward another. The evidence feed and phase strip come from the same planner state.
4. At the default resource shortage, choose more event time or pending extra equipment. The shared brief and marketing assumptions update. Autoplay resumes after that decision.
5. At the delivery gate, explicitly simulate approval or keep drafts local. Neither action sends a real message. Autoplay never grants this decision.
6. Open the C progress board, then use **A · 3D campus** to come back. Inspect shared deliverables to see the generated planning templates.
7. Try **Data analyst** with your own `topic,attendees` CSV, or **Poster studio** with the current brief. Download the actual Markdown report or PNG.

## What the visuals mean

| Element | What drives it |
|---|---|
| Idle robots | Ambient walking, not background agent execution |
| Robot carrying a document | Current phase in the scripted planner |
| Shared-brief hub | A visual symbol of the one browser's shared state, not a live inference meter |
| Agent passport and status | Current role, persona, skills and planning task |
| Amber access gate / decision | Simulated policy boundary; no OpenShell enforcement |
| Evidence feed | Planner transitions and completed browser skill runs |
| One Spark / one model note | Intended shared inference architecture; current UI is not connected |

The scene does not claim to be an Omniverse application or an official NVIDIA UI component. Its synthetic miniature workspace and poster layout were built for this demo.

## Controls and browser support

- Drag the scene to orbit; scroll over it to zoom; the crosshair resets the camera.
- Pause scene motion separately from crew autoplay. The operating system's reduced-motion preference disables ambient animation by default.
- Rendering is capped near 30 FPS, pixel ratio at 1.6, and stops when the tab or scene is hidden. The scene uses one WebGL renderer.
- WebGL2 is required for 3D. If unavailable or the context is lost, a visible message explains the fallback; agent selection, planning controls and the progress board remain usable.
- State is per browser tab and resets on refresh. There is no persisted run, attendee isolation backend or actual multi-agent execution yet.
- CSV input is limited to 64 KB / 500 rows and two named columns. Values must be nonnegative whole numbers. It is parsed locally, with no evaluation or upload.
- The poster is deterministic Canvas output, not generated model imagery. Event dates, detailed venue and registration remain unconfirmed.

## Implementation

`src/campus.js` consumes `window.BacDemo.snapshot()` and the `bac:crew-state` browser event. It invokes the same form and workflow actions as the board. All permissions are still prototype UI state. A future backend should replace that source of events with actual task, tool, approval and artifact records.

`src/vendor/three-r180.cjs` is the upstream r180 CommonJS build (one indentation-only fix), wrapped locally during `scripts/build.py`; its MIT license is retained in `src/vendor/three-LICENSE.txt`. The generated HTML is about 2 MB and contains all scene code. `src/skill-tools.js` contains the local tools. No additional packages are installed during normal app updates.

Validation: macOS Chrome, including WebGL movement, pause, board state consistency, both decision stops, CSV upload/report downloads, PNG dimensions, stale result invalidation, mobile layout, reduced motion and WebGL failure fallback. Real Spark browser and GPU serving validation remain outstanding.

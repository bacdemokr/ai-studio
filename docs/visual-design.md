# NVIDIA-inspired demo styling

This prototype uses a local theme informed by the public [NVIDIA Build interface](https://build.nvidia.com/), inspected on September 19, 2026. It is a custom theme, not an installation of the Kaizen component library.

## Applied choices

- A near-black canvas with distinct neutral-gray panels and input surfaces.
- NVIDIA green (`#76b900`) on primary actions, selected tabs, active missions and completed execution steps.
- White headings, readable gray supporting text and amber for blocked requests or pending decisions.
- Small, consistent corner radii, thin borders and simple line icons.
- A shared treatment across the skill playground, agent onboarding, Agent campus, Mission control and artifacts.
- Robot characters with graphite bodies and green eyes, preserving the approachable agent identities.
- A fixed dark appearance so the demo is consistent across host OS themes.

The font stack uses locally available NVIDIA Sans, then Arial, Helvetica and a generic sans-serif. No font files, icon libraries or remote styling dependencies are required. The header currently renders the NVIDIA name as text.

## Editing

`src/nvidia-theme.css` contains the shared theme. It is embedded after the layout styles by `scripts/build.py`, keeping the standalone preview offline. The simple skill icons are inline SVG in `src/playground.js`.

After making a change, run `python3 scripts/build.py`. Inspect Agent campus and Mission control, onboarding and the playground at desktop and mobile widths. Color alone should not convey a task's state; retain the existing status labels and access explanations.

The main experience uses a bundled Three.js workshop with a rectangular exhibition floor, five individual workbenches, small robot specialists and a central shared-brief hub. The existing carbon-and-green panels remain. Role colors, restrained desk lighting and moving document packets make responsibilities and handoffs visible. Idle movement is ambient; active lighting and transfers follow app-observed task states. The skill buttons connect the furniture to the actual Studio experiences. The renderer runs locally in the browser and requires no CDN.

## Crew views

Agent campus emphasizes agent identity and Mission control emphasizes task status. They use the same theme and shared run state.

![Agent campus — miniature workshop](agent-studio.png)

The same underlying job state also drives Mission control. See the [runtime guide](live-studio.md) for the live execution contract.

---
name: bac-builder
description: Build small desktop web prototypes with a short implementation and verification cycle.
---

Use this skill for building or changing code. For greetings, explanations or planning questions, answer directly without creating a file.

Create the smallest useful version of the requested app or game. Preserve the user's requirements and your own voice. When Casey assigns work, follow the assignment, acceptance criteria and required output paths; use the supplied research rather than repeating it.

Default to one self-contained HTML file in artifacts/ with inline CSS and JavaScript. Use no external libraries, network requests or external images. Target desktop keyboard and mouse interaction. Skip mobile layouts, touch controls, installation, deployment, elaborate animations and extra features unless explicitly requested and supported by your tools.

For held-key controls, track independent key states so simultaneous inputs work. Clear those states on keyup, window blur, page hiding and restart, so controls cannot remain pressed when focus leaves the preview. Keep the requested key mapping and show it beside the game.

For a game with collisions, trace an approaching object on each side: a hit must send it away from the surface, while a miss can change the score. Check both velocity signs and reset state, not just whether the object animates.

Keep source compact: use shared data and reusable functions instead of repeating large HTML blocks. Read only relevant inputs and existing source. For a new page, write a complete usable first version, not a skeleton requiring many edits. For a follow-up, update the same file with targeted edits and preserve unrelated behavior.

Make one focused static check of the main interaction and the requested acceptance criteria while composing. After a successful save, return unless a concrete defect or missing requirement needs a fix. Do not reread merely to confirm that saving succeeded. Fix concrete errors; do not rewrite working code for style, repeatedly reread the file, or ask for optional review. Stop after the required behavior and saved handoff are complete. Honor Casey's narrower task budget.

Use real write/edit tools to create the file. If writes are unavailable in a direct conversation, provide one complete HTML code block and state that it was not saved. A code block is not a saved specialist handoff. Do not claim execution, browser tests or deployment without tool evidence; writing source code does not grant command execution.

Return a short receipt, under 80 words, with what was built, its saved path and any material limitation. This receipt limit does not limit the code or required functionality. Never claim features or checks that were not completed.

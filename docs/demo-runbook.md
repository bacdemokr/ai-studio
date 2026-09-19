# A useful agent you can see — presenter runbook

## Before attendees arrive

Start the chosen model, OpenClaw and app. Check `./bac llm check` and `./bac runtime check`. Keep one model active across all agents. Connect optional Telegram/search credentials yourself; never bake them into an image. If using OpenShell, run a real mission and inspect the actual sandbox before describing it as enforced.

Open Agent Studio in a fresh browser profile. Confirm WebGL movement, no horizontal overflow, and a green runtime indicator. Inference latency depends on the selected model and hardware; do a timed rehearsal on the actual Spark. Keep the separate, visibly labeled Workflow rehearsal available for a service outage.

## 0–2 minutes: a teammate with a personality

Open **Hiring**. Ask the attendee to choose Classic, Orbit or Rover, pick a color and accessory, name their agent and choose Helper, Creator or Researcher. Choose a tone and answer length separately. Compare Kind with Cynical, then Brief with Detailed in the sample reply. Under **What should your agent help you with?**, choose concrete abilities such as reading documents or building small apps. These are reusable skills; the working style itself does not grant tools. Creating the agent opens **Agent lounge**, where one robot appears per saved agent. Its appearance and identity survive refreshes. Create another teammate to show the room growing; click either robot to open its own conversation and workspace. Explain that a persona changes how the agent approaches work; a skill supplies reusable instructions, and tool access is checked separately.

## 2–5 minutes: a visible, useful result

In **Agent lounge**, choose **Make something playable**. Request a tiny reaction-time game, wait for the real agent response, and open the saved HTML. Play it. The result is a file, not an animation of an imagined task. If generation fails, show the actual error and a local tool or a labeled rehearsal; do not claim a fallback is a live success.

Alternative: choose **Ask your documents**, add the sample brief or your own .txt/.md/.csv, and ask for an answer with filename evidence. Or choose **Plan around the weather** for a current observation and source.

## 5–7 minutes: memory and continuity

Ask the agent to remember a preference. Open Memory to inspect the actual file, refresh, and ask what it remembers. If Telegram was configured, pair the participant’s private chat and ask the same question there. Web and phone use the same OpenClaw session, not two bots pretending to remember.

## 7–13 minutes: why several agents?

Click **Create an agent** to add a second teammate with a different persona and skill loadout. Switch back and forth to show separate memory and files. Open **BaC mission room**, then launch a BaC in Zurich, Europe / EMEA, in English. Let the attendee change attendance, duration and group/session sizes. The preset Milo-led crew is ready without personal onboarding or OpenShell. For this custom exercise, check **Let … lead instead of Milo**; the selected agent becomes event lead. Assign the new teammate to one of the four specialist roles; leave the rest at their ready-made defaults. With the default crew, Nova designs the participant experience; Atlas explains deterministic device/staff counts; Momo uses those outputs for invitation copy; Pico reviews the combined plan.

Open **3D crew** to see personalities and movement. Switch to Mission control to inspect dependencies and completed deliverables. Deliberately enter too few devices. The server stops before marketing; the attendee can plan additional equipment (still unconfirmed) or cancel and revise the brief. The review calls out missing dates/venue/registration links.

Explain the value in concrete terms: each role has a clear responsibility, its own context, and an output another role can inspect. The reviewer can catch inconsistencies. A single short task does not need a crew; a coordinated plan benefits from explicit dependencies. This implementation runs sequentially on one LLM, so it does not promise faster execution from concurrency.

## 13–15 minutes: make it their own

Edit persona/skills after the mission finishes. Schedule a one-minute follow-up; the queue survives refresh. Download the final plan, mini app or report. No invitation email is sent from the demo. Optional browser voice playback reads the answer; this is browser speech, not a separate voice model.

## Presentation boundaries

Keep the dark NVIDIA-inspired shell and familiar panel layout. Hiring contains a large character preview and OpenClaw connection details; Agent lounge contains only the attendee’s saved agents; Mission room contains the five specialist stations and Mission control. Personal agents keep their appearance when assigned to crew roles. For the spatial experience, click the 3D view and press Enter, double-click an empty area, or use Full screen. The side panel hides and the 3D room fills the display. Esc or Exit full screen restores the studio; the camera and running work are preserved. Hotspot dialogs remain usable in fullscreen, and selecting a personal skill returns to the mission composer. Character wandering is ambient when idle; movement toward a station represents an observed task state. The evidence panel contains app events and actual files, not a fine-grained tool trace or hidden reasoning.

OpenClaw owns agent execution, identity, skills, tool use and conversation state. The BaC app owns onboarding, the shared brief, role orchestration, scheduling and UI. OpenShell is an opt-in execution sandbox for personal agents, while the preset crew stays outside it. Open **Policies** to demonstrate a denied weather request, approval of only the weather API, successful retry, and revocation. Check the actual loaded policy and access logs, separately from approval history; an application approval is not proof of an OpenShell policy boundary.

## Add a security and recovery segment

Open **Inspect shared state** during a crew mission. Show the actual received brief, completed prior-role outputs, timestamps and files. This is the concrete reason for several roles: Momo drafts from a plan resolved by other specialists, and Pico sees the complete package.

For a five-minute security segment, click **Access gate**. In **Try the concept**, let the attendee attempt the request, propose a narrow operator permission, retry and test a different destination. Keep the illustrative label visible. Switch to **Inspect host evidence** and show a capture from `./bac openshell prove`, if the operator has run it. Explain that the timestamped result belongs to a dedicated proof sandbox. Then inspect a real agent sandbox on the host before making claims about its enforcement. Do not claim host-side web tools automatically run inside that sandbox.

Demonstrate **Stop after active call**: the pending model request may finish, but the next role does not start. Reset while running must visibly refuse; after completion, **Reset mission board** preserves the selected agent’s memory and files; the other agents’ boards stay unchanged. Use **Help & fallback** to show an error, download its evidence, enter a labeled fallback or retry deliberately.

Before the event, complete the [requirements and fault checks](cohort-requirements.md), especially real Spark inference and OpenShell enforcement.

If the event includes NeMoReef, the facilitator can explain the two experiences: this Studio focuses on personal onboarding, useful skills and visible crew handoffs; the supplied NeMoReef brief emphasizes persistent assignments, orchestration and policy/failure recovery. Confirm the event’s available demos before directing attendees to another station. This guidance is part of the presenter runbook.

## Show the connected studio

In Hiring, point out the two lit doorways: one into Agent lounge and one directly into BaC mission room. Use **See the whole studio** to show the L-shaped floor plan: lounge at upper left, BaC at upper right, onboarding below the lounge. The third corridor bends around the open courtyard, completing a loop. Visit all three rooms through their doorways; no intermediate room is required. The small studio map uses the same layout. Enter fullscreen and use the doorways or the small map to move without leaving it. Draft names, appearance, selected agents and their work stay intact as you travel. Policies remains a separate control panel. For motion-sensitive attendees, the browser’s reduced-motion preference makes the camera changes immediate.

In BaC mission room, click Atlas or another robot to inspect it in the right-hand panel. Selection does not open a modal or scroll the page. Show the role, persona, equipped skills and the previous/next handoff partners; after a role delivers, expand its actual saved output in the panel. In fullscreen, selecting a robot docks the same panel beside the world. Close the panel to return to the full-width scene.

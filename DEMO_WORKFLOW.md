# Demo workflow: what, why, and how
Updated October 10, 2026

## Understanding the workflow and its objectives

### Demo objectives

- **Create an agent**
  - Depending on the audience's level of knowledge, explain what an agent is and how its identity, character, purpose, and skills define it.
  - Show that an agent can operate either directly or within an [OpenShell](https://build.nvidia.com/openshell)-controlled environment.
- **Work with or without [OpenShell](https://build.nvidia.com/openshell) in Stages 1 and 2**
  - The demo currently uses [OpenClaw](https://openclaw.ai/). Explain what it is and why an agent harness matters. Other solutions include Hermes, NanoClaw, and Manus.
  - At a high level, these tools turn natural-language instructions into multi-step actions across files, applications, and services. They may use self-hosted infrastructure or a managed platform.
  - [OpenShell](https://build.nvidia.com/openshell) adds an external runtime boundary that governs what an agent can access and do.
- **Explore a multi-agent system**
  - Use several scenarios to show how an orchestrator delegates parts of a task to specialized agents.
  - This demo includes predefined agents for tasks such as web research, creating a polished visual result, and reviewing the output.
  - The objective is not to provide every possible agent or support every possible scenario. The goal is to demonstrate representative multi-agent workflows.

### Audience

The audience may range from beginners and students to technical experts and C-level executives. Adapt both the message and the depth of the demonstration accordingly.

Use the room guides for a short introduction. For more detail, open **Instructions** to inspect AGENTS.md, IDENTITY.md and SOUL.md, or **Usage & time** after a Stage 3 run. These are optional views, not separate attendee modes.

For experts, use the demo as a starting point for discussion. Listen to their requirements and learn what capabilities they are looking for.

The key objectives are:

1. Explain what an agent is, including its profile, identity, skills, and runtime controls.
2. Demonstrate live agent behavior with and without sandboxing or protection.
   - Compare direct access to an external website with [OpenShell](https://build.nvidia.com/openshell)-controlled access.
   - Show an initially blocked request, approve the specific website, and retry the request successfully.

## 1. The different stages

### Stage 1. Hiring

**Target:** Explain how to create an agent and introduce:

- The available visual styles and profiles
- The agent's purpose and identity
- The skills assigned to the agent
- Whether the agent operates with or without [OpenShell](https://build.nvidia.com/openshell)

### Stage 2. Agent Lounge

Use manual chat for task-driven skills. An agent with **Tech Radar** instead runs Heartbeat, even when other skills are equipped. Its first check waits at least 10 seconds; busy model queues can delay summaries. Pause stops future checks; remove the skill to restore manual chat.

**Target:** Demonstrate how an individual agent performs a task and how [OpenShell](https://build.nvidia.com/openshell) changes its access to external resources.

One approach is to ask an agent without [OpenShell](https://build.nvidia.com/openshell) to perform an action that requires web access, then ask an agent with [OpenShell](https://build.nvidia.com/openshell) enabled to perform the same action.

An alternative workflow is:

1. Use an agent protected by [OpenShell](https://build.nvidia.com/openshell) and ask it to perform a task that requires internet access.
2. Observe that access to the requested website is initially blocked.
3. Authorize access to that specific website.
4. Ask the agent to retry the same task.

The objective is to explain [OpenShell](https://build.nvidia.com/openshell) and show how it sandboxes the agent's environment while allowing explicitly approved access.

### Stage 3. Multi-agent work

**Target:** Show how a multi-agent team works toward a task or goal that requires different specialist skills.

This is similar to building a house:

- The lead agent is the orchestrator and the user's main point of contact.
- The orchestrator identifies the specialists needed and plans the work required to reach the goal.
- One specialist may understand the overall construction process.
- Another may specialize in walls and structural work.
- Another may focus on energy efficiency.
- Another may create a functional and attractive interior design.

Similarly, each agent has specialized skills that help it produce the best possible contribution in its area of responsibility.

Stage 3 has two separate workflows:

- **3-1 Event Brief:** Riley coordinates the fixed team of Dylan, Alex and Morgan. The application runs the event workflow; demo research and operations can run in parallel after Riley's brief. All team members use the model selected for this scenario's connection.
- **3-2 Open Task:** Casey coordinates the selected team. Choose **Hired only** (default, Casey plus your hires, no built-in specialists) or **Hired + Standby** (prefer your hires with built-in backups). Name an agent to require its actual participation, e.g. `/goal Let Pixel do the coding. Build a counter page.`

Event Brief keeps its own fixed agents, conversations and files. In both team modes, idle hired agents follow you into Open Task and sit on waiting benches. Selected specialists move to workbenches, then return to waiting seats while you remain in the room. Leaving the room sends idle visitors back; ongoing assignments continue. Movement alone never runs a model request. Busy agents remain with their existing work.

Casey always coordinates using the Open Task connection. Hires retain their identity, persona, skills, policy and selected model. Already-selected specialists do not receive duplicate reaction calls; other available hires may react. The team selector is locked during a task; a reload or Open Task reset defaults new tasks to Hired only. Hired-only requests with no available hires are blocked with guidance; invalid built-in assignments are repaired once before dispatch, then stopped if still invalid.

For a simple hired-only demo, create a **Web researcher** and a **Programmer** in Hiring. Their visible **Web research** and **Coding** skills provide bounded research and small desktop prototypes. These are instructions plus the existing tool permissions, not a general browser or code execution environment. Ask Casey: `/goal Have Orbit research three places in Barcelona using official sources, then have Pixel create a small interactive travel page from the saved findings.`

For a fresh demonstration, reset Open Task before choosing the next team. Reset is optional between completed tasks; switching the toggle alone keeps earlier conversations and results. After stopping active work, wait for the current call to finish before starting again.

## 2. Before presenting

- Connect Local and/or External Endpoint in **Settings > Model**. Under **Models**, choose the **Event Brief** and **Open Task** connections independently. New hired agents default to connected Local, otherwise the configured External Endpoint model. To choose another model, expand **Model** below **OpenShell protection** during Hiring or in **Edit agent**. Earlier agents without an individual choice retain their shared default; built-in teams prefer External Endpoint by default; each selector shows the connection currently used.
- Rehearse the selected request on the actual model and hardware. Endpoint timings in the examples are observed runs, not local Spark benchmarks or guaranteed completion times.
- For an offline rehearsal, select Local and try Event Brief with Riley, Alex and Morgan (omit Dylan’s live research), or the store-email / ping-pong Open Task examples without external sources. Web research, live weather and Telegram still need internet. The email example does not demonstrate enforced filesystem blocking; that remains separate work.
- **Files** shows uploads/results for the selected agent only and is hidden when empty. Definition files use **Instructions → Copy**; result files support preview/download.
- **Usage & time** shows recorded tokens, elapsed time and agent turns after a Stage 3 run. Agent time includes tools; summed time can exceed elapsed time when turns overlap. It is not a provider billing report.
- `./bac start` clears runtime data and starts fresh. Use `./bac start --keep-data` to retain a rehearsal. `./bac stop --all` stops the demo and its managed local model, then removes the Compose stack and its data volumes.
- Keep the demo tab open to retain its session. After 60 minutes disconnected, its agents and results are automatically cleared once active work finishes. A preserving restart gives the browser 60 minutes to reconnect.
- One browser session can present at a time. To switch browser or device, close the existing demo tabs and select **Try again** on the new screen. If the previous browser crashed, allow 90 seconds for access to release; any running task must also finish.


## Scenario ideas in [README_POSSIBLESCENARIOS.md](README_POSSIBLESCENARIOS.md)

### Audiences and objectives

**Note:** These ideas are not ranked, and one is not better or necessarily more complex than another. Their purpose is to show how a virtual coworker or AI agent can help with different types of tasks.

- **Basic and accessible to anyone: plan a trip**
  - **Audience:** Anyone who wants help planning a personal trip.
  - **Objective:** Demonstrate a non-work-related task that primarily involves web research and the creation of a polished result, such as an HTML travel plan.

- **Coding practitioners: development or monitoring**
  - **Audience:** Developers investigating a technical topic and IT operations teams monitoring systems or services.
  - **Objective:** Demonstrate a work-related task that identifies how to solve a technical issue or determines the steps needed to implement a solution. Use drone research for public-source analysis or ping-pong for a compact coding example. Do not present a generated game or a static review as proof of execution testing.

- **Decision-makers and managers: monitoring, decision support, and work preparation**
  - **Audience:** Managers and other decision-makers who need to understand the current state of a topic and potentially decide what to do next.
  - **Objective:** Demonstrate a virtual personal assistant that summarizes recent developments in a chosen field, such as finance, research, or global news.
  - **Alternative objective:** Review an ongoing discussion using emails, messages, and documents; compare developments year over year; identify what went wrong; and recommend changes.

For exact controls, recovery steps and model-budget explanations, use the [presenter runbook](docs/demo-runbook.md).

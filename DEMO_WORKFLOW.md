# Demo workflow: what, why, and how
October 7, 2026

## Understanding the workflow and its objectives

### Demo objectives (version xxx)

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

Each stage provides several ways to explain the underlying concepts. The visual experience makes the demo approachable and attracts attention, while the configuration, prompts, and agent definitions provide additional detail for technical audiences.

For experts, use the demo as a starting point for discussion. Listen to their requirements and learn what capabilities they are looking for.

The key objectives are:

1. Explain what an agent is, including its profile, identity, skills, and runtime controls.
2. Demonstrate live agent behavior with and without sandboxing or protection.
   - Compare direct access to an external website with [OpenShell](https://build.nvidia.com/openshell)-controlled access.
   - Show an initially blocked request, approve the specific website, and retry the request successfully.

## 1. The different stages

### 1.a. Hiring

**Target:** Explain how to create an agent and introduce:

- The available visual styles and profiles
- The agent's purpose and identity
- The skills assigned to the agent
- Whether the agent operates with or without [OpenShell](https://build.nvidia.com/openshell)

### 1.b. Agent Lounge

**Target:** Demonstrate how an individual agent performs a task and how [OpenShell](https://build.nvidia.com/openshell) changes its access to external resources.

One approach is to ask an agent without [OpenShell](https://build.nvidia.com/openshell) to perform an action that requires web access, then ask an agent with [OpenShell](https://build.nvidia.com/openshell) enabled to perform the same action.

An alternative workflow is:

1. Use an agent protected by [OpenShell](https://build.nvidia.com/openshell) and ask it to perform a task that requires internet access.
2. Observe that access to the requested website is initially blocked.
3. Authorize access to that specific website.
4. Ask the agent to retry the same task.

The objective is to explain [OpenShell](https://build.nvidia.com/openshell) and show how it sandboxes the agent's environment while allowing explicitly approved access.

### 1.c. Events — multi-agent work

**Target:** Show how a multi-agent team works toward a task or goal that requires different specialist skills.

This is similar to building a house:

- The lead agent is the orchestrator and the user's main point of contact.
- The orchestrator identifies the specialists needed and plans the work required to reach the goal.
- One specialist may understand the overall construction process.
- Another may specialize in walls and structural work.
- Another may focus on energy efficiency.
- Another may create a functional and attractive interior design.

Similarly, each agent has specialized skills that help it produce the best possible contribution in its area of responsibility.

The orchestrator plans the work, selects the appropriate specialists, assigns their tasks, coordinates their contributions, and combines the results to achieve the overall goal.

## 2. Stage 1: Create your agent

## 3. Stage 2: Test agents with and without runtime controls

## 4. Stage 3: Explore a multi-agent workflow
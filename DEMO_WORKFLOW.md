# Workflow and what to do in the demo: what, why and how
October 7, 2026

## understanding the worflow and the targetS ##

### Targets of this demo (version xxx)

- creating an 'Agent'
-- depending on the audiance 'knowledge', it may make sense or not to come back on the topic: creating an agent, with some IDENTIDY/SOULD/etc.., which skills linked ot it...is it under control or not (Openshell)
- with or without 'Openshell' [stage 1 and 2]
-- demo is currently relying on 'openclaw' [https://openclaw.ai/], need to know what is it about, why important (other solutions: Hermes, Nanoclaw, Manus...to be updated BUT the important is to understand the basic: * These tools are AI agents that turn natural-language instructions into multi-step actions across files, apps, and services, either through self-hosted infrastructure or a managed platform*)
-- Openshell is there to 'protect' those (openClaw and Hermess) agent harnesses
- what is it about working a multi-agent system and what could we could do with (examples and attendee's idea)
-- different scenarios. Somehow the 'orchestrator' is requiring different 'sub-agents' to perform a task. In this demo, some agents with some skills are already pre-defined, like 'web-searching', 'creating a nice UI output', 'double checking the output', etc...Note that we can not extend (and don't target!!!) to have a list of any kind of possible agents, fullfilling any kind of scenarios. This is not the target (and the world is wide). Point is to showcase some workflow

### the audience

from beginners to expert, from students still learning to CXX people...we need to adapt our message and the demo.

that's why, in every stage, we can bring different elements to showcase what it is about.

To say, nice visual demo (for beginners and to attract people to look into the demo), but then some access to some more 'what is behind the scene' configuration/prompt/configuration.

For experts : even though we could build and try...let's for now listen as well what the 'market' is looking into...

Targets are :
1. what is an agent ('profile', 'skills', controlled or not (openshell))
2. Try out 'live' with or without a 'sandbox/protection' [to mention: sandbox is not yet, as of today, a common understanding]
-- try reaching one external [WWWeb] endpoint with or without OR withoug having access and then after, after accepting, having access





## 1. The different stages

### 1.a. Hiring

**Target:** Present how to create an agent and introduce:

- The available visual styles and profiles
- The agent's purpose and identity
- The skills assigned to the agent
- Whether the agent operates with or without OpenShell

### 1.b. Agent Lounge

**Target:** Demonstrate how an individual agent performs a task and how OpenShell changes its access to external resources.

One approach is to ask an agent without OpenShell to perform an action that requires access to the web, then ask an agent with OpenShell enabled to perform the same action.

An alternative workflow is:

1. Use an agent protected by OpenShell and ask it to perform a task requiring internet access.
2. Observe that access to the requested website is initially blocked.
3. Authorize access to that website.
4. Ask the agent to retry the same task.

The objective is to explain OpenShell and show how it provides sandboxing for the agent's environment while allowing explicitly approved access.

### 1.c. Events — multi-agent work

**Target:** Show how a multi-agent team works toward a task or goal that requires agents with different specialist skills.

This is similar to building a house:

- The leader, the guy you talk to directly, is the 'orchestrator' of the full job and ensure the right delivery
-- first part of his work is to 'hire' the right 'agent' and 'plan' the job to reach the 'goal'
-- then later, some other agents are called, example :
-- One expert understands the full work and how to build it.
-- Another specializes in the walls and structure.
-- Another focuses on energy efficiency.
-- Another creates a functional and attractive interior design.

In the same way, each agent has specialized skills that helps it produce the best possible contribution for its area of responsibility.

The team also needs an orchestrator. This agent plans the work, selects the right specialists, assigns the right tasks, coordinates their contributions, and brings the results together to achieve the overall goal.

## 2. STAGE 1: Creating your Agent
## 3. STAGE 2: Testing the Agents, with or without 'control'
## 4. Stage 3: testing a multi-agent workflow
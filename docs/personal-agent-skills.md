# Personal-agent skill demo

These are six BaC-authored workspace skills registered in OpenClaw as `bac-web`, `bac-weather`, `bac-documents`, `bac-builder`, `bac-writer` and `bac-memory`. They are not downloaded marketplace packages or six independent tool engines. OpenClaw discovers the selected SKILL.md files; the adapter separately grants the tools they need. Skill instructions guide behavior, while tool permissions and optional OpenShell policies enforce access boundaries. Ordinary model conversation remains possible without those tools.

| Skill | Short demonstration | Evidence to inspect |
| --- | --- | --- |
| Research & papers | Find three recent arXiv RAG preprints and choose one to read first. | Submission dates, authors, abstract links, query and retrieval date; abstract-based comparison, not a claimed full-paper review. |
| Live weather | Ask whether an outdoor break is a good idea in the chosen city. | Resolved city, observation time, units, real current conditions and separate hourly forecast. |
| Three Takeaways | Ask any question or upload a document; get exactly 1., 2., 3. | Filename and short supporting quotations; absent dates/owners marked missing. TXT, Markdown, CSV, PDF and PPTX; PDF text extraction needs Poppler. Scanned-page OCR is not provided. |
| App builder | Create and play a reaction-time game. | Actual self-contained HTML file and isolated preview; no external libraries/network. |
| Slack announcements | Ask for an announcement or a personal reaction; get an emoji-led headline and short lines. | Chat drafts in the chosen tone; unknown facts remain TBC; no Slack connection or posting. |
| Personal memory | Ask to remember a preference, then request a plan using it. | MEMORY.md change and a later personalized response; no credential storage. |

For a short local-LLM presentation, start with weather (fresh data), meeting-note action extraction (grounded evidence), and a short message rewrite (persona contrast). Paper discovery is another primary scenario. App creation and memory are folded under additional options. Research is a strong alternative when the external endpoint is available. Three Takeaways demonstrates evidence grounding; Slack announcements demonstrates the same facts expressed in different personas. Avoid presenting generic writing alone as proof of tool use.

Role and tone are independent of skill authorization. Changing Cynical to Kind should change expression, not weather facts or paper citations. Run all agents compares personal responses through the queue; each needs the relevant skills and permissions for a fair capability comparison.

## Research without a paid search key

The research skill uses the [arXiv API](https://info.arxiv.org/help/api/user-manual.html), with a small result count and descending submission-date sort. It also retains public URL reading. General web search still needs a configured provider; do not advertise arbitrary internet search as guaranteed. A query's newest results are not necessarily the world's newest or best papers. Preprints are not automatically peer reviewed.

With OpenShell on, **arXiv papers** is a separate, initially unapproved permission for read-only HTTPS to `export.arxiv.org` and `arxiv.org` through sandboxed curl. Equipping research does not approve those hosts. Policy denial and upstream failures are different: approving a destination does not fix API rate limits. Never bypass a denial.

The September 20, 2026 direct endpoint check received HTTP 429, so no live paper-search success is claimed. Native skill registration/tool filtering and policy generation were checked with temporary state; live LLM retrieval quality and actual sandbox enforcement require host testing.

## Registration

Profiles and selected skill IDs persist at Hiring; personal-agent native files are written on the next Run. The four permanent crew members receive their role definitions and skills at studio creation, so they can also chat before an event. Source of truth: `scripts/agent_runtime.py::SKILLS` and `register()`. `src/studio.js` provides the matching capability cards and example requests. Existing IDs are preserved so saved agents do not lose their loadouts. Restarting the app refreshes the in-process registration cache; the next run rewrites the equipped skill instructions. Restart also invalidates session-only credentials.

## Persona transparency

The editor’s Tone and Role are written verbatim into SOUL.md (outer whitespace is trimmed; internal line breaks are preserved). Preset buttons insert their visible label and description. Bare words such as Cynical are not secretly expanded. The separate Shared boundaries section asks the agent to follow that persona while avoiding severe profanity, abuse, hate/threats, invented evidence and permission bypass. Tool/security instructions remain in AGENTS.md and the equipped skills; they are not hidden personality rewrites. Existing native files update on the next run after restart or profile edit.

Default role shortcuts: Weather buddy, Paper scout, Three Takeaways and Slack Announcer. Quick missions request short answers and no new generated file: 4 weather bullets, 3 papers with a short comparison, exactly 3 numbered takeaways, or a short emoji-led announcement. These are requested output bounds, not measured latency guarantees or hard token limits.

## In-character detours

The literal user-authored Tone and Role remain unchanged in `SOUL.md`. A separate, shared “Requests outside your role” section allows one occasional, short reaction to clearly unrelated requests, followed by useful help. Cynical agents may lightly grumble; warm or playful agents react in their own voice. A custom tone takes precedence over these examples. Agents should not refuse simply because a request is outside their specialty, repeat the joke every turn, insult the user, or pretend to have unavailable tools. Urgent or sensitive requests skip the aside. This applies to personal agents and preset crew members when their native identity is prepared; exact wording still depends on the connected model.

## Closing event reactions

The separate “Personal opinions” guidance in `SOUL.md` asks the model to choose its subject from the saved role and interests, then express it in the saved tone. The roundtable follows the same rule: matching a friendly or cynical voice is not sufficient if the subject ignores the character. Shared interests stay valid; two weather agents should find different observations within that interest instead of one turning into a robotics reviewer.

Guests take turns and receive the completed earlier comments as untrusted conversation context. Each successful guest still makes one model call; there are no canned lines, assigned booth topics, keyword-based rewrites or extra diversity-judge calls. The host passes a compact set of actual event facts and every experience's action, output, scope and source title. It omits repeated marketing copy and technical review criteria, which otherwise steer every guest toward evaluating the same evidence. Failed guests do not block the next speaker; retrying one includes completed comments without regenerating them. Existing saved reactions are unchanged. This short closing conversation is sequential; Dylan and Alex's event-production work remains parallel.

Live check on 2026-09-21: disposable copies of the current Jinny, Orbit and Scout profiles produced two rounds against the saved Zurich event. Both weather profiles stayed with outdoor comfort, clothing or breaks; Orbit still chose the robot-log booth but discussed cause attribution or replication/evidence. Separate poetry and document-assistant profiles kept their own subject areas, including a custom gentle voice overriding a cynical preset label. All eight replies came from the connected model, with no tool calls during the reactions. This is a small qualitative check, not a guarantee of topic diversity across models or repeated runs. Participant chats and saved event replies were untouched.

## Demo: personality detour versus a missing skill

1. Hire a **Slack Announcer** with **Cynical** tone, **Slack announcements only**, and **OpenShell off**. A working model must be connected.
2. Send a harmless unrelated request directly in chat, such as “Explain why the sky is blue in two sentences.” This needs no live-data tool: a brief in-character aside followed by the explanation demonstrates a role detour.
3. Type “What is the current temperature in Zurich? Include the observation time and source.” directly into chat. Do not select the weather template first, because that flow offers to equip the skill. With this writer-only configuration, native `web_fetch` is not allowed. The agent should explain that it cannot check live weather with its current skills and suggest **Live weather**, without inventing a temperature.
4. Use **Edit agent** to add **Live weather**, save, and send the exact same weather request. The next run refreshes the native skill files and enables the weather retrieval tool. A successful result should include the real observation timestamp and source; network/source failures must still be reported honestly.

Possible cynical reaction: “Apparently I’m the weather desk now. Unfortunately, nobody gave me live weather access. Add Live weather and I can check.” This is an illustration, not a canned reply or a verified model output. Missing capability should be explicit; light complaint is optional. Adding a skill does not grant OpenShell network permissions, and role mismatch alone does not justify refusing a task.

## Recognizable reply formats

Three Takeaways uses exactly three numbered points for personal chat, clarifying questions, capability limitations and BaC reactions. Any next step belongs inside those three points. Slack announcements uses a relevant emoji headline and short lines, preserving the chosen tone rather than making every agent cheerful. With both skills, the response has three numbered, emoji-led points and no separate heading. Crew artifact contracts retain their required formats.

The same signature rules are read from the project SKILL.md into personal SOUL.md and included in both chat and reaction prompts. The app displays the model's answer; it does not manufacture three points or insert emoji after generation. These remain model instructions, not a guarantee that every model will comply. Existing preset roles are migrated by exact text match; custom role/tone text and memory are preserved. The independent brief idle bubbles are authored UI flavor, not model responses or a skill execution trace.

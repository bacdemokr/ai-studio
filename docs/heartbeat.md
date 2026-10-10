# Tech Radar and Telegram

1. Add the **Tech Radar skill** to any personal agent in Hiring or Edit agent. The Tech Radar preset is a shortcut; the skill controls Heartbeat.
2. Connect the model. No upload or chat prompt is needed.
3. OpenClaw checks every **20 seconds** for an unread article from NVIDIA Developer Blog or Hugging Face Blog. A completed summary includes the source link.
4. Use **Pause / Resume** in the agent panel.

The first check cannot start during the first 20 seconds after hiring or changing the agent's skills. Runtime preparation or the native scheduler can delay it further. Suggested feed hosts do not produce policy alerts before an access request; actual denials appear when OpenShell blocks a request.

While this skill is equipped, manual chat, attachments and scheduled follow-ups are disabled, and Run all agents excludes the agent. This applies even with additional skills or while Heartbeat is paused. Remove the Tech Radar skill to restore manual chat.

Older feed entries are eligible: the agent discovers useful reading rather than waiting for newly published posts. Each short summary has a source link and publication date, and follows the chosen persona. The source evidence is the feed excerpt, not a full article review. Politics, investing, earnings and personnel announcements are excluded using a preliminary filter and agent judgment.

Shared URLs and skipped items are remembered in the agent workspace across restarts. The agent stays quiet when it exhausts the available relevant feed entries; it does not repeat old summaries or invent news. Feed changes are checked with conditional caching. Removing the agent removes its discovery history.

20 seconds is the native heartbeat cadence, not a response deadline. Model calls and ongoing tasks may delay an update. Checks pause while the model is disconnected, the agent is assigned other work, or its owning browser session is disconnected. Authenticated browser activity renews a 90-second lease, including for keyless local models. Closing the last tab ends its lease; a lost close signal expires within 90 seconds plus the relay check interval. Other browser sessions cannot keep this session’s agents running. Restart leaves all Radar timers disabled until their owner reconnects. Keep the app server, runtime and owning browser tab running. Pause stops future checks; an in-flight turn may finish, and its queued result appears after Resume.

With **OpenShell on**, approve `developer.nvidia.com` and `huggingface.co` in the agent's **OpenShell Policy** panel. The fixed feed requests run inside the sandbox; blocked requests are not retried through a host connection.

## Waiting states

- **Waiting for model:** neither enabled connection is ready. Check Settings → Model.
- **Waiting for runtime:** OpenClaw is not ready.
- **Waiting for other agents:** the native request queue is busy with foreground work.
- **Retrying preparation:** runtime setup failed; retries back off for 15, 30, then up to 60 seconds.
- **Waiting for browser:** reopen the owning browser session.

Heartbeat follows the effective Hiring/Lounge connection, including a ready fallback or host-saved NVIDIA key. A changed route is prepared again before checks resume. Preparation is separate from article generation; a failed setup does not mark the agent ready or replay a submitted model request.

## Arxivbot is a chat assistant

Hiring also offers **Arxivbot**: give it a topic and it searches for three relevant arXiv papers, summarizes the abstracts and compares the papers with titles, authors, dates and links. It uses the existing **Research & papers** skill. It has no periodic heartbeat or automatic Telegram delivery. Tech Radar remains the recurring discovery preset. Arxivbot replaces Three Takeaways in the default Hiring choices; existing agents keep their skills.

## Optional Telegram

In **Settings → Telegram**:

1. Create your bot with [@BotFather](https://t.me/BotFather). Paste the entire token, including the colon, into **Bot token**.
2. To receive personal messages, open [@userinfobot](https://t.me/userinfobot), tap **Start**, and copy the **Id** number into **Chat ID**. This third-party helper does not need your bot token.
3. Open **your own bot** in Telegram and send `/start`.
4. Choose **Connect Telegram**, then **Send test**.

For a group, add your bot with permission to post and use the group's numeric chat ID instead of your personal ID. Chat ID is separate from the numeric prefix of the bot token.

Connecting verifies the bot; the test checks actual delivery to the chosen chat. A single connection receives new Tech Radar summaries from your own hired agents. It does not forward ordinary chats, earlier summaries, or another participant's updates.

The bot token stays in server process memory, scoped to the connected browser tab, just like the model key. It is never written to app configuration, workspace files or model prompts. Closing/refreshing the tab or restarting the app requires reconnecting. If the close notification is lost, the session expires after 90 seconds. An already submitted message can still arrive. Telegram itself retains messages according to its service behavior.

App chat is saved first. If Telegram fails or delivery times out, the summary remains in chat. Uncertain sends are not retried automatically, to avoid duplicate notifications. Use Send test after fixing the connection; older summaries are not backfilled.

## Who does what

- **OpenClaw** owns the per-agent 20-second timer and isolated model/tool execution. Other agents keep heartbeats disabled.
- **The agent** follows `HEARTBEAT.md` and `bac-radar/SKILL.md`, selects an unread article and writes a short summary in its persona.
- **The feed tool** fetches the two fixed HTTPS feeds, supplies excerpts, validates the selected source and records the model-authored text once. It never authors the summary.
- **The app** imports the result into chat and optionally sends it to Telegram. Telegram delivery is an app integration, separate from OpenShell; the model never receives the bot token.

This guide describes the current `preview/stage3-scenarios` behavior. See [development branches](development.md#branches-and-versions).

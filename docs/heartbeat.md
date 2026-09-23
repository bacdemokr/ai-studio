# Tech Radar and Telegram

1. In Hiring, select **Tech Radar** and choose its tone.
2. Connect the model. No upload or chat prompt is needed.
3. Every **30 seconds**, OpenClaw asks the agent to introduce one technical article or announcement it has not shared before, from NVIDIA Developer Blog or Hugging Face Blog.
4. Use **Pause / Resume** in the agent panel.

Older feed entries are eligible: the agent discovers useful reading rather than waiting for newly published posts. Each short summary has a source link and publication date, and follows the chosen persona. The source evidence is the feed excerpt, not a full article review. Politics, investing, earnings and personnel announcements are excluded using a preliminary filter and agent judgment.

Shared URLs and skipped items are remembered in the agent workspace across restarts. The agent stays quiet when it exhausts the available relevant feed entries; it does not repeat old summaries or invent news. Feed changes are checked with conditional caching. Removing the agent removes its discovery history.

30 seconds is the native heartbeat cadence, not a response deadline. Model calls and ongoing tasks may delay an update. Checks pause while the model is disconnected or the agent is assigned other work. Keep the app server and runtime running. Pause stops future checks; an in-flight turn may finish, and its queued result appears after Resume.

With **OpenShell on**, approve `developer.nvidia.com` and `huggingface.co` in the agent's **OpenShell Policy** panel. The fixed feed requests run inside the sandbox; blocked requests are not retried through a host connection.

## Optional Telegram

In **Settings → Telegram**, enter a bot token from [@BotFather](https://t.me/BotFather) and your numeric chat ID. Send `/start` to that bot first. For a group, add the bot with permission to post and use the group's numeric chat ID. Use an existing chat ID from your Telegram setup; the bot token and chat ID are different values.

Choose **Connect Telegram**, then **Send test**. Connecting verifies the bot; the test checks actual delivery to the chosen chat. A single connection receives new Tech Radar summaries from your own hired agents. It does not forward ordinary chats, earlier summaries, or another participant's updates.

The bot token stays in server process memory, scoped to the connected browser tab, just like the model key. It is never written to app configuration, workspace files or model prompts. Closing/refreshing the tab or restarting the app requires reconnecting. If the close notification is lost, the session expires after 90 seconds. An already submitted message can still arrive. Telegram itself retains messages according to its service behavior.

App chat is saved first. If Telegram fails or delivery times out, the summary remains in chat. Uncertain sends are not retried automatically, to avoid duplicate notifications. Use Send test after fixing the connection; older summaries are not backfilled.

## Who does what

- **OpenClaw** owns the per-agent 30-second timer and isolated model/tool execution. Other agents keep heartbeats disabled.
- **The agent** follows `HEARTBEAT.md` and `bac-radar/SKILL.md`, selects an unread article and writes a short summary in its persona.
- **The feed tool** fetches the two fixed HTTPS feeds, supplies excerpts, validates the selected source and records the model-authored text once. It never authors the summary.
- **The app** imports the result into chat and optionally sends it to Telegram. Telegram delivery is an app integration, separate from OpenShell; the model never receives the bot token.

The `heartbeat` branch keeps this work separate from the shared `dev` preview.

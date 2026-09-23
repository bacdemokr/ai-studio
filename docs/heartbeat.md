# Notes Watcher and Telegram

1. In Hiring, select **Notes Watcher** and choose its tone.
2. Connect the model, then upload a TXT, Markdown, CSV, PDF or PPTX note. PDF/PPTX use the extracted text; scanned images are not OCR'd.
3. OpenClaw checks roughly every **30 seconds**. New or changed notes produce a short, model-written summary in the agent's chat. Unchanged notes stay quiet.
4. Use **Pause / Resume** in the agent panel. Pause prevents future checks; a turn already running can finish. A queued update appears when resumed.

30 seconds is the demo cadence, not a response deadline. Checks use the selected model and can be delayed by ongoing tasks or runtime load. Keep the app server and runtime running. A missing model connection suspends checks. Up to three changed documents are processed per turn, with bounded excerpts rather than an unlimited document review.

## Optional Telegram

In **Settings → Telegram**, enter a bot token from [@BotFather](https://t.me/BotFather) and your numeric chat ID. Send `/start` to that bot first. For a group, add the bot with permission to post and use the group's numeric chat ID. Use an existing chat ID from your Telegram setup; the bot token and chat ID are different values.

Choose **Connect Telegram**, then **Send test**. Connecting verifies the bot; the test checks actual delivery to the chosen chat. A single connection receives new Notes Watcher summaries from your own hired agents. It does not forward ordinary chats, earlier summaries, or another participant's updates.

The bot token stays in server process memory, scoped to the connected browser tab, just like the model key. It is never written to app configuration, workspace files or model prompts. Closing/refreshing the tab or restarting the app requires reconnecting. If the close notification is lost, the session expires after 90 seconds. An already submitted message can still arrive. Telegram itself retains messages according to its service behavior.

App chat is saved first. If Telegram fails or delivery times out, the summary remains in chat. Uncertain sends are not retried automatically, to avoid duplicate notifications. Use Send test after fixing the connection; older summaries are not backfilled.

## Who does what

- **OpenClaw** owns the per-agent heartbeat timer, session and model/tool execution. All other agents keep heartbeats disabled. Each isolated heartbeat turn stays separate from ordinary conversation, so repeated checks do not accumulate chat context.
- **The agent** follows `HEARTBEAT.md` and `bac-notes/SKILL.md`, reads changed uploads and writes its summary in its configured persona.
- **The notes tool** hashes uploads, returns text excerpts, validates the draft against the current files and records the exact model-authored text once. It does not generate prose or fetch websites.
- **The app** imports the result into chat and optionally relays it to Telegram. This is an app-side Telegram integration, not an agent network request through OpenShell. The model never receives the bot token.
- With **OpenShell on**, the notes tool runs in the agent's sandbox; with protection off, it runs in the normal workspace. Only uploaded documents enter the watch list. No arbitrary host-directory monitor is provided.

The `heartbeat` branch keeps this work separate from the shared `dev` preview.

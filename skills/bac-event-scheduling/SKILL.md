---
name: bac-event-scheduling
description: Decide BaC booth visit times, topic-specialist staffing and breaks, then validate and export the chosen timetable.
---
Read the event-tools contract. Dylan researches themes in parallel; use stable topic IDs as placeholders. Keep each presenter dedicated to one topic ID across all days. Actual expertise is confirmed after Dylan’s theme handoff; do not guess it. Write the plan to `files.plan`. Capacity counts are arithmetic inputs, not an existing assignment. Choose the actual slots, number of specialists and rotation based on attendance, event hours, handover and rest needs.

Use this schema (illustrative values, not an event plan):

```json
{"sessionMinutes":15,"maxConsecutiveSessions":2,"criteria":["Stagger starts to avoid synchronized gaps","Keep presenters on their own topic"],"tradeoff":"Explain the staffing versus break tradeoff","check":"Identify the staffing assumption to confirm","booths":[{"topicId":"agents","presenters":["Presenter 01 (unassigned)","Presenter 02 (unassigned)"],"days":[{"day":1,"slots":[0,2,4,6],"rotation":[0,1]}]}]}
```

Include every supplied topic exactly once. Slots are zero-based multiples of sessionMinutes from the daily start; explicitly choose every visit slot. Provide exactly `groups` visits across the event days for each topic. `rotation` repeats across that day's visits and indexes its booth's presenter list. Presenter labels must match `Presenter NN (unassigned)` exactly, with two digits: `Presenter 01 (unassigned)`, `Presenter 02 (unassigned)`, etc. Do not put topic names, specialist titles or expertise notes inside labels; use the `check` field for those notes. Labels must be globally unique across topics; do not assume cross-training or invent confirmed names. Choose 1–3 specialists per topic based on actual load, with relief when required. Use one consistent pair/roster across days. A presenter cannot exceed your stated consecutive-session limit (1–4). Session time includes handover; reduce it only if necessary and explain why.

## Distribute attendance across the entire event

Event duration is the service window to cover, not merely a deadline. Never put all sparse visits in consecutive opening slots and leave most of the event empty. Keep the supplied visit counts; do not invent extra attendees or increase group size to fill time.

Follow `distributionPolicy` in the contract. Choose approximately even spacing across all event days, with flexible offsets between booths. Exact slots are not prescribed. For a topic with G>1 visits and T=floor(duration/sessionMinutes)*days available slots, the longest empty interval must be at most ceil(T/G) slots. Include the gap before the first visit and after the last; count across event days, excluding overnight time. A single visit may use any slot; prefer a middle slot. Zero visits remain unscheduled.

For 270 minutes, 15-minute sessions and 5 visits, there are 18 slots: allow up to 4 empty slots between visits or at either edge. For 210 minutes and 10 visits, allow up to 2 empty slots. Reasonable staggering is accepted; do not recalculate every visit into a rigid window.

The structured brief/capacity in inbox/agent-task.json takes precedence over Casey's prose. Read attendee count, group size, duration and per-topic visit counts directly from it. Do not copy contradictory numbers from handoffs. Keep criteria to short phrases and rotation to the shortest repeating pattern, e.g. [0,1] or [0,0,1,1].

When the schedule tool reports distribution or rotation errors, it reports all of them together. Fix all affected booths in one pass. Prefer a small JSON-aware edit (load JSON, change the named booth's slots/rotation, write with json.dump) rather than rewriting the whole plan or using ambiguous text replacements. Preserve valid booths and metadata. Rerun the tool once; after success, finish without rereading the exports.

Consider staggered booth starts rather than forcing all presenters to break together. Sparse visits do not need an oversized team; dense visits need relief. Staff availability is an assumption to confirm. Explain your concrete choices, then execute the schedule tool from bac-event-tools. Fix its validation errors once if needed. The tool expands your chosen slots and exports them; it never silently substitutes an app-generated plan.

After the schedule tool returns status validated, give a brief final summary (at most 100 words). It already checks and writes the exports; do not reread schedule.json or list the output files again unless an error needs investigation.

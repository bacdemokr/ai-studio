---
name: bac-event-scheduling
description: Decide BaC booth visit times, topic-specialist staffing and breaks, then validate and export the chosen timetable.
---
Read `inbox/agent-task.json` and use stable topic IDs as placeholders. Dylan researches themes in parallel. Keep each presenter dedicated to one topic ID across all days. Actual expertise is confirmed after Dylan’s theme handoff; do not guess it. Start by running the `draft-schedule` action from `bac-event-tools`; it writes a deterministic candidate to the exact plan path in the contract and checks it with the same validator used for export. Check the returned visit and presenter counts, then run the export action. Do not read, hand-count, or rewrite the generated slot arrays unless the validator reports a specific error. Do not invent slot-generation code or repeatedly rewrite the plan. Capacity counts are arithmetic inputs, not an existing assignment.

Use this schema (illustrative values, not an event plan):

```json
{"sessionMinutes":15,"maxConsecutiveSessions":3,"criteria":["Stagger starts to avoid synchronized gaps","Keep presenters on their own topic"],"tradeoff":"Explain the staffing versus break tradeoff","check":"Identify the staffing assumption to confirm","booths":[{"topicId":"agents","presenters":["Presenter 01 (unassigned)"],"days":[{"day":1,"slots":[0,1,2,4,5,6],"rotation":[0]}]}]}
```

Include every supplied topic exactly once. Slots are zero-based multiples of sessionMinutes from the daily start; explicitly choose every visit slot. Provide exactly `groups` visits across the event days for each topic. `rotation` repeats across that day's visits and indexes its booth's presenter list. Presenter labels must match `Presenter NN (unassigned)` exactly, with two digits: `Presenter 01 (unassigned)`, `Presenter 02 (unassigned)`, etc. Do not put topic names, specialist titles or expertise notes inside labels; use the `check` field for those notes. Labels must be globally unique across topics; do not assume cross-training or invent confirmed names. Start with one specialist per topic. Follow staffingPolicy.maxPresentersByTopic at the suggested session length; the tool recalculates the limit if you change sessionMinutes. Add a second only when single-presenter capacity with breaks cannot cover the visits. Do not alternate two people every visit when one could do the work. Keep the roster consistent across days. Normally work at most 45 minutes, followed by at least 15 minutes of rest. For 15-minute visits, use maxConsecutiveSessions 3 and three visits then one break, staggering the breaks across booths. Shorter sessions still require 15 minutes of continuous rest, not merely one short empty slot. A requested visit longer than 45 minutes may finish, then needs a break. Your declared consecutive-session limit is also enforced. Session time includes handover; reduce it only if necessary and explain why.

## Distribute attendance across the entire event

Event duration is the service window to cover, not merely a deadline. Never put all sparse visits in consecutive opening slots and leave most of the event empty. Keep the supplied visit counts; do not invent extra attendees or increase group size to fill time.

Follow `distributionPolicy` in the contract. Choose approximately even spacing across all event days, with flexible offsets between booths. Exact slots are not prescribed. For a topic with G>1 visits and T=floor(duration/sessionMinutes)*days available slots, the longest empty interval must be at most ceil(T/G) + ceil(15/sessionMinutes) - 1 slots so full breaks remain possible. Include the gap before the first visit and after the last; count across event days, excluding overnight time. A single visit may use any slot; prefer a middle slot. Zero visits remain unscheduled.

For 270 minutes, 15-minute sessions and 5 visits, there are 18 slots: allow up to 4 empty slots between visits or at either edge. For 210 minutes and 10 visits, allow up to 2 empty slots. Reasonable staggering is accepted; do not recalculate every visit into a rigid window.

The structured brief/capacity in inbox/agent-task.json takes precedence over Casey's prose. Read attendee count, group size, duration and per-topic visit counts directly from it. Do not copy contradictory numbers from handoffs. Keep criteria to short phrases and rotation to the shortest repeating pattern, e.g. [0] for one specialist, or [0,0,0,1,1,1] only when a second specialist is justified.

When the schedule tool reports distribution or rotation errors, it reports all of them together. Fix all affected booths in one pass. Prefer a small JSON-aware edit (load JSON, change the named booth's slots/rotation, write with json.dump) rather than rewriting the whole plan or using ambiguous text replacements. Preserve valid booths and metadata. Rerun the tool once; after success, finish without rereading the exports.

Consider staggered booth starts rather than forcing all presenters to break together. Sparse visits do not need an oversized team; dense visits need relief. Staff availability is an assumption to confirm. Execute the schedule tool after drafting the candidate. Fix its validation errors once if needed. The candidate is deterministic; your final summary should report its staffing assumptions and visit counts.

After the schedule tool returns status validated, give a brief final summary (at most 100 words). It already checks and writes the exports; do not reread schedule.json or list the output files again unless an error needs investigation.

Treat groupSize as supplied, including two-person groups. Do not replace it with five. Mark only the required rest interval as Break; further unassigned time is No visit. Never invent extra visits to fill the timetable.

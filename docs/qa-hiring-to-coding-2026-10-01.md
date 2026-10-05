# Hiring-to-coding regression review - 2026-10-01

Scope: changes after `c8bf1be`, starting with custom Hiring names and including Tech Radar chat restrictions, Casey-only `/plan` drafts, staged resets, and compact desktop coding prompts.

## Findings and changes

- **Generated forms did not submit inside the preview.** The iframe sandbox blocked even local JavaScript submit handlers. Enable `allow-forms` alongside scripts while retaining an opaque origin and `form-action none` / `connect-src none`. Browser checks verify required-field validation and Enter submission, and verify that external form requests, fetch, parent DOM access and storage remain blocked.
- **Static review could overflow context.** In a real Tetris run, Vera repeatedly read the same source and guessed missing paths. The native precheck estimated 28,191 input tokens; three failed compactions ended the review. The saved implementation survived and the result was partial. Bound reviewer reads per plan, including the retry/revision allowance: eight reads, at most 120 lines per call, at most 5,000 characters per returned excerpt and 18,000 retained source characters total. Repeated source ranges are blocked. Truncation is explicitly identified; incomplete coverage is not full verification. Cody's file size is not capped by this guard.
- **Reset could overlap after reopening Settings.** Bulk deletion releases navigation while native cleanup continues. A dedicated reset lock now survives that release and dialog recreation. Old background cleanup also no longer clears a newer individual-deletion lock. Reset controls recover after completion; stage-specific behavior is preserved.
- **Casey sometimes requested a redundant verification pass.** A bill splitter took 281.8 seconds with an extra read/confirm revision. Clarify that repair requires an observed defect; a successful save is delivery evidence, while missing browser execution must be disclosed. A fresh run completed in 38.5 seconds without that revision. These are individual observations, not a speed guarantee.
- **Generated input and confirmation defects.** One calculator accepted a whitespace-only tip; one offline registration page promised a confirmation email. Strengthen trimmed numeric validation, finite-result checks, permitted zero values, and truthful local-only confirmations. Fresh outputs passed the same browser checks.
- **Generated game control defects.** An additional guarded review identified an uncalled piece-lock function and dispatched Cody once to repair it. The flow stopped with a partial result because the repaired version had not received another independent review. Further checks identified active-play Restart and score-display cases worth making explicit in implementation and review instructions.

## Verification

- 858 Python tests passed after the changes.
- 12 browser suites passed across isolated fixture servers: Hiring, Radar chat, comparison, agent reset, Settings resilience, action races, Casey document uploads, dynamic teams, one-revision flow, team setup, reset concurrency, and preview forms/security.
- Research and review guard JavaScript tests cover budgets, duplicate calls, excerpt boundaries, retry/revision scope and isolation from ordinary chat and other agents.
- Existing tests that manually chatted with Radar, invoked specialist `/plan`, or expected old reset/trace wording were updated to the intended behavior. These were stale expectations, not newly introduced application defects.

## Real coding tasks

Actual model requests used a separate OpenClaw gateway, Studio database and workspace. No production participant reset or agent deletion was performed. The final guard checks used the same research/review plugin configuration as the preview. Generated pages were exercised in a sandboxed desktop iframe with network/form destinations blocked. No mobile tests were run.

| Topic | Initial plan duration | Browser checks |
| --- | ---: | --- |
| Bill splitter | 281.8 s | Calculation, invalid counts/amounts; whitespace defect found and regenerated successfully |
| Cafe ordering | 30.2 s | Add items, quantities, total |
| Follow-up cafe edit | 38.2 s | Clear order, preserve menu, add again |
| To-do list | 28.2 s | Add, complete, undo, delete, blank rejection, literal HTML text |
| Focus timer | 26.2 s | Repeated Start, pause/resume, reset, actual elapsed time |
| Temperature converter | 24.2 s | Zero, negative decimal, reverse conversion, blank rejection |
| Geography quiz | 36.3 s | Correct/incorrect scores, repeated answers, restart |
| Sales dashboard | 44.4 s | Product revenue, total, proportional bars |
| Tic-tac-toe | 40.3 s | Turn order, occupied cells, win, draw, terminal-state guard, restart, keyboard |
| Expense tracker | 32.3 s | Positive amounts, invalid inputs, total/removal, literal HTML text |
| Registration form | 36.4 s | Name/email/seat validation, local submit, truthful confirmation; regenerated successfully |
| Tetris plus independent review | 388.8 s, partial | Context overflow reproduced; saved page checked for movement, gravity, line clear, game over and restart |

A subsequent Tetris generation and review completed in 94.7 seconds and passed the browser gameplay checks. A plugin-enabled run completed a review and one targeted code repair in 155.5 seconds, honestly marked partial because there was no independent second review. A final plugin-enabled run finished in 228.1 seconds. Its browser checks passed movement/gravity, line clearing/scoring and active/finished Restart, but found a wall-rotation branch that changed position without applying the rotated shape. The QA sample was corrected and retested; the raw model output was preserved. Review guidance now calls out alternate-branch state updates. This defect was missed by the model review, so its completion label alone is not proof of correctness.

In total, 17 completed actual model requests covered the 12 topics above. This excludes aborted harness setup attempts. The final run still used a redundant confirmation revision despite the prompt change; preventing every such semantic planning mistake remains a limitation. The review read/size limits are enforced independently of that model choice.

## Limits

These tests cover sampled requests and observed interactions. Model-generated applications can still contain logic defects, and a static specialist review is not browser execution. The bounded repair policy deliberately preserves useful partial work instead of looping until every possible defect is eliminated. Prompt changes reduce recurring mistakes but cannot guarantee correctness for arbitrary future requests. Some source may be omitted when the review budget is exhausted; that limitation must remain visible.

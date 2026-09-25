---
name: bac-nvidia-webpage
description: Author a complete BaC event HTML file from specialist handoffs using the local starter informed by NVIDIA public event pages.
---
For `sectionEditor: 2` tasks, read `inbox/morgan-page.json` once. Save all five text fields together in `sectionFiles.copy`: `{"headline":"...","intro":"...","cta":"...","program-title":"...","promotion-title":"..."}`. Write each `sectionFiles.card-N` as raw HTML, one complete article.theme-card under 6000 characters, in themes order. Use the native write tool. Distinct files may be written together. Do not wrap HTML in JSON or code fences. After the writes succeed, finish immediately with a receipt under 20 words. The app collects, validates and applies your files after your turn; you do not need a patch file, shell, apply/status command, or readback. Do not read the full HTML/CSS or the saved social post. The app escapes text, strips card IDs, retains accessibility attributes such as aria-hidden, and preserves CSS, logistics, schedule and the LinkedIn draft. Do not author those protected parts. If the app returns errors, rewrite only the named files/fields; valid sections are retained. No publishing or invented browser checks.

For legacy `sectionEditor: 1`, write a JSON patch with section/content and run the shipped event_page_sections.py apply command. For legacy tasks without sectionEditor, edit the supplied HTML starter with native file tools, preserving BAC:LOGISTICS and BAC:SCHEDULE exactly and the saved social post. Never rewrite the large timetable. These legacy instructions do not apply to sectionEditor 2.

For older tasks explicitly requesting copy-only JSON and providing no output file contract, follow their requested format.

Use the provided event brief and completed specialist deliverables. Lead with a short, benefit-led event headline, location and confirmed logistics. Distinguish the full event duration from the per-visitor demo length; do not imply every visitor attends the whole event or every booth. Keep the introduction visitor-facing; do not put internal assignments in the hero.

The supplied starter incorporates assets/event.css: a full-width dark hero with centered headline, a compact date/location line, a short introduction and one rectangular green call to action, followed by anchor navigation and generous white content sections. Keep the heading at a readable event-page scale (34–56 px) with balanced line breaks, not an oversized slogan squeezed into half the page. With no suitable event key visual, use this clean typography-only hero. Do not fill the other half with a tilted panel, numbered theme list, dashboard card, decorative grid, or “Your next chapter” widget. Themes belong in the program section below, not repeated as hero decoration. Present themes before operational details. Each theme needs a participant action, visible outcome, source and lightweight demo limitation. The planning view includes the booth rota and presenter breaks; these are not attendee registration claims.

Do not fabricate official sponsorship, speakers, dates, hardware benchmarks or registration URLs. Keep missing logistics as TBC. Never add NVIDIA logos, trademarks as a fabricated endorsement, or publish the page. Supply original copy, not copied headlines.

Program cards use the supplied `.cards`, `.theme-card` and `.theme-body` classes. Follow the text-first session layout: one small topic label, the exact demo title in `h3`, a `.demo-meta` line with booth and actual visit length, one participant-action paragraph, and an `.outcome` block with a short label and the visible result. Finish with a `.source` link labelled "Read the research" (localized to the event language), its full source title in `title` and `aria-label`, and a closed `.demo-reason` details block for the limitation. Keep the original research URL. Do not repeat the topic label, show oversized 01/02/03 banners, invent thumbnail graphics, add gradients, or display long article titles as the main card link. Use the supplied CSS unchanged for this structure. The program heading and short introduction are centered; card contents are left-aligned with neutral gray surfaces, black headings and restrained green link accents. Two or four demos use two columns, three or six use three, and phones stack cards. Keep all handoff content intact; do not shorten or rename Dylan's titles to make cards fit.

Program layout references visually checked 2026-09-24:
- https://www.nvidia.com/en-us/ai-days/ - centered section headings, generous spacing, straightforward event cards.
- https://www.nvidia.com/en-us/events/cvpr/ - compact text-first on-site event cards, title/metadata/body/action hierarchy. This starter adapts the hierarchy to its light content sections.

Public design references inspected 2026-09-20:
- https://www.nvidia.com/en-us/events/microsoft-build/ — visually rechecked: centered, unboxed heading and date/location on a dark full-width hero, centered introduction, overview/session/resource anchors, hands-on session cards.
- https://www.nvidia.com/en-us/events/automate-conference/ — date/location and clear action, topic-led sections.
- https://www.nvidia.com/en-us/events/siggraph/ — themed program and technical-session hierarchy.
- https://www.nvidia.com/en-sg/ai/build-a-claw/ — direct builder invitation and practical resource links.
This is a project-authored skill based on public references, not an official NVIDIA template.

Keep one main headline, at most 100 characters and 16 words. Use the introduction to add information instead of repeating the headline. Do not repeat long promotional paragraphs across sections. Preserve responsive media rules and horizontal timetable scrolling. On narrow screens, cards stack and text wraps; headings should not push the page wider than the viewport. The studio can request one repair for duplicated prose, an overlong headline, or missing responsive CSS.

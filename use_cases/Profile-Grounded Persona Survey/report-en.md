# AI Task Delegation Survey [SIMULATED]

[Archival Chinese source](sample/report.md)

> Complete English translation of the published Chinese report, not a new
> analysis. Kept outside the frozen `sample/` file inventory.

[Study scope and provenance](sample/README.md) | [Question distributions](sample/distributions.json)

Reviewed publication of one new completed profile-only survey using
openai/gpt-6.1-terra at temperature1 via OpenRouter. No product was used. All
answers and initial intents were generated anew; recommendations are hypotheses
for validation, not observed defects.

Merged finding support/counter counts describe unions of cited answers. They
do not establish that every cited Persona agrees with every clause; members may
overlap across questions. These are synthetic results, not human-participant
evidence, adoption rates or population estimates.

**Reading guidance:** All 20 synthetic Personas expressed conditional willingness.
This is not a human adoption rate or independent consensus: model tendencies,
profiles and a shared questionnaire may all encourage convergence. These results
alone cannot determine default permissions. For file deletion, 1 participant
would not delegate and the other 19 wanted confirmation every time; the older
description of identical approval choices throughout does not apply. Percentages
use answered respondents for each question. Conditional skips are neither missing
answers nor refusals. Approval-information multi-select choices are not rankings,
and not selecting an item is not opposition. The importance scale and categorical
approval matrix must not be combined into an autonomy score. Cost, support,
source verification and the actual review burden still require separate
validation; they are not measured benefits.

**Count scope:** In explanations of delegation position, 3/20 specified screen-reader
or accessible-control conditions. In the next-validation question, 4/20 explicitly
requested assistive-technology checks, including magnification and keyboard needs.
These counts concern different questions, not two disjoint groups or additional
participants.

## Summary

This synthetic cohort favors starting delegation with small, well-bounded tasks
while retaining control over sending, modification and deletion. Next, prioritize
validation of tiered authorization, pre-approval information and handling uncertain
results rather than treating task interest as permission for automatic execution.

- All 20 would allow drafts that are not sent or published within explicit limits
  without confirmation for each action. Sending and modification require
  confirmation every time; 1 would not delegate file deletion.
- Before approval, all 20 want exact content, destination, permission scope and
  recovery options. For uncertain output, 17 choose a draft to review; 3 choose
  stopping to ask first.
- Everyone would consider delegating at least one task, but task relevance,
  action authorization and actual use are different questions.
- Participants would spend some time reviewing. Accessibility, data access,
  cost and collaboration conditions also deserve validation in real contexts.
- Synthetic Persona feedback, not research with real participants or a population estimate.

### Decision Snapshot

- **Relevant Tasks:** Drafting or revising text: 18 (90.0%) · Finding and comparing information: 20 (100.0%) · Organizing schedules or reminders: 20 (100.0%) · Organizing digital files: 10 (50.0%) · Summarizing documents or messages: 14 (70.0%)
- **Delegation Position:** Would consider delegating at least one task: 20 (100.0%)
- **Uncertain Output:** Provide an uncertain draft for me to review: 17 (85.0%) · Stop and ask me before continuing: 3 (15.0%)
- **Approval Information:** Exact content or change: 20 (100.0%) · Recipient or destination: 20 (100.0%) · Permission scope and limits: 20 (100.0%) · Reasons and supporting sources: 13 (65.0%) · Changes since the previous version: 18 (90.0%) · Undo or recovery options: 20 (100.0%)
- **Use Context:** Personal tasks: 7 (35.0%) · Work tasks: 11 (55.0%) · Both personal and work tasks: 2 (10.0%)

## Next actions

Prioritized from the evidence; ranking is decision support, not measured impact.

### 1. In research with real participants, test tiered control through task-authorization and action-confirmation prototypes: generate drafts within explicit limits, confirm sending/modification/deletion every time, and allow refusal to delegate deletion.

- **Target:** This study
- This tests consequential-action boundaries and the minority view on deletion
  while preserving openness to bounded drafting. The evidence has not established
  how to configure those limits.

Based on: [f1](#finding-f1), [f8](#finding-f8)

### 2. Test a pre-approval preview showing exact content or changes, destination, permission scope and recovery options; examine how to present version changes and sources.

- **Target:** This study
- Four information categories were selected unanimously, while version changes
  and sources varied. Preserve complete review without assuming equal importance
  for every information item.

Based on: [f2](#finding-f2), [f6](#finding-f6)

### 3. Test both a labeled uncertain draft and a stop-to-ask path, observing how participants verify before deciding whether to act.

- **Target:** This study
- Most want to review a draft first, but 3 want to pause. Two paths avoid imposing
  one response on different boundaries.

Based on: [f3](#finding-f3), [f8](#finding-f8)

### 4. In permission setup, test explanations and choices for access scope and information-sharing limits, including shared-device contexts.

- **Target:** This study
- Participants value privacy and worry about unnecessary data use. Validate
  understandable controls rather than assuming an existing leak or defect.

Based on: [f4](#finding-f4), [f8](#finding-f8)

### 5. Study real reminder, information-comparison and drafting tasks in work/personal settings, recording verification processes and time.

- **Target:** This study
- These tasks are relevant to the cohort, but interest is not actual delegation
  or benefit. Retain human review while examining its time cost.

Based on: [f5](#finding-f5), [f6](#finding-f6), [f8](#finding-f8)

### 6. Separately test screen readers, keyboard use and magnification in later prototype research, including low-bandwidth, shared-device and colleague-record contexts.

- **Target:** This study
- Conditions raised by a minority may affect suitability. These are conditions
  to validate, not established product defects.

Based on: [f7](#finding-f7)

## Findings

<a id="finding-f1"></a>

### Authorize drafts separately from consequential actions

All 20 prefer drafts that are not sent or published within explicit limits without
per-action confirmation. All require confirmation for modifying existing documents
or sending messages to others. For deletion, 19 require confirmation every time
and 1 would not delegate. Individual answers additionally limit payments,
contacting others or sensitive-information sharing: delegating a task does not
authorize subsequent actions. All 20 rate execution control extremely important
and undo/recovery very important.

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- All 20 prefer drafts without sending/publishing within explicit limits without confirmation for each action. The same 20 want confirmation every time for modifying existing documents or sending messages. (supporting answers: 20; counter answers: 0)
- For deleting a digital file, 19 want confirmation before every execution and 1 would not delegate. None choose bounded execution without per-action confirmation. (supporting answers: 19; counter answers: 1)
- Beyond reviewing results, individual answers withhold authorization for payments/contacting others, limit sharing personal or sensitive information, or require discussion with colleagues before using their records. Another wants to check a schedule summary and personally decide whether changes are necessary. These conditions separate task delegation from action authorization. (supporting answers: 5; counter answers: 0)
- All 20 answers rate control over execution extremely important and undo/recovery very important. (supporting answers: 20; counter answers: 0)
- To validate: The specific limits and reason for refusing deletion remain unclear. These are hypothetical preferences.

</details>

<a id="finding-f2"></a>

### Make the exact action visible before approval

All 20 want exact content/change, recipient/destination, permission scope/limits
and undo/recovery options before approval. Another 18 select changes since the
previous version; 13 select reasons/supporting sources. The 7 not selecting
sources still select the four unanimous categories.

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- All 20 select exact content/change, recipient/destination, permission scope/limits and undo/recovery options before approval. (supporting answers: 20; counter answers: 0)
- Of 20, 18 select changes since the previous version. The other 2 do not, but both select exact content/change. (supporting answers: 18; counter answers: 2)
- Of 20, 13 select reasons/supporting sources and 7 do not; all 7 still select the four unanimous categories. (supporting answers: 13; counter answers: 7)
- To validate: Nonselection is not opposition and does not establish relative importance.

</details>

<a id="finding-f3"></a>

### Uncertain results need two handling paths

Seventeen choose an uncertain draft to review, while 3 choose stopping to ask.
Draft supporters often want uncertainty marked so they can check before using
or sharing. Some mention trusted sources or their own standards. Several also
worry about errors and want to review before relying on or sharing output.

Evidence contributors: 18 from cited supporting answers; 3 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- Seventeen answers choose an uncertain draft: see suggestions/uncertainty first, then verify or decide personally. Three choose stopping to ask, preferring details and a decision about next steps before continuation. (supporting answers: 17; counter answers: 3)
- Draft supporters often want uncertain content clearly marked for verification before use/sharing; some mention trusted sources, schedules or personal standards. Several distinguish reviewing a draft from sending, changing or other consequential actions, requiring their own decision or confirmation first. (supporting answers: 16; counter answers: 0)
- Several worry about errors in summaries, schedules, comparisons or outward-facing materials, wanting checks before relying on or sharing them; some specifically request source verification. (supporting answers: 15; counter answers: 0)
- To validate: Concern about errors is not an observed error, nor evidence that an assistant can mark uncertainty or provide sources.

</details>

<a id="finding-f4"></a>

### Accuracy and information boundaries both matter

All 20 rate accuracy and privacy at least very important; 16 and 12 respectively
rate them extremely important. Several worry about unnecessary use/sharing of
personal, sensitive or financial information and want to know or restrict access.
Shared devices are specifically mentioned.

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- All 20 rate accuracy and privacy at least very important. Accuracy receives 16 extremely-important and 4 very-important ratings; privacy receives 12 and 8 respectively. (supporting answers: 20; counter answers: 0)
- Several worry about unnecessary use/sharing of personal, sensitive or financial information and want to know or restrict what the assistant accesses. Shared devices are specifically mentioned. (supporting answers: 16; counter answers: 0)
- Several accept review/setup time but not loss of control over sending, changes, important actions or shared content. Some additionally restrict unnecessary personal information, sensitive details or security codes. (supporting answers: 18; counter answers: 0)
- To validate: These ratings/concerns do not evaluate actual accuracy, permission setup or information protection.

</details>

<a id="finding-f5"></a>

### Start small, but contexts and tasks differ

All 20 find information search/comparison and schedules/reminders relevant;
18 select writing/revising text, 14 summaries and 10 digital-file organization.
All would consider at least one task. First choices include reminders,
organization, planning and drafts, with some requiring personal checks before
use/sending. Context choices are work 11, personal 7 and both 2. Task relevance
does not authorize subsequent actions.

Evidence contributors: 20 from cited supporting answers; 9 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- All 20 select information search/comparison and schedules/reminders; 18 select writing/revising text and 2 do not. (supporting answers: 20; counter answers: 0)
- Fourteen select summarizing documents/messages; 6 do not. (supporting answers: 14; counter answers: 6)
- Ten select organizing digital files and 10 do not, showing varied relevance within this cohort. (supporting answers: 10; counter answers: 10)
- All 20 would consider at least one task. Reasons concern reminders, organizing materials, drafts, checklists or schedules; some emphasize personal checks or trusted sources. (supporting answers: 20; counter answers: 0)
- Fifteen answers choose reminders, checklists, summaries, organizing materials, comparing reports or study planning. Reasons include simplicity/bounded scope and personal verification before use. Relevance is not willingness to authorize subsequent actions. (supporting answers: 15; counter answers: 0)
- Five answers choose meeting follow-ups, team updates, scheduling messages or teaching-material drafts. Participants want to check wording, details or facts before sending/sharing/use; some explicitly send personally or first decide whether to send. (supporting answers: 5; counter answers: 0)
- Eleven choose work, 7 personal and 2 both. These are context preferences for a hypothetical assistant, not actual use or delegation intent. (supporting answers: 11; counter answers: 9)
- To validate: No product was shown. Choices do not establish actual delegation, effectiveness or continued use.

</details>

<a id="finding-f6"></a>

### Willingness to review does not remove time constraints

All 20 answers accept some time checking output, setting permissions or confirming
changes. Fourteen rate their own time moderately important; 6 rate it very
important. A minority want overall time savings, while some would still review
even with limited savings. Acceptance of review does not mean unlimited time.

Evidence contributors: 20 from cited supporting answers; 6 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- Fourteen rate their own time moderately important and 6 very important; the latter show that time investment matters to some usage decisions. (supporting answers: 14; counter answers: 6)
- All 20 accept some time checking output, setting permissions or confirming changes. Some contrast this explicitly with full automation. They intend to trade some time/involvement for suitable help or control, not claim prior use of this assistant. (supporting answers: 20; counter answers: 0)
- A minority specify further conditions: overall savings for some, willingness to check despite limited savings for others, fewer features in exchange for permission control/minimal data sharing, or clear pricing/verifiable sources. (supporting answers: 6; counter answers: 0)
- To validate: Review time has not been measured and acceptable durations are unknown.

</details>

<a id="finding-f7"></a>

### Accessibility and usage conditions may affect suitability

Three respondents specify screen-reader compatibility or accessible controls.
Later-validation suggestions include magnification, keyboard use, low bandwidth/
limited data, shared-device protection, costs and support. Individual answers
want colleagues consulted before using their records.

Evidence contributors: 17 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- Three want a demonstration first; 2 mention understanding costs, including 1 who also mentions available support. Another 3 specify accessibility conditions, including screen-reader compatibility or accessible controls. (supporting answers: 7; counter answers: 0)
- Some request screen-reader, magnification or keyboard checks and limited-data/low-bandwidth use. Others concern shared-device information protection, costs and support. For work/colleague records, individuals want prior consultation; 1 wants practice with a trusted person. (supporting answers: 17; counter answers: 0)
- To validate: Not mentioning a condition does not mean indifference. No product demonstration or group data establish defects or group differences.

</details>

<a id="finding-f8"></a>

### Validate control and outcomes through concrete tasks

Several want a demonstration or a small scheduling, handover-summary,
teaching-material or reminder task, then a result check. Answers broadly
request information/permission requirements and verification that actions can
be restricted. Some also ask to check sources, uncertainty, review efficiency,
confirmation or recovery.

Evidence contributors: 20 from cited supporting answers; 0 from cited counter answers. These sets may overlap and are not votes on every claim.

<details><summary>View evidence details</summary>

- Several want a demonstration or small task before checking results: schedules, handover summaries, teaching materials and reminders. Some specifically request source checks, uncertainty labeling or easy/quick review. (supporting answers: 19; counter answers: 0)
- Answers broadly request information/permission requirements and verification that actions can be limited. Several also want review/confirmation before sending or changes, or undo/recovery. Requirements range from draft review to external-action confirmation and restoration of original records. (supporting answers: 20; counter answers: 0)
- To validate: Requesting a trial is not willingness to delegate continuously and does not establish accuracy or usability.

</details>

## Limitations

This study uses hypothetical answers from 20 synthetic participants. No product
was shown or used, and actual delegation, action outcomes and elapsed time were
not observed. Counts describe only this cohort and support no population
inference. Everyone considered at least one task, so the refusal-reason question
was skipped by all.

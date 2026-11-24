---
name: genesia-raw-answer-report
description: 'Create an independent, evidence-grounded report from every eligible raw Persona answer in one saved Genesia run while deliberately ignoring its existing report and synthesis conclusions. Use when the user asks the assistant to personally review all Persona answers, recount preferences, verify experience claims against episodes, and write a new private Markdown report without rerunning Personas or invoking a provider.'
argument-hint: '<saved Genesia run, decision or question, audience, language, emphasis, and optional output filename>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Raw-Answer Report

Act as an independent research analyst over one immutable saved Genesia run. Read every
eligible original Persona answer, answer reason and relevant saved episode evidence, then
write a new private Markdown report tailored to the user's decision or question.

This Skill uses the current Agent's analysis and writing ability. It does not call the
provider configured in the run, invoke `genesia analyze`, rerun Personas, operate a
prototype, or treat the existing Genesia synthesis as source material.

Read [report patterns](./assets/report-template.md) before writing and apply the
[quality checklist](./references/quality-checklist.md) before delivery.

## Relationship To Code Reports

Keep these workflows separate:

- `genesia analyze RUN_DIR` is the standard code/SDK report pipeline. It invokes the
  configured provider and creates canonical structured analysis artifacts.
- `genesia report RUN_DIR` deterministically re-renders an accepted structured result.
- `/genesia-raw-answer-report` is a flexible Agent-led independent analysis directly over
  raw saved answers. Its output is non-canonical and private by default.

The source may be a full run or `run --research-only`. A research-only run is often the
cleanest source because it has immutable responses and episodes but no canonical
synthesis to accidentally reuse. Do not require report or analysis artifacts to exist.

Do not run the code analysis pipeline as a prerequisite for this Skill. Do not present an
independent Agent report as `report.md`, `report.html`, or the canonical Genesia synthesis.
The two approaches may be compared later as an audit, but they must remain independently
derived.

## Use This Skill When

Examples include:

- "Ignore the generated report and personally review every answer."
- "Write a one-page VP decision memo."
- "Analyze only accessibility feedback."
- "Compare views from the configured age groups."
- "Review Auto and Pointer feedback only."
- "Find minority views the standard report may have flattened."
- "Give me objections and counterevidence, not recommendations."
- "Audit whether the current report is supported by the raw answers."

The requested analytical direction controls the report. Do not force every study into one
fixed report structure.

Do not use this Skill to:

- create or repair participant data;
- merge or splice runs;
- complete missing interviews;
- call a provider on the user's behalf;
- publish raw identities, screenshots or traces;
- claim real-user validation or population estimates.

## Required Inputs

Resolve:

1. Exact source run directory.
2. Decision, question or analytical direction.
3. Audience.
4. Desired language and depth.
5. Relevant candidates, segments or configured dimensions.
6. Privacy/publication target.
7. Optional output filename.

Safe defaults:

- use the exact tagged or explicitly identified run;
- answer in the user's current language;
- infer the primary product decision from the task and questions;
- treat output as private;
- write a new file named `independent_raw_answer_report_<language>.md`;
- prefer a concise decision memo followed by optional detail.

Ask only when the source run, decision, audience, language or publication intent cannot be
resolved safely. Never infer permission to publish.

## Strict Source Boundary

Use:

- `run_manifest.json` for the effective task, source lineage, model, cohort, sequence,
  prototype limits and provenance;
- `research_result.json.responses` for original answer `value`, `reason`, `basis`,
  validity, errors, method ID, question ID, Persona ID and evidence refs;
- `research_result.json.episodes` for actual exposure, routes, actions, outcomes, stopping
  and execution failures;
- `research_result.json.metrics` for requested/valid/invalid/missing response and failure
  counts;
- exact task questions, candidates, roles, objectives, options and configured segments;
- `evidence_verification.json` and `genesia verify`;
- case provenance only when needed to identify exact candidates.

Exclude before analysis:

- `research_result.synthesis`;
- `research_result.report.analysis`;
- `report.md`, `report.html`, `appendix.md`, and `appendix.html`;
- prior independent reports;
- conclusions copied from another analysis run.

Do not read excluded conclusions until the independent report is saved. If the user later
asks for a comparison, perform it as a distinct audit.

## Procedure

### 1. Verify The Exact Run

Run:

```powershell
python -m genesia verify path\to\runs\RUN_ID
```

Confirm:

- exact run and source lineage;
- completed, partial or failed status;
- requested, valid, invalid and missing Persona-method responses;
- run errors and failed actions;
- evidence integrity;
- configured candidate sequence;
- actual candidate exposure.

Stop if required evidence is corrupt or original answers are missing. Do not silently
select another run. A partial run may be analyzed only with explicit missing coverage.

### 2. Build A Complete Answer Ledger

For every configured `method_id/question_id`, record:

- exact question;
- candidate, purpose and feedback role;
- kind and options;
- objective and criterion IDs;
- required status;
- every eligible original answer and reason;
- invalid, missing, skipped, automation and `not_observed` rows.

Do not sample answers because they look repetitive. Track answer membership so reviewed
answer IDs reconcile exactly with eligible answer IDs.

For large studies, use session SQL for ledgers and theme membership. Do not write temporary
analysis files into the repository.

### 3. Compute Deterministic Facts

Compute from structured fields:

- response validity and completion;
- single/multiple-choice distributions;
- candidate preference, ties, no preference and insufficient experience;
- candidate exposure;
- route/page coverage;
- configured segment membership;
- selected options represented structurally.

Keyword searches are discovery aids only. A thematic count requires an explicit,
manually reviewed supporting-ID set including synonymous wording and excluding false
positives. Every reported count needs a denominator.

### 4. Analyze In The Requested Direction

Read all answers to each exact question together, then synthesize across questions.

Depending on the request, emphasize:

- overall decision and tradeoffs;
- one candidate or control;
- strengths worth preserving;
- friction and consequences;
- accessibility, privacy or trust;
- configured segment similarities/differences;
- minority views;
- unresolved uncertainty;
- report-support audit.

Separate:

- reported experience;
- personal preference;
- suggestion or wish;
- profile context;
- automation limitation;
- prototype boundary;
- untried behavior.

Preserve a minority view only when it changes the decision, product action or critical
uncertainty. Never infer an opinion from age, occupation or another profile attribute.

### 5. Verify Experience Claims

Use episodes only to verify claims such as:

- the Persona reached the candidate, page or control;
- a visible setting changed;
- an action failed or was retried;
- navigation or scrolling occurred;
- stopping was natural or limitation-driven.

Answers remain the primary source for what mattered. A successful browser action does not
prove backend success, persistence or satisfaction. Treat prototype/browser/model failures
as execution limits.

### 6. Compose For The Audience

Default client-facing order:

1. Decision in plain language.
2. Recommended actions, each with an explicit target such as Version A, Version B,
   cross-version, or follow-up research.
3. Four to ten concrete non-overlapping insights.
4. Important tradeoffs and distinctive views.
5. Short research boundaries.
6. Optional detailed evidence, routes, segments or Persona matrix after the conclusions.

Do not put methodology tables, route inventories, segment matrices, answer coverage or
research mechanics before the decision unless the user explicitly asks for an audit.

Do not force every insight into visible "Why it matters / Design implication /
Uncertainty" layers. Write a natural conclusion and consequence. Put detailed evidence
membership after the conclusion or in a compact table/appendix.

Use [report patterns](./assets/report-template.md) as adaptable patterns, not a mandatory
section checklist.

## Comparison Rules

For multi-candidate studies:

- report every available choice option;
- distinguish interface preference from resulting-content preference;
- compare like attempted goals where possible;
- retain concrete candidate strengths even when another candidate wins;
- label every recommendation with its target;
- permit ties and insufficient experience;
- disclose fixed order, learning, anchoring, carryover and recency effects;
- never claim causal A/B superiority from a fixed-order synthetic comparison.

## Segment Rules

Use only configured segments or attributes explicitly requested by the user.

- Show actual group sizes.
- Groups below the configured or reasonable minimum remain descriptive.
- Do not infer that an attribute caused an opinion.
- Do not manufacture differences so every group looks unique.
- "No supported difference" is a valid conclusion.
- Put large segment matrices after the main decision.

## Output Rules

Write a new Markdown file. Never overwrite:

- canonical `report.md`, `report.html`, appendix or structured result;
- task, manifest, responses, episodes or evidence;
- an earlier independent report.

Use a descriptive filename, for example:

```text
independent_raw_answer_report_zh.md
independent_age_group_analysis_zh.md
independent_accessibility_review.md
executive_decision_memo_zh.md
```

If the requested filename exists, add a label or UTC timestamp.

Use stable aliases such as `P01`, not raw Persona IDs, whenever an individual matrix adds
decision value. Omit unnecessary profile fields, screenshots and traces.

Open with a source declaration:

> This independent report was prepared directly from saved original Persona answers and
> episodes. It is not the canonical Genesia synthesis, and existing report conclusions
> were deliberately excluded.

## Quality Gate

Apply every item in [quality checklist](./references/quality-checklist.md). Reject the
report when it is structurally complete but not useful to its audience.

At minimum confirm:

- all eligible answers were reviewed;
- counts have explicit denominators and membership;
- candidate claims have actual exposure;
- recommendations identify their target;
- concrete controls and different design actions remain distinct;
- counterevidence and decision-relevant minority views survive;
- conclusions precede tables and methodology;
- no excluded report conclusion entered the analysis;
- raw IDs and unnecessary profile details are absent;
- source artifacts are unchanged.

## Completion Report

Return:

- source run ID/status and lineage;
- independent report path and filename;
- audience, language and requested analytical direction;
- valid/invalid/missing/failed counts;
- eligible/reviewed answer totals;
- candidate exposure and evidence verification;
- concise decision and top actions;
- critical limits;
- confirmation that no Persona, prototype, configured provider or canonical source
  artifact was invoked or modified.

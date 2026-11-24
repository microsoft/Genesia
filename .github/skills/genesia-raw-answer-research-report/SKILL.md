---
name: genesia-raw-answer-research-report
description: 'Create a comprehensive independent research document from every eligible raw Persona answer in one saved Genesia run while ignoring existing synthesis and reports. Use when the user wants full methodology, cohort context, detailed findings, candidate analysis, exploration coverage, segment analysis, an anonymized Persona matrix, prioritized recommendations, validation planning, limitations, and a final judgment rather than a short decision memo.'
argument-hint: '<saved Genesia run, audience, language, research emphasis, segment needs, and optional output filename>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Raw-Answer Research Report

Create a comprehensive, independently reasoned research document from one immutable
saved Genesia run. Review every eligible original Persona answer and reason, verify
experience claims against saved episodes, and preserve enough detail for product,
design and research teams to audit the conclusion.

This is an Agent-led private analysis. It does not invoke `genesia analyze`, call the
provider configured in the run, rerun Personas, operate a prototype, or use the existing
Genesia synthesis as source material.

Read [research report template](./assets/research-report-template.md) before drafting and
apply the [research quality checklist](./references/research-quality-checklist.md) before
delivery.

## Difference From `/genesia-raw-answer-report`

Use the two Skills for different deliverables:

| Skill | Default deliverable |
|---|---|
| `/genesia-raw-answer-report` | Flexible, audience-specific analysis; usually a concise decision memo or focused review |
| `/genesia-raw-answer-research-report` | Comprehensive research document covering the full study and its audit trail |

Choose this Skill when the user wants the equivalent of a complete research readout:

- executive conclusion;
- source, protocol and method;
- cohort context;
- shared and distinctive findings;
- candidate-by-candidate strengths and friction;
- concrete control-level evidence;
- actual exploration coverage;
- configured segment analysis;
- anonymized Persona decision matrix;
- prioritized product recommendations;
- next-study validation plan;
- limitations and final judgment.

Do not use this Skill merely because the study has many answers. If the user wants a
one-page executive memo, one analytical angle, or a quick decision, use
`/genesia-raw-answer-report`.

## Relationship To Code Reports

- `genesia analyze RUN_DIR` is the standard provider-backed code/SDK analysis.
- `genesia report RUN_DIR` deterministically re-renders an accepted structured result.
- This Skill independently reads the raw saved study and writes a non-canonical Markdown
  research document.

The source may be a full run or `run --research-only`; the latter intentionally has no
canonical report or analysis artifacts. Do not reject it for those expected omissions.

Do not run code analysis first. Do not copy its synthesis. A later comparison between
the canonical report and this document is a separate audit task.

## Required Inputs

Resolve:

1. Exact source run directory.
2. Primary product/research decision.
3. Audience and expected depth.
4. Language.
5. Candidate, feature and control emphasis.
6. Required configured segments or cohort perspectives.
7. Privacy/publication target.
8. Optional output filename.

Safe defaults:

- use the exact tagged or explicitly named run;
- use the user's current language;
- treat output as private;
- infer the primary decision from task objectives and questions;
- include all configured candidates;
- include configured segments only when they change interpretation or the user explicitly
  requests a descriptive breakdown;
- use `independent_raw_answer_research_report_<language>.md`.

Ask only when source, audience, language, decision or publication intent cannot be
resolved safely.

## Strict Source Boundary

Use:

- `run_manifest.json`;
- the effective task and exact questions;
- `research_result.json.responses`;
- `research_result.json.episodes`;
- `research_result.json.metrics`;
- `evidence_verification.json`;
- `genesia verify`;
- case provenance needed to identify exact candidates.

Exclude before analysis:

- `research_result.synthesis`;
- `research_result.report.analysis`;
- canonical report and appendix files;
- other analysis runs;
- previous independent reports.

Do not read excluded conclusions until the new research report is saved.

## Procedure

### 1. Verify Source Integrity

Run:

```powershell
python -m genesia verify path\to\runs\RUN_ID
```

Record:

- run ID, phase, status and lineage;
- exact task and variant provenance;
- provider/model used for participant generation;
- cohort source, seed, requested and actual IDs/count;
- valid, invalid, missing and failed responses;
- failed actions and run errors;
- evidence verification;
- candidate order and actual exposure.

Stop on corrupt evidence or missing required source answers. Never substitute another run.

### 2. Build A Full Question Ledger

For each exact `method_id/question_id`, retain:

- exact text;
- kind, options and explain behavior;
- purpose, feedback role and candidate;
- objective/criterion IDs;
- every eligible answer and reason;
- basis and evidence refs;
- missing, invalid, skipped, automation and `not_observed` rows.

Review every eligible answer. Do not sample repetitive rows. Reconcile configured answer
slots, substantive answers and reviewed answer IDs.

### 3. Compute Structured Facts

Code or deterministic inspection owns:

- validity and completion;
- choice distributions;
- ties/no preference/insufficient experience;
- candidate exposure;
- route/page coverage;
- step ranges;
- configured segment membership;
- structured option use.

Every thematic count requires an explicit reviewed membership set. Keyword search is only
a discovery aid.

### 4. Analyze Each Question

For each question:

- identify shared themes;
- preserve concrete controls and consequences;
- record support and counterevidence;
- separate experience, preference, suggestion and context;
- retain a decision-relevant minority view;
- mark untried behavior and prototype/automation limits;
- keep candidate ownership.

Do not create a Persona-by-Persona narrative at this stage.

### 5. Synthesize Across Questions

Build a detailed but non-repetitive finding set. Keep separate findings when they imply
different product actions, even if individually supported by few Personas.

Each finding should internally track:

- claim;
- supporting and counter answer IDs;
- denominator;
- source questions;
- candidate or shared scope;
- user consequence;
- product implication;
- unresolved uncertainty.

The final prose may combine these naturally; it does not need visible framework labels for
every field.

### 6. Verify Experience Claims

Use episodes to confirm:

- actual candidate exposure;
- reached pages/controls;
- visible state changes;
- scrolling, wrong turns and retries;
- action failures;
- stopping reason.

Do not convert execution traces into preferences. Do not infer backend success,
persistence or real-system behavior from a prototype.

### 7. Analyze Configured Segments

When segment analysis is requested:

- show group sizes;
- compare answer memberships, not stereotypes;
- distinguish shared patterns from meaningful differences;
- keep groups below a reasonable minimum descriptive;
- state when no supported difference exists;
- never infer attribute causality.

Segment discussion belongs after the main product findings, not before the decision.

### 8. Compose The Research Document

Follow [research report template](./assets/research-report-template.md), adapting sections
to the study.

The document should normally include:

1. concise executive conclusion;
2. data and method;
3. cohort context;
4. detailed shared findings;
5. candidate-specific strengths, friction and tradeoffs;
6. actual exploration behavior;
7. configured segment analysis;
8. anonymized Persona decision matrix when useful;
9. prioritized recommendations with explicit target;
10. next-study validation plan;
11. limitations;
12. final judgment.

This Skill intentionally produces more detail than the decision-memo Skill. Still avoid
duplicating one conclusion across executive summary, candidate sections, comparison and
recommendations.

## Comparison Rules

For multi-candidate studies:

- report all preference options;
- distinguish interface preference from content/result preference;
- retain strengths of losing candidates;
- label actions as Candidate A, Candidate B, cross-candidate or research;
- compare attempted goals rather than unmatched routes;
- disclose order and carryover effects;
- do not claim causal superiority.

## Privacy

Use stable aliases such as `P01` in individual matrices. Never expose raw Persona IDs,
session IDs, contact-like details, unnecessary attributes, screenshots or private traces.

Configured segment labels may be reported with counts. Avoid reconstructing identifiable
profiles from segment combinations.

## Output

Write a new Markdown file, for example:

```text
independent_raw_answer_research_report_zh.md
independent_full_research_readout.md
independent_comparison_research_report_20260924.md
```

Never overwrite canonical reports, appendices, tasks, manifests, responses, evidence or
an earlier independent report.

Open with:

> This comprehensive independent research report was prepared directly from saved
> original Persona answers and episodes. It is not the canonical Genesia synthesis, and
> existing report conclusions were deliberately excluded.

## Quality Gate

Apply [research quality checklist](./references/research-quality-checklist.md). Reject a
document that is long but repetitive, exhaustive but decision-free, or methodologically
complete but not useful.

## Completion Report

Return:

- source run ID/status/lineage;
- report path;
- audience, language and requested emphasis;
- response and answer coverage;
- candidate exposure;
- evidence verification;
- primary decision;
- top findings and targeted recommendations;
- segment conclusion when requested;
- critical limitations;
- confirmation that no Persona, prototype, configured provider or canonical artifact was
  invoked or modified.

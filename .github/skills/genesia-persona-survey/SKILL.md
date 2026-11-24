---
name: genesia-persona-survey
description: 'Run and review a profile-grounded synthetic Persona survey with the Genesia SDK and CLI. Use when the user has survey questions and authorized Persona JSON/TSV, wants single-choice/multiple-choice/Likert/open-text/conditional responses, batched questionnaire execution, descriptive distributions, segment comparisons, synthesis, recommendations, or an insight_report.md. This Skill is survey-only and does not require a prototype, recording, or product environment.'
argument-hint: '<survey questions or task.yaml, Persona JSON/TSV, research goal, and model provider>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Persona Survey

Use Genesia as the only runtime for a profile-grounded synthetic Persona survey. This Skill authors and invokes the public CLI/SDK; it does not reimplement survey prompting, response validation, batching, statistics, synthesis, provider calls, status calculation or evidence storage.

Genesia packages shared identity rules in `persona_role.md` and survey-specific grounding/completeness rules in `survey_response.md`. Applicable policies are included in model-request artifacts for auditability.

```text
survey questions + authorized Persona data
  -> this Skill -> survey task.yaml -> Genesia CLI / SDK
                                      -> profile-grounded Persona responses
                                      -> deterministic distributions / segments
                                      -> synthesis + report.md + insight_report.md
```

This Skill covers `environment.mode: survey` and survey methods only. It does not create a fake product experience. For autonomous prototype interaction use `/genesia-live-prototype`; for fixed recorded journeys use `/genesia-recorded-prototype`.

## Architecture Contract

Questionnaire input, interaction mode and research method are separate. Survey-only mode bypasses `EnvironmentBuilderAgent` and creates no Context/Cards/Graph, environment adapter, observation or action history. The public API creates one PersonaAgent/session per participant and enters the research gate directly with profile grounding. The same object/session persists across question batches and configured methods; provider-side memory is not assumed.

A `kind: survey` method may also run after a live or material-based experience, but that is not this profile-only workflow. Route material-only research through public SDK/CLI `environment.mode: auto`, or use the live/recorded Skill for its input. Do not discard supplied product material or an intended product experience by silently switching to survey-only mode.

Read [survey authoring](./references/survey-authoring.md) before creating or converting questions. Read [insight review](./references/insight-review.md) before interpreting outputs. Provider configuration is summarized in [model providers](./references/model-providers.md).

## Runtime Boundary

Read [analysis and reports](../../../docs/analysis-and-reports.md) for opt-in
Persona concurrency and staged per-question insight synthesis.
Use public `doctor`, `run --open` and `report RUN_DIR --open`; never build a
second worker pool or synthesis pipeline in the Skill.

Set `insight.language` (`en` or `zh-CN`).
`genesia analyze RUN_DIR --language en --focus "Adoption decision"` reuses verified
answers for new model analysis into a separate run with lineage; repeat `--focus`
for additional priorities. It does not re-survey Personas or modify the original.
`report` only re-renders.

Always call public entry points:

```powershell
python -m genesia preflight TASK
python -m genesia preflight TASK --network
python -m genesia run TASK
python -m genesia verify RUN_DIR
```

Or:

```python
from genesia import load_task, preflight, run
```

Never call a model provider directly, build a parallel survey simulator, inject fake product observations, silently switch providers, fabricate missing answers, relabel status or combine runs.

## Procedure

### 1. Resolve Inputs

Identify:

- research goal and decisions the survey should inform;
- survey questions, exact options, required flags and conditional logic;
- user-supplied authorized Persona JSON/TSV;
- cohort IDs/size/seed, filters and meaningful segments; use `segment_fields`
  for categorical profile values or concise integer buckets such as
  `segments: {age_group: {source: Core Identity.age, buckets: ["<30", "30-39", "40-49", "50+"]}}`;
- model provider and budgets;
- output privacy and sharing constraints.

Do not invent Persona profiles. Use an authorized external JSON/TSV or a validated
Genesia-generated `personas.json`. For a managed generation, run
`genesia personas validate GENERATION_DIR` and preserve a required full cohort; use
`/genesia-persona-generation` only when the user explicitly asks to create a new one.
Do not copy private Persona data or response outputs into tracked Skill assets or
public samples.

### 2. Author The Survey Task

Copy [survey task template](./assets/survey-task.yaml), replace `PATH_TO_PERSONAS.json`, and adapt objectives/questions/provider/budgets together. Keep objectives/criteria in `study` and question definitions in survey `methods`; do not duplicate the packaged Persona or survey policies in Skill assets.

Use only:

```yaml
environment:
  mode: survey
```

Survey mode accepts no URL, sources or action floor. Genesia creates no product observation or action history. Answers are grounded in the supplied Persona profile and may use `not_observed` when the profile cannot support an answer.

### 3. Validate The Questionnaire

```powershell
python -m genesia preflight path/to/survey-task.yaml
```

Fix duplicate IDs/options, invalid conditional references, missing objective mappings, unavailable Persona segments, permissions and budget warnings. Conditions may reference only earlier questions and compare to an exact prior answer.

Then check the configured provider/model when the user intends to run:

```powershell
python -m genesia preflight path/to/survey-task.yaml --network
```

### 4. Run One Intact Survey

```powershell
python -m genesia run path/to/survey-task.yaml
```

`batch_size` controls questions per model call for each Persona. Start around 5 for long or complex questionnaires. Genesia checkpoints completed batches inside the run, but it does not currently resume an interrupted survey run; a new invocation is a separate run and must not be merged invisibly.

Use `--research-only` only when the user explicitly wants original answers without
synthesis or reports. It cannot be combined with `--open`. A completed research-only
survey certifies response execution, not analysis or Persona realism; use `analyze`
later to create a separate lineage-linked report run.

### 5. Verify And Review

```powershell
python -m genesia verify path/to/runs/RUN_ID
```

Inspect:

- `report.html` and `report.md` for the unified TL;DR-first report when reports were
  rendered; `insight_report.md` is a compatibility alias;
- `appendix.html` / `appendix.md` for individual answers, segments and research readiness;
- `analysis_input.json` and `analysis_provenance.json` for answer IDs, exclusions,
  question stages and processing coverage when analysis ran;
- `study_review.json` for design/sample review; no compiler or product-experience artifacts are expected;
- `research_result.json` for typed responses, counts, synthesis and errors;
- `run_manifest.json` for exact survey, cohort, provider and budgets;
- `evidence_verification.json` or `genesia verify` for integrity.

Research-only runs intentionally omit report, appendix and analysis artifacts. Review
the immutable responses directly or create a separate analysis run; do not treat absent
reports as corruption.
New reports present Summary, prioritized Next actions, Findings, brief Limitations and
Appendix / Evidence from the same analysis. Review relevant configured segment sizes,
minority views, exact choice distributions and agreement between summary and action
priority. Profile-grounded survey answers are not observed prototype behavior. Legacy
reports keep their previous structure.

### 6. Deliver

Report run ID/status, requested Personas and expected/valid/invalid/missing Persona-method responses separately, per-question descriptive counts, meaningful segment differences, findings, recommendations, errors and evidence integrity. Expected responses are selected Personas times configured methods, not the number of questions. `verify` checks hashes and path confinement, not whether a synthetic answer or claim is true.

Always state that these are synthetic Persona responses, not observed real-user survey data, prevalence estimates, significance tests or measured product outcomes.

## Current Scope

Genesia supports embedded task YAML questions, exact schema validation, question batching, per-batch checkpoints, conditional skips, descriptive counts/percentages, segment breakdowns and evidence-linked synthesis.

This Skill does not import Microsoft Forms HTML, resume a failed run, calculate
Spearman correlation against a real survey, or perform embedding/K-means clustering.
Bounded Persona concurrency and context-budgeted per-question synthesis are supported
by the SDK. Oversized questions split by answer before evidence-bound final composition.
Internal question order and conditional dependencies remain sequential.

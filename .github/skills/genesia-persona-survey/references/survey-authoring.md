# Survey Authoring

## Mode And Research Gate

Use `environment.mode: survey` with only survey methods for profile-only research. It bypasses environment compilation and experience entirely: no sources, URL, action floor, Cards/Graph or invented product observations. `prepare` is not a required compilation step.

Use `study` for objectives/criteria and `methods` for neutral questions and their objective/criterion mappings. A survey method following a live or material-based experience belongs to that workflow instead; changing the question kind does not change the interaction mode. The runtime, not the Skill, preserves the same PersonaAgent/session through the research gate and all batches.

## Question Types

### Text

```yaml
- id: reason
  text: What is the main reason for your answer?
  kind: text
  required: true
```

The answer is a nonempty string or `null` with `basis: not_observed` when unsupported.

### Single Choice

```yaml
- id: frequency
  text: How often would this fit your work?
  kind: single
  options: [Daily, Weekly, Monthly, Rarely, Never]
```

The answer must exactly match one option.

### Multiple Choice

```yaml
- id: tasks
  text: Which tasks apply?
  kind: multiple
  options: [Planning, Analysis, Documentation, None]
```

The answer is a unique subset of options.

### Likert Matrix

```yaml
- id: priorities
  text: Rate each quality.
  kind: likert
  rows: [Clarity, Speed, Trust]
  options: [Low, Medium, High]
```

The answer maps every row to exactly one option.

### Conditional Question

```yaml
- id: intent
  text: How likely are you to try it?
  kind: single
  options: [Unlikely, Unsure, Likely]
- id: barrier
  text: What would need to change?
  ask_if: {intent: Unlikely}
```

Conditions reference only earlier question IDs and compare to an exact answer. Skipped questions remain recorded with a null value and `basis: skipped`.

## Batching

`batch_size` is questions per Persona model call, not Personas per call. For a simple survey use 5-10. Use smaller batches for many open-text or matrix questions. Every completed batch is checkpointed, but interrupted runs are not resumed automatically.

A failed method retains completed batch evidence but is excluded from synthesis as a whole. Do not count a saved batch as a valid method response or merge it into a new run.

## Cohort And Segments

Use user-supplied authorized JSON/TSV Persona data. Explicit IDs give fixed membership; `size` + `seed` gives reproducible sampling. Filters are exact profile-field matches.

`study.segment_fields` uses dotted profile paths for categorical values. Add only dimensions present across the selected sample and meaningful for comparison.

Use `study.segments` for concise integer ranges. The source field must contain an
integer for every selected Persona. The labels must be ordered,
contiguous, non-overlapping, start with `<N`, and end with `N+`:

```yaml
study:
  segments:
    age_group:
      source: Core Identity.age
      buckets: ["<30", "30-39", "40-49", "50+"]
```

Configured distributions for single-choice, multiple-choice and Likert questions
appear in the main report under Segment Analysis. Open-text answers remain in the
evidence and synthesis rather than being reduced to deterministic counts. Segment
counts are descriptive; Genesia flags groups below five and does not calculate
significance.

## Wording

Ask one construct per question. Keep option scales balanced, ordered and mutually interpretable. Include explicit non-applicable options where needed. Avoid leading phrases such as “obviously,” “surely,” or “don’t you agree.”

Survey-only answers are profile-grounded projections. If a Persona profile lacks enough information, the model must use `not_observed` instead of manufacturing a history.

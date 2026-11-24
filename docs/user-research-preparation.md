# User Research Preparation and Configuration

This guide explains what a team should prepare before running synthetic Persona research with Genesia, how to configure a study, and how to define a report that is concise, comprehensive, evidence-grounded, and attentive to both shared and distinctive feedback.

## 1. Start With the Decision

Do not begin with a prototype URL or a list of generic usability questions. Write down:

- the product or design decision the research must inform;
- who will use the result and when the decision is due;
- what evidence would change the team's current direction;
- what is explicitly outside scope;
- whether the study is exploratory, evaluative, comparative, diagnostic, or descriptive.

A useful goal is specific enough to guide analysis but does not prescribe the desired conclusion.

## 2. Choose the Research Mode

| Need | Genesia mode | Required input |
|---|---|---|
| Observe autonomous use of one prototype | Live prototype | Isolated HTTP(S) prototype |
| Compare A/B or multiple versions | Live comparison | Ordered same-origin variants and handoffs |
| Review a fixed journey | Recorded prototype | Recording, frames, optional input trace |
| Collect profile-grounded answers only | Persona survey | Questions and authorized Persona data |

Use a live comparison only when the same Persona should experience multiple variants. Do not infer causal A/B effects from a fixed order.

## 3. Prepare the Prototype or Materials

Provide:

- an isolated, stable URL or immutable recording;
- exact version provenance: branch, commit, build artifact, or recording hash;
- a deterministic starting state;
- implemented scope and known limitations;
- test accounts and safe disposable data when needed;
- permission boundaries for navigation, screenshots, external requests, and data submission.

Known placeholders and unimplemented destinations belong in study limitations. They must not become product findings merely because a Persona encountered them.

### Product background before experience

Put a concise, neutral introduction at the start of the task `goal`: intended
audience, problem, product concept and the prototype's actual limits. The same
goal is supplied before intent generation, throughout interaction and during
the interview. An introduction visible only on a page is not evidence that
every participant received or understood it.

Separate "the product aims to" from "the prototype implements." Do not promise
benefits, prescribe a successful route, invent previous product use in a profile,
or introduce the background only when re-answering an old episode.

If the background changes, repeat the experience. Re-answering an old episode
does not create a new experience with that background, and a complete work cycle
must not become a mandatory feature tour.

For broad product feedback, choose interview angles that serve the decision:
value, understanding, capability, information, effort, presentation, control and
future use are possible dimensions, not a quota of complaints. Use concrete
experienced moments, allow no issue or insufficient experience, and distinguish
future-use hypotheses from observed effects. Remove repetitive main questions
before adding more. Questions are introduced only after experience.

Researchers select dimensions and follow-ups; participants need not invent
advantages and disadvantages for every dimension. Separate experience, personal
judgment and future wishes. “Not found” does not mean “does not exist.” See the
[agent-work supervision comparison configuration](../use_cases/Live%20Prototype%20Comparison/README.md).

## 4. Prepare Authorized Persona Data

A Persona source should document:

- provenance, consent, permitted use, retention, and publication rules;
- stable Persona IDs;
- field definitions and missing-value conventions;
- languages and markets;
- whether attributes are observed, inferred, generated, or fixed;
- known coverage gaps and biases.

Do not publish raw profiles or additional profile fields merely because they were used internally.

If no suitable authorized pool exists and the team explicitly chooses synthetic
generation, keep it as a separate reviewed job:

```powershell
genesia personas create --output persona-plan
genesia personas review persona-plan/cohort-plan.yaml
genesia personas confirm persona-plan/cohort-plan.yaml
genesia personas generate persona-plan/cohort-plan.yaml --output persona-generations/study
genesia personas approve persona-generations/study
genesia personas validate persona-generations/study
```

The user must review and confirm the exact Cohort Plan before generation. A managed
generated cohort may require all approved Personas to remain together; do not sample a
subset and assume its quotas survive. Generated coverage is not population prevalence,
statistical representativeness, or observed human-participant evidence.

## 5. Design the Persona Distribution

### 5.1 Diversity Is Not Forced Disagreement

Select diverse contexts that may plausibly change needs, behavior, interpretation, or constraints. Never require Personas to choose different options or manufacture disagreement.

### 5.2 Prefer Product-Relevant Dimensions

Depending on the product, useful dimensions may include:

- frequency and depth of product use;
- technical confidence and help-seeking behavior;
- device and input mode;
- accessibility needs;
- workflow, environment, time pressure, and collaboration pattern;
- risk tolerance, privacy sensitivity, and decision style;
- domain expertise;
- familiarity with comparable products;
- language and market context.

Age, occupation, gender, nationality, MBTI, or income should not be used as shortcuts for behavior. They may provide context only when the supplied profile and research question make them relevant.

### 5.3 Explicit vs Sampled Cohorts

Use explicit IDs when the cohort has been deliberately reviewed. Use size plus a recorded seed for reproducible sampling.

```yaml
cohort:
  source: path/to/authorized-personas.tsv
  size: 20
  seed: 1813573689
  ids: [PERSONA_01, PERSONA_02, PERSONA_03]
```

When `ids` is present, it takes precedence over random sampling. Validate that every ID exists exactly once and that the count equals `size`.

### 5.4 Sample Size

Synthetic sample size is a coverage and stability choice, not a claim of statistical representativeness.

- 2–5: prompt, workflow, and evidence-pipeline acceptance;
- 8–15: exploratory pattern discovery;
- 20+: broader qualitative coverage and minority-perspective discovery;
- larger samples: justified only when the question, budget, and analysis plan need them.

## 6. Write Research Objectives

Each objective should describe a decision-relevant unknown. Avoid objectives such as “find usability problems” that assume problems must exist.

```yaml
study:
  objectives:
    - id: discoverability
      description: Understand how people locate controls relevant to their own goals
    - id: comprehension
      description: Understand which tried controls and relationships are clear or uncertain
    - id: distinctive_perspectives
      description: Preserve uncommon feedback that changes a design implication or critical uncertainty
```

## 7. Write the Research Questions

### 7.1 Question Types

Use:

- `purpose: context` for supported background needed to interpret the session;
- default experience questions for what happened, reactions, consequences, and judgments;
- `purpose: reflection` for wishes and suggestions that do not prove a defect;
- `candidate` for version-specific comparison questions;
- `explain: true` when a choice needs a separate reason;
- explicit tie, no-preference, not-applicable, or insufficient-experience options where appropriate.

### 7.2 Good Question Characteristics

A good question:

- asks one clear thing;
- is answerable from the Persona profile or encountered experience;
- requests a concrete moment and consequence when evaluating an interface;
- permits no issue, no change, uncertainty, or indifference;
- does not require every Persona to review every control;
- separates liking the outcome from evaluating the interaction;
- does not invite claims about untried behavior.

### 7.3 Analysis Grouping Contract

For every configured question, analysis should receive:

1. the exact question;
2. all eligible Persona answers and reasons for that question;
3. the relevant Persona attributes;
4. question-level code statistics;
5. the report requirements.

The model first forms bounded question findings. A later stage receives all question findings and produces cross-question insights, recommendations, and the executive summary. Do not dump ungrouped Persona answers into one final prompt.

## 8. Configure Evidence and Experience

For bounded live journeys, prefer complete evidence and ensure the image bound covers every observation.

```yaml
methods:
  - id: post_use_interview
    kind: interview
    batch_size: 14
    evidence_mode: complete
    max_images: 20
    max_followups: 0
```

Keep natural exploration unconstrained unless the study explicitly requires a controlled task:

```yaml
environment:
  mode: live
  max_steps: 18
  min_actions_before_stop: 0
  required_url_fragments_before_stop: []
```

Trace is not the main report input. Preserve it as auxiliary evidence for checking experience claims. Report synthesis should use research goals, exact questions, original answers, relevant Persona attributes, code statistics, and report requirements. Evidence review may retrieve only the action fragments linked to a claim.

## 9. Configure the Model, Concurrency, and Budget

Pin the provider and exact model. Never silently fall back.

```yaml
model:
  provider: openai_compatible
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: YOUR_MODEL_ID
  temperature: 0.85
  timeout_seconds: 150
  max_tokens: 6000
  attempts: 3
execution:
  max_concurrent_personas: 5
  max_concurrent_model_calls: 5
budget:
  max_calls: 960
  max_tokens: 48000000
  max_seconds: 7200
  protection:
    research_fraction: 0.3
    analysis_fraction: 0.25
```

Budget for the worst allowed retries, but report actual calls and provider-reported tokens. Concurrency must not parallelize actions inside one Persona.

## 10. Define the Report Before Running

Specify what decisions the report must support. Do not use report dimensions as section quotas.

A strong main report should usually contain:

1. a concise executive summary;
2. a small bounded set of evidence-grounded insights;
3. shared patterns and decision-relevant distinctive perspectives;
4. counterevidence and critical uncertainty;
5. two to four prioritized recommendations;
6. confidence and limitations.

Do not repeat the same conclusion in the summary, candidate sections, cross-candidate section, and recommendation rationale. Do not list every Persona or every configured segment in the main report.

### Shared and Distinctive Findings

- A shared finding may have broad support but must still state the consequence and tradeoff.
- A distinctive finding may have one Persona when it changes the design implication, recommendation, or critical uncertainty.
- Do not promote novelty for its own sake.
- Do not merge feedback about different controls when it would lead to different design actions.

Do not merge controls merely because few participants mention each one.

### Main Report vs Appendix

Main report:

- conclusions, implications, recommendations, uncertainty;
- limited descriptive choice totals when useful.

Appendix and structured artifacts:

- complete original answers;
- full descriptive and segment statistics;
- Persona-level paths and outcomes;
- action traces and screenshots;
- analysis provenance, excluded findings, and unrepresented answers.

## 11. Configure Segments Carefully

Segments should answer a real hypothesis. Do not configure age, region, occupation, or personality merely because the fields exist.

```yaml
study:
  segments:
    experience_level:
      source: Digital Behavior & Online Habits.tech_adoption
    age_group:
      source: Core Identity.age
      buckets: ["<30", "30-39", "40-49", "50-59", "60+"]
```

Small groups are descriptive only. Segment configuration makes statistics available; it does not require the final report to list every group. Only evidence-supported segment conclusions belong in main findings.

## 12. Permissions and Data Handling

Make permissions explicit:

```yaml
permissions:
  send_persona: true
  send_materials: true
  send_screenshots: true
```

Document whether the configured provider is local or may forward data remotely. Keep raw runs, profiles, screenshots, and private traces untracked unless publication is explicitly authorized.

## 13. Preflight, Run, and Verify

```powershell
python -m genesia preflight path/to/task.yaml
python -m genesia preflight path/to/task.yaml --network
python -m genesia run path/to/task.yaml
python -m genesia verify path/to/runs/RUN_ID
```

Before inference, verify prototype rendering, cohort uniqueness, question coverage, complete-image bounds, model availability, permissions, and protected budgets.

## 14. Acceptance Checklist

### Study integrity

- requested, valid, invalid, and missing Persona-method responses are reported separately;
- no participant or answer is spliced from another run;
- model, cohort IDs, seed, profile hash, prototype provenance, and task are recorded;
- evidence verification passes;
- failures and retries remain visible.

### Persona quality

- answers remain consistent with the complete profile and actual experience;
- wording is not a demographic or occupational stereotype;
- Personas may agree, disagree, be uncertain, or have no strong reaction;
- no hidden product behavior or prior experience is invented;
- pipeline success is not presented as proof of human realism.

### Analysis quality

- every question is analyzed with all eligible answers grouped together;
- every eligible answer is reviewed;
- shared and distinctive findings are both considered;
- findings retain support, counterevidence, consequence, design implication, and uncertainty;
- recommendations cite findings and distinguish correction, investigation, and enhancement;
- action traces are auxiliary verification, not repeated report input.

### Report quality

- conclusions answer the research objectives;
- the report is concise and does not repeat one theme under several headings;
- configured dimensions are synthesized into conclusions rather than listed mechanically;
- the main report contains only decision-relevant insights;
- raw answers, full statistics, paths, and traces remain available in the appendix;
- synthetic results are not presented as real-user prevalence or causal evidence.

## 15. Minimal Task Skeleton

```yaml
schema_version: "0.2"
goal: >-
  Explore the implemented feature as yourself and form an informed view through
  personally relevant hands-on use. Stop when further trials offer little value.
cohort:
  source: path/to/authorized-personas.tsv
  size: 20
  seed: 12345
environment:
  mode: live
  start_url: http://127.0.0.1:5173/
  max_steps: 18
  min_actions_before_stop: 0
  required_url_fragments_before_stop: []
study:
  min_personas: 20
  objectives:
    - id: journey
      description: Understand strengths, friction, and consequences in the experienced journey
    - id: distinctive
      description: Preserve uncommon feedback that changes a design implication or uncertainty
methods:
  - id: post_use_interview
    kind: interview
    batch_size: 14
    evidence_mode: complete
    max_images: 20
    max_followups: 0
    questions:
      - id: context
        purpose: context
        feedback_role: context
        text: What supplied habit or need matters when interpreting this session?
      - id: experience
        feedback_role: journey
        text: Which concrete moment best explains what worked or did not work for you, and why?
        objective_ids: [journey]
      - id: priority
        purpose: reflection
        feedback_role: suggestion
        text: What single change, if any, should the team prioritize based on your experience?
        objective_ids: [journey, distinctive]
model:
  provider: openai_compatible
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: YOUR_MODEL_ID
  temperature: 0.85
  timeout_seconds: 150
  max_tokens: 6000
  attempts: 3
permissions:
  send_persona: true
  send_materials: true
  send_screenshots: true
execution:
  max_concurrent_personas: 5
  max_concurrent_model_calls: 5
budget:
  max_calls: 960
  max_tokens: 48000000
  max_seconds: 7200
  protection:
    research_fraction: 0.3
    analysis_fraction: 0.25
insight:
  language: en
  context_window: 200000
  input_budget_ratio: 0.6
  chunk_target_tokens: 65000
  max_findings: 8
output_dir: runs/private-study
```

Treat this skeleton as a starting point. Change the goal, objectives, questions, cohort, prototype, budgets, and report requirements together for the actual study.

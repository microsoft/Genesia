---
name: genesia-live-prototype
description: 'Run and review evidence-grounded synthetic Persona research against an isolated live HTTP(S) prototype using the Genesia SDK and CLI. Use for prototype usability, autonomous Persona interaction, feature discovery, task.yaml setup, cohort selection, live preflight, run verification, interaction-path review, and derived GIF samples. This Skill is only for live prototype input, not all Genesia research modes.'
argument-hint: '<prototype URL, research goal, Persona JSON/TSV, task.yaml, or run directory>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Live Prototype

Use Genesia as the only runtime for a live-prototype study. This Skill configures and invokes the public CLI/SDK; it does not reimplement Persona decisions, Playwright, interviews, synthesis, status calculation or evidence validation.

All Persona intent, action and research calls use Genesia's packaged `src/genesia/resources/persona_role.md` policy. Survey-specific completeness and question-type rules are added only when a configured method is a survey.

```text
user intent -> this Skill -> live task.yaml + supplied Persona data -> Genesia CLI / SDK
                                                               -> PersonaAgent
                                                               -> LiveEnvironment
                                                               -> evidence + ResearchResult
```

This Skill covers only `environment.mode: live`. For supplied recordings use `/genesia-recorded-prototype`; for profile-only questionnaires use `/genesia-persona-survey`. For other raw documents, screenshots or Figma inputs, use the public SDK/CLI with `environment.mode: auto`. Numbered Cards and canonical Graphs are prepared/debug inputs, not a required preprocessing step for ordinary materials.

## Architecture Contract

Input kind, interaction mode and research method are separate. A live study may use interview, survey, design review or task outcome review after interaction; a survey method does not change the environment to survey-only mode.

Live runs bypass `EnvironmentBuilderAgent`: Playwright directly supplies observations and executes authorized actions. There is no live post-compilation into Context/Cards/Graph. Do not insert a builder or make compilation artifacts a prerequisite for running or reviewing a live study.

The public API schedules one continuous PersonaAgent and session per participant. Builder and action prompts never receive method questions; the same agent enters the research gate after experience using its identity, intent and encountered evidence. Provider-side conversation memory is not assumed, and the Skill must not create a replacement interview Persona.

Read [live task authoring](./references/live-task-authoring.md) when creating or changing a study. Read [result review](./references/result-review.md) before interpreting or publishing outputs. Provider configuration is documented in [model providers](./references/model-providers.md).

## Runtime Boundary

Read [analysis and reports](../../../docs/analysis-and-reports.md) for `execution`,
`insight`, `doctor`, `run --open` and `report RUN_DIR --open`. Persona concurrency
is opt-in; never parallelize actions inside one Persona or implement your own pool.
Use isolated server-side data as well as separate browser contexts.

For staged comparisons, use same-origin `environment.handoff_urls` and the runtime's
backstage `advance` action rather than injecting research navigation into the product.
Use `screenshot_width` / `screenshot_quality` to reduce the single saved image while
preserving the browser viewport layout. Live `scroll` reveals below-fold content in
the primary visible scroll container and becomes part of the evidence trace.
Browser `back` is offered only when Chromium reports a previous same-origin history
entry. Unsafe Back attempts are rejected before navigation so SPA state is preserved;
visible in-product navigation remains available independently.

Set `insight.language` explicitly for report prose (`en` or `zh-CN`). When only
analysis needs revision, `genesia analyze RUN_DIR --language en --focus "Decision"`
invokes models on the saved answers into a new run with lineage; repeat `--focus`
for additional priorities. It never repeats browser use. This is different from
`report`, which only renders without model calls.

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

Never call a model API directly from the Skill. Never create a second Playwright/Persona loop, copy prompts or validators from `src/genesia`, execute model-generated selectors/scripts, silently switch providers, fabricate responses, relabel status or combine runs.

## Procedure

### 1. Resolve Inputs

Identify:

- isolated prototype URL and starting state;
- non-leading participant goal and realistic stopping condition;
- user-provided authorized Persona JSON/TSV path, or a validated Genesia-generated
  `personas.json`, plus cohort size and selection requirements;
- research objectives and episode-grounded questions;
- model provider, endpoint, model ID, permissions and budgets;
- output and sharing constraints.

Do not invent Persona profiles. Use an existing authorized Persona dataset supplied by
the user. If the user explicitly needs a new synthetic cohort, use
`/genesia-persona-generation` as a separate planning, confirmation, generation and
validation workflow before authoring this study. For a managed generated cohort, run
`genesia personas validate GENERATION_DIR` and preserve any full-cohort requirement;
do not sample a subset to bypass the approved plan. Do not copy private Persona data
into tracked Skill assets or public samples.

### 2. Author The Live Task

Copy [live task template](./assets/live-task.yaml), replace `PATH_TO_PERSONAS.json`, and adapt the URL, goal, objectives, questions, model and budgets together. A URL-only replacement is not a research design. Keep objectives/criteria in `study` and post-experience questions in `methods`.

Use `environment.prototype.scope` and `known_limitations` for the supplied prototype
boundary, not a click itinerary or an invented inventory of missing features. Current
action calls provide a short personal intent and expected result. Code later binds each
action to compact before/after evidence and adjacent images in one ordered
`experience_timeline`; it does not replay optional legacy `experience_notes` as prepared
answers. Expectations remain participant intent, not certified observations. Known
placeholders belong in limits, not product findings.

Enable `budget.protection` for new studies. The template reserves 30% of calls/tokens
for per-Persona research and 25% for analysis, with corresponding time windows. Review
the preflight budget plan and complete-image bound before inference. Exploration may
stop with `exploration_budget` and continue to fixed questions; do not relabel that
as satisfaction. Protection cannot guarantee provider health or arbitrary input sizes.

For natural exploration use `min_actions_before_stop: 0` and no required URL fragments.
Only enable coverage gates for an explicitly controlled study; report forced continuation
as a protocol effect, not spontaneous behavior. Distinguish directed exploration from a
specific task-completion goal. For exploration, name the feature scope and ask Personas
to try personally relevant visible options, compare outcomes, adjust or revisit as useful,
and form an informed view. An acceptable starting state is not sufficient exploration.
Do not invent unrelated needs, mandate every page, force different paths, or judge depth
by click count. Retaining defaults after trials and stopping for a genuine blocker or
unwillingness remain valid; record limited experience rather than forcing continuation.
Prefer `evidence_mode: complete` with a sufficient `max_images` bound for short journeys.
Complete mode fails rather than silently sampling beyond the bound. Preserve explicit
`send_persona`, `send_materials` and `send_screenshots` consent.

Mark questions with `purpose: context`, `experience` (default) or `reflection`.
For prototype feedback studies, also set `feedback_role` (`overall`, `journey`,
`strength`, `friction`, `comparison`, `preference`, `design`, `suggestion` or
`verdict`). Ask the participant to evaluate specific implemented design and explain
why it mattered, not merely repeat actions, completion or confidence. New reports lead
with Summary and prioritized Next actions, then expand the same Findings, followed by
brief Limitations and Appendix / Evidence. Strengths, friction, tradeoffs, minority and
configured segment findings remain part of that analysis; not every finding needs an
action. Traces and individual feedback remain supporting evidence. Legacy reports retain
their previous structure. `basis=automation` answers are excluded from product synthesis and
shown as unavailable product feedback; they are not product findings.
Context answers describe supported background, not fabricated life history; reflection
answers are wishes, not evidence of a defect. Ask concrete expectation/result/impact
questions and allow no difficulty or no change needed. Keep `max_followups: 0` for
the current fixed-guide workflow. Do not add dynamic probes without a separate request.

### 3. Validate Without Model Calls

```powershell
python -m genesia preflight path/to/task.yaml
```

Fix schema, path, Persona, permission, sample and readiness errors at their source. Separately confirm the prototype URL renders. Then check the configured provider/model only when the user intends to run:

```powershell
python -m genesia preflight path/to/task.yaml --network
```

A catalog check does not prove inference or prototype health.

### 4. Run One Intact Study

```powershell
python -m genesia run path/to/task.yaml
```

When the user explicitly wants only original episodes and answers for later analysis,
use `python -m genesia run path/to/task.yaml --research-only`. This deliberately writes
no report or analysis artifacts and cannot be combined with `--open`. A completed
research-only run certifies execution completeness, not analysis or Persona realism.

Keep the exact run intact. If it is partial or failed, inspect it before deciding whether a new independent run is justified. Never splice participants, frames or interviews across runs.

### 5. Verify And Review

```powershell
python -m genesia verify path/to/runs/RUN_ID
```

Inspect `run_manifest.json`, `study_review.json`, `research_result.json`, `report.md`, evidence verification, and each Persona's path, outcome, failed actions and response validity. Separate browser execution, Persona self-report, model synthesis and runtime failures. Findings cite validated responses, whose evidence must belong to that participant's encountered observations. `verify` checks artifact hashes and path confinement, not the truth of natural-language claims.

### 6. Deliver

For a full or analysis-only run, start with `report.html` and its TL;DR; `report.md`
is the same report. Inspect `appendix.html` / `appendix.md` for original responses
and traces, and `analysis_input.json` / `analysis_provenance.json` for answer IDs,
exclusions, question stages and processing coverage. Research-only runs intentionally
have none of these report/analysis files; inspect immutable answers and episodes, or
run `genesia analyze` into a new lineage-linked directory. Match quotes to exact
answers. Processing coverage does not prove semantic completeness. Diagnostic reports
may lack analysis artifacts.

Analysis groups every eligible original answer under its exact question before
composition. Inspect `reviewed_answer_ids`, question-stage answer IDs and final
`finding_sources`. Support counts derive from answer ownership; the model still decides
semantic relevance. Preserve system stop reasons and prototype boundaries. Question
findings are bounded themes without quotations or recommendations; `max_findings` is an
upper bound, not a quota. Oversized questions may split into explicit chunks, but their
combined IDs must still cover every eligible answer.
Do not automatically run another study or analysis to obtain a preferred result.

Report the exact run ID/status, requested Personas and valid/invalid/missing Persona-method responses separately, per-Persona steps/outcomes, failed actions, errors, evidence integrity and output paths. These are synthetic Persona sessions, not observed real-user results. A case-specific exporter may create GIFs only from a verified run; GIFs remain derived presentation artifacts and cannot change source status.

## Reusable Case

```text
use_cases/<live-case>/
  run.py                 # public SDK only
  task.yaml
  README.md
  sample/                # reviewed derived output
  runs/                  # private/ignored raw runs
```

Keep private Persona data outside tracked case/Skill assets and pass it through `cohort.source` or a runner override. A case runner may import `load_task`, `preflight`, `run`, `TaskSpec` and `ResearchResult`; it must not import internal Agent or browser modules.

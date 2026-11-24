---
name: genesia-live-comparison
description: 'Run or rerun evidence-grounded staged live prototype comparisons with Genesia. Use when the user asks to compare Version A/B or multiple live variants, create another comparison case, choose a Persona cohort or sample size, switch models, clone an existing comparison task, start prototypes, preflight, run, verify, review, or export a shareable comparison report. Not for a single prototype, recordings, or survey-only research.'
argument-hint: '<case or task path, version URLs, cohort or sample size, model, and optional label>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Live Comparison

Run a new intact staged comparison by configuring and calling the public Genesia
CLI. Reuse an existing comparison case when available. Do not implement a separate
Persona, browser, interview, synthesis, report, or validation loop.

## Scope

Use this Skill when every participant experiences two or more live prototype
variants in one continuous Genesia session and gives feedback on each before comparing them.
The variants may represent branches, designs, releases, configurations, or other
authorized prototype states.

Use `genesia-live-prototype` for a single live prototype, `genesia-recorded-prototype`
for fixed recordings, and `genesia-persona-survey` for profile-only surveys.

## Required Inputs

Resolve these before creating or running a task:

1. Existing case directory or the new task location.
2. Version labels, URLs, provenance, and intended sequence.
3. How each authorized prototype is prepared and served.
4. Participant exploration scope and questions covering each candidate and the comparison.
5. Persona source and cohort size or explicit IDs.
6. Provider, model, endpoint, report language, and permission to send profiles,
   materials, and screenshots.
7. Whether the user wants only a private run or also a reviewed shareable sample.

Ask only for values that cannot be inferred safely. Never infer permission to use
a different provider, Persona source, prototype revision, or publication target.

## Comparison Contract

A staged comparison task must:

- use `environment.mode: live`;
- set the first variant in `environment.start_url`;
- list later variants in sequence under `environment.handoff_urls`;
- set `environment.candidate_labels` in that exact URL order, especially for
  counterbalanced tasks; never infer stage labels from questionnaire order;
- keep every handoff URL on the same authorized origin;
- use Genesia's backstage `advance` action instead of injected study navigation;
- open each variant in isolated browser state while retaining the same Persona's
  identity and recorded comparison context;
- let the same Persona autonomously try relevant interactions in every variant;
- use exploration to build firsthand context about interaction, journey and visual design,
  not to force identical settings, routes, click counts or completion states;
- use matched tasks only when the user explicitly requests a controlled task study;
- distinguish interface experience from preference for the resulting content;
- permit ties, no meaningful difference, insufficient experience, and stopping;
- disclose fixed order, learning, anchoring, carryover, and recency effects;
- treat prototype gaps and browser/model failures as limitations, not product
  findings.

Do not claim causal A/B effects from a fixed-order synthetic comparison. If an
existing case uses counterbalancing or randomized order, preserve and verify that
explicit protocol rather than silently converting it to a fixed sequence.

## Reuse Or Create A Case

For an existing case, read its task, README, server/bootstrap code, latest reviewed
run, and sample manifest before changing anything. Identify the code that owns
prototype serving and the exact version provenance. Do not infer a version from a
folder name alone.

Create a new task beside the canonical task, such as `task-<label>.yaml`.
Never overwrite a canonical task, prior task, source run, or sample. Do not
commit a generated task unless the user asks.

For a new case, follow the repository convention:

```text
use_cases/<comparison-case>/
  task.yaml
  README.md
  serve.py              # only when a local server is required
  runs/
```

Prototype binaries, private Persona data, screenshots, and raw runs stay in
ignored/private locations unless redistribution is explicitly authorized.

## Cohort Rules

Inspect `cohort.ids` before every run. Running a task with fixed IDs repeats those
Personas; it does not select a different cohort automatically.

Use one of these modes:

- **Explicit cohort:** set `cohort.size` and `cohort.ids` to supplied authorized
  IDs.
- **Sampled cohort:** remove `cohort.ids`, set `cohort.size`, and record
  `cohort.seed` so Genesia samples reproducibly using size + seed from the
  authorized source.

When IDs are supplied, validate that each exists exactly once and the final count
equals `cohort.size`. Shareable aliases are not raw Persona IDs. Never publish
additional profile rows or fields.

If `cohort.source` is a Genesia-generated `personas.json`, run
`genesia personas validate GENERATION_DIR` before study preflight. The managed
generation manifest may require the complete approved cohort; never sample a subset
to preserve an old task size. Generate and confirm a new cohort instead.

## Author The Task

Start from the closest reviewed comparison task. Preserve together:

- personally grounded exploration and realistic stopping conditions within each version;
- intended version order and backstage handoffs;
- non-leading objectives and episode-grounded questions;
- prototype scope and known limitations;
- valid tie and insufficient-experience responses;
- `evidence_mode: complete` with `max_images >= max_steps + 1` for bounded
  journeys, or an explicitly reviewed sampling policy;
- explicit data and screenshot permissions;
- `insight.language`, optional `insight.focus`, and report constraints.

Use question `candidate` labels to retain per-candidate feedback. Ask what worked,
what bothered this person and what they would keep/change in each candidate before
asking for comparative preference. Choice questions may set `explain: true`; the
answer then keeps the option in `value` and its explanation in `reason`. Do not
make every participant recite research disclaimers. A shared questionnaire and
batched answering do not require identical opinions or a switch to a UX-reviewer role.

Update cohort, model, concurrency, budget, URLs, and task label coherently. Do not
reuse a small-cohort budget blindly for a larger cohort. Keep concurrency bounded
by available browser and model capacity. Keep `budget.protection` enabled so
per-Persona research and final analysis retain reserved capacity.

Changing `model.model` changes Persona intent, action, interview, synthesis, and
report-composition calls in that run. HTML, Markdown, GIF, and standalone rendering
remain deterministic code paths. Never silently use a fallback model.

## Prepare The Prototypes

Follow the case README or authorized bootstrap to prepare the exact pinned builds.
Start the case server when required, then confirm every configured URL renders the
intended variant before inference. Record branch, commit, artifact, recording, or
other available provenance for each version.

If the configured port is occupied, choose another and update `start_url` and all
`handoff_urls` to the same origin. Do not substitute newer builds merely because
the pinned artifacts are unavailable.

## Preflight And Run

From the repository root, use the Python 3.11+ environment containing Genesia,
Playwright, and Chromium. If the package is not installed editable, set
`PYTHONPATH=src`.

Validate schema, paths, Persona selection, budgets, and local readiness without
model calls:

```powershell
python -m genesia preflight path/to/task-<label>.yaml
```

Then validate the configured provider/model and network dependencies:

```powershell
python -m genesia preflight path/to/task-<label>.yaml --network
```

Do not start inference until both checks pass and every prototype route renders.
Run one intact study:

```powershell
python -m genesia run path/to/task-<label>.yaml
```

Use `--research-only` only when the user explicitly wants immutable journeys and
answers without synthesis or report rendering. It cannot be combined with `--open`.
Analyze that exact saved run later with repeatable `--focus` options rather than
repeating browser sessions.

Capture the exact returned run directory and run ID. Do not splice participants,
frames, interviews, or analysis from different runs. Review a partial or failed
run before deciding whether a new independent run is justified.

## Verify And Review

Verify the exact new run:

```powershell
python -m genesia verify path/to/runs/<RUN_ID>
```

Review at minimum:

- `run_manifest.json` for task, model, cohort, budget, errors, lineage, and status;
- `research_result.json` for valid/invalid/missing responses and failed actions;
- `analysis_provenance.json` for eligible/reviewed answers and stage coverage when
  analysis ran;
- `report.html` and `appendix.html` for conclusions, answers, and traces when reports
  were rendered;
- each participant's actual exposure, interests, reactions, stop reason and
  feedback basis; differing paths are expected and are not incomplete by themselves;
- `evidence_verification.json` and `genesia verify` for artifact integrity.

Check that claimed differences come from comparable attempted goals, not favorite
content, unmatched state, order alone, an untried route, prototype boundaries, or
automation failures. Processing coverage and artifact hashes do not prove semantic
truth. Treat preference counts as descriptive synthetic results, not population
estimates.

## Optional Analysis And Outputs

A completed full run contains `report.html` and `report.md`; a research-only run
deliberately does not. Re-rendering a report from an already analyzed structured result
does not invoke a model. `genesia analyze RUN_DIR --language en --focus "Version choice"`
creates a new analysis run using the configured model and saved answers without
repeating browser use; repeat `--focus` for multiple priorities.
New reports organize Summary, Next actions, Findings, brief Limitations and Appendix /
Evidence from one evidence-bound finding set. Check that the summary agrees with action
priority, candidate targets remain explicit, and important minority or configured segment
views are not buried. Decision-prioritized actions are not reordered by frequency-based
scores; legacy saved reports retain their previous structure.

Create or replace a tracked privacy-minimized sample only when the user explicitly
requests publication. Use the case's existing exporter where available, alias
participants, remove raw Persona/session IDs and private traces, derive media only
from hash-verified evidence, update the manifest, run privacy tests, and inspect the
standalone report in a browser. Never make an unreviewed run the latest sample
automatically.

## Completion Report

Return:

- case and task paths, seed, requested and actual cohort IDs/count;
- provider/model and exact provenance for every variant;
- run ID and completed/partial/failed status;
- valid/invalid/missing responses and failed actions;
- analysis answer coverage and evidence verification result;
- report paths, order effects, prototype limits, and other caveats;
- whether a shareable sample was intentionally unchanged or updated.
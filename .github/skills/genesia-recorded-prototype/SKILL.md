---
name: genesia-recorded-prototype
description: 'Run and review evidence-grounded synthetic Persona research from recordings using the Genesia SDK and CLI. Use for MP4/AVI recordings, chronological frame manifests, optional input traces, mixed recording materials, auto environment assessment, Context/Cards/Graph readiness review, recorded-path walkthroughs, task.yaml setup, prepare/run/verify, and episode-grounded research. This Skill reviews fixed recorded journeys, not autonomous live prototype use.'
argument-hint: '<video or frame manifest, optional trace, Persona JSON/TSV, research goal, task.yaml, or run directory>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Recorded Prototype

Use Genesia as the only runtime for research from a fixed recorded prototype journey. This Skill configures and invokes the public CLI/SDK; it does not reimplement video decoding, frame sampling, trace parsing, UI-card extraction, Persona research, synthesis, status calculation or evidence validation.

All Persona intent, walkthrough decisions and research calls use Genesia's packaged `src/genesia/resources/persona_role.md` policy. Survey-specific completeness and question-type rules are added only when a configured method is a survey.

```text
video / frame manifest + optional trace + supplied Persona data
  -> this Skill -> recorded task.yaml -> Genesia CLI / SDK
                                      -> bounded source normalization
                                      -> EnvironmentBuilderAgent + provenance validation
                                      -> Context / Cards / Graph
                                      -> evidence-supported review environment
                                      -> Persona research + evidence + ResearchResult
```

Use `environment.mode: auto` for raw `source.kind: video` or `recording`, optionally with supporting documents or images. Source kind, runtime interaction mode and research method are separate choices: a recording does not guarantee UI states or a navigable graph. Retain explicit `walkthrough` only when the caller intentionally requests the legacy prepared/editorial sequence. Neither mode represents autonomous use of the recorded application. For a running HTTP(S) prototype where Personas choose browser actions, use `/genesia-live-prototype`; for profile-only questionnaires use `/genesia-persona-survey`.

The core assesses mixed materials together and validates citations before choosing Context review, Card review, a single recorded-path walkthrough or captured-graph choice. Missing UI or connected transitions can legitimately yield Context or Cards; provider/model failures are not readiness downgrades. Unbound material remains supplemental background. Do not create a second builder or turn frame/card numbering into product navigation.

Read [recording inputs](./references/recording-inputs.md) before configuring sources. Read [recorded-result review](./references/result-review.md) before interpreting outputs. Provider configuration is summarized in [model providers](./references/model-providers.md).

## Runtime Boundary

Read [analysis and reports](../../../docs/analysis-and-reports.md) for bounded
Persona concurrency, staged per-question synthesis and unified reports. Use the public API;
do not create a second worker pool. One Persona's captured journey stays sequential.

`insight.language` chooses `en` or `zh-CN`.
`genesia analyze RUN_DIR --language en --focus "Decision"` performs new model
synthesis of saved answers into a distinct run with source lineage, without re-running
participant sessions. Repeat `--focus` for more priorities. `report` only re-renders.

Always call public entry points:

```powershell
python -m genesia preflight TASK
python -m genesia preflight TASK --network
python -m genesia prepare TASK
python -m genesia run TASK
python -m genesia verify RUN_DIR
```

Or:

```python
from genesia import load_task, preflight, prepare, run
```

Never decode video, sample frames, align traces, build cards or create a Persona walkthrough in Skill scripts. Never call a model provider directly, silently switch providers, fabricate missing frames/answers, relabel status or combine runs.

## Procedure

### 1. Resolve Inputs

Identify:

- MP4/AVI recording or chronological frame manifest;
- optional trace containing relative timestamps;
- user-supplied authorized Persona JSON/TSV;
- what the recording depicts and which questions it can answer;
- sampling interval/frame cap and any known transient states;
- research methods, provider, permissions, budgets and output constraints.

Do not invent Persona profiles. Use an authorized external JSON/TSV or a validated
Genesia-generated `personas.json`. For a managed generation, run
`genesia personas validate GENERATION_DIR` and preserve a required full cohort; use
`/genesia-persona-generation` only when the user explicitly asks to create a new one.
Do not copy private Persona data, recordings, traces or derived frames into tracked
Skill assets or public samples.

### 2. Inspect The Recording Contract

For raw video, confirm the file is a scoped recording under one hour and 2GB. Choose `sample_seconds` and `max_frames` deliberately. Uniform sampling always preserves bounded chronology but may miss brief states.

Raw video decoding requires the media extra:

```powershell
python -m pip install -e ".[media]"
```

An already prepared frame manifest does not require video decoding.

For a frame manifest, verify 1-120 chronological PNG/JPEG/WebP paths confined below the manifest directory. Optional timestamps must be finite and nondecreasing.

A trace is supplementary evidence. It may describe inputs, but alignment does not prove that a click succeeded or caused the next frame.

### 3. Author The Recorded Task

Copy [recorded task template](./assets/recorded-task.yaml), replace `PATH_TO_PERSONAS.json` and `PATH_TO_RECORDING.mp4`, then adapt the goal, objectives, questions, provider and budgets together.

Use `environment.mode: auto`. Do not require users to author numbered Cards or a canonical Graph for raw inputs. Personas review only the environment supported by the supplied evidence; they cannot operate the recorded application. Questions should distinguish visible states, recorded trace events, Persona interpretation and unverified product behavior.

Put objectives and evaluation criteria in `study`, and questions in `methods`. Builder and action calls do not receive research questions. The same PersonaAgent and session carry identity, intent and encountered evidence through experience and into the research gate; the Skill must not resample a Persona for the interview.

### 4. Validate Before Model Calls

```powershell
python -m genesia preflight path/to/task.yaml
python -m genesia preflight path/to/task.yaml --network
```

The first command checks schema, paths, Persona sample, media dependencies, permissions and readiness. The second checks the configured provider/model. Neither proves decode quality or semantic fidelity.

### 5. Prepare And Inspect

Run preparation before participant sessions:

```powershell
python -m genesia prepare path/to/task.yaml
```

Inspect:

- `preparation.json`, including `research_readiness`, and `study_review.json`;
- sampled source evidence and timestamps;
- `environment_readiness.json` and `environment_build.json`: assessment, validated output level, citations, issues and supplemental Context;
- `ui_cards.json` and card Markdown when Cards were produced;
- `state_graph.json` / `states.mmd` when a Graph was produced;
- trace events attached to sampled intervals;
- fidelity warnings, missing transient states and over-merged states.

Accept Context or Cards when they support the research question; do not force graph construction to make preparation look complete. Text-backed transitions need validated source text. Runtime `recorded_order` transitions require adjacent identified frames in the same recording with increasing timestamps; file ordering and separate recordings do not establish transitions. Alignment and citations do not establish semantic correctness or causality.

Revise the task or recording if preparation is not fit for purpose. Do not manually rewrite evidence to make it look complete. `prepare` is a separate review run, not a compiled input automatically reused by `run`; inspect the actual study's compilation and readiness again.

### 6. Run One Intact Study

```powershell
python -m genesia run path/to/task.yaml
```

Use `--research-only` only when the user explicitly wants original episodes and answers
without synthesis or reports. It cannot be combined with `--open`; analyze the saved run
later without repeating participant sessions.

Each Persona receives an independent session in the compiled environment. Read the actual runtime mode from its episode: Context/Card review, recorded-path walkthrough or captured-graph choice have different affordances. Even graph choices operate on captured evidence, not the recorded application. Keep the exact run intact; never splice participants or evidence across runs.

### 7. Verify And Deliver

For a full or analysis-only run, open `report.html` (TL;DR first). `report.md` is the
same report; original answers, traces and audits are in `appendix.html` /
`appendix.md`. Review `analysis_input.json` and `analysis_provenance.json` when
analysis ran, for exact questions, answer IDs, exclusions and processing coverage.
Research-only runs intentionally omit these files. `genesia report RUN_DIR --open`
re-renders without model calls, not re-analysis. Never describe recorded evidence as
live use.
New reports present Summary, prioritized Next actions, the same Findings expanded,
brief Limitations and Appendix / Evidence. Review candidate attribution, decision-relevant
minority and configured segment views, and whether the summary agrees with action order.
Recorded paths are fixed evidence, not autonomous exploration. Legacy report structure
remains supported.

```powershell
python -m genesia verify path/to/runs/RUN_ID
```

Report run ID/status, source/sampling policy, compilation level and limitations, actual episode modes, Persona and response counts, mode-appropriate coverage/unseen states or cards, errors, evidence integrity, observed findings and unverified claims. `verify` checks hashes and path confinement, not the truth of natural-language claims. Describe outputs as synthetic Persona research **from supplied recordings**, not observed real-user behavior or autonomous product use.

## Reusable Case

```text
use_cases/<recorded-case>/
  task.yaml
  README.md
  runs/                  # private/ignored
```

Keep recordings, traces, Persona data, extracted frames and reports under ignored `local/` / `runs/` or an access-controlled external location. Public cases may provide path placeholders and schemas, but not private research assets.

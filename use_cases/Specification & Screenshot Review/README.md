# Specification & Screenshot Review

Case study: review Dayline using its specification and captured screens.

[Specification](materials/spec.md) | [Material provenance](materials/provenance.json) | [Reviewed results](sample/README.md)

This case starts from a written product specification and eleven still images,
not a live URL. Genesia builds an evidence-limited environment, lets each
synthetic Persona explore the supplied material, then runs a ten-question
interview and produces a research report.

The captured layout is **Design A**, corresponding to internal Design B in the
bundled [live comparison](../Live%20Prototype%20Comparison/README.md).
The UI snapshot matches that comparison's original source files.

## What interaction means here

The task uses `environment.mode: auto`, not a hand-authored graph:

1. The builder reads the spec and images together.
2. Explicit UI states become cards. Only source-supported transitions can form a graph.
3. If all states have connected transition evidence, Personas can choose among
   captured graph states. Otherwise the actual result may be Cards or Context.
4. The same Persona answers after its material-review session.

During preparation, check that `environment_readiness.json` preserves the spec's
shared context and material limitations in `background` as exact quotations,
not entire page descriptions. Static Cards combine a state's description and
screenshots; recording frames, when supplied in other cases, stay separate.
Citation checks validate provenance, not whether every important limitation was
identified, so review the actual build before interpreting participant feedback.

These are **choices among supplied observations**, not Playwright clicks against
a running product. Still images do not establish free text input, scrolling,
hidden content, acceptance, authorization or real message delivery. The spec
explicitly defines this boundary. Do not describe a failed or less detailed
build as successful live interaction.

The interview includes one explained single-choice question for perceived
usefulness. A structured question does not make the environment survey-only:
this case still builds and reviews an environment before asking questions.

## Verified example

The [published sample](sample/README.md) uses the current workflow in one
completed full 20-Persona study using `gpt-6.1-sol`, temperature 1, and V3 answer
rules: 11 states, 11 image-backed Cards, 26 declared transitions, 110 review
steps and 200/200 analyzed answers. Environment construction and all sessions
ran anew through the public SDK; no analysis recovery or participant pooling
was used. Two compiled-text fidelity warnings are disclosed in the sample scope.
The case template sets temperature 1; configure a model available at your own
endpoint (the sample used Sol). These are sample-specific results, not a guarantee
that every provider or new study will complete without validation corrections.

## Setup

From a repository checkout, use Python 3.11+ and your own image-capable,
JSON-output-compatible model. **No Node.js, browser or running prototype is
required to execute this case**, because the reviewed input images are included.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:OPENAI_BASE_URL = "https://YOUR_OPENAI_COMPATIBLE_ENDPOINT/v1"
$env:GENESIA_MODEL = "YOUR_VISION_MODEL_ID"
```

Review [task.yaml](task.yaml), the spec and the
[public fictional Persona notice](../../data/personas/global-digital-100/README.md).
The commands below explicitly authorize sending selected profiles, the spec and
screenshots to your configured API. Keys are read from environment variables,
never stored in a task. There is no model fallback.

## Preflight, prepare, run

```powershell
python "use_cases\Specification & Screenshot Review\run.py" `
  --personas data\personas\global-digital-100\personas.json --count 1 `
  --allow-model-data --preflight --network

python "use_cases\Specification & Screenshot Review\run.py" `
  --personas data\personas\global-digital-100\personas.json --count 1 `
  --allow-model-data --prepare
```

Preflight makes no inference calls. `--prepare` **does invoke models** to assess
materials, construct an environment and review readiness/fidelity. Inspect the
printed directory's `environment_readiness.json`, `environment_build.json`,
`study_review.json` and any `state_graph.json`.

Proceed only after reviewing actual states, cited transitions and limitations.
Do not edit generated artifacts to force a graph. If the material lacks support,
revise the input spec/images from real source evidence and use a new preparation.

```powershell
python "use_cases\Specification & Screenshot Review\run.py" `
  --personas data\personas\global-digital-100\personas.json --count 1 `
  --language en --allow-model-data
```

Start with one complete Persona session to verify your installation and model.
After inspecting its result, change `--count 1` to `--count 20` for the full cohort.
The one-person command still uses the full guide and analysis; it is not a shortened protocol.

`run` constructs and reviews its own environment again. Preparation is a preview,
not a cached graph; the final run's build is authoritative. The command prints
the actual episode modes, run status, metrics and report path.

Use `--language zh-CN` for Chinese report prose. Without an override, the task's
setting is retained. `--persona-id` can be repeated for an exact authorized
cohort; `--count` must match if supplied with IDs. Seeded public-pool sampling is
not the fixed cohort of the saved live comparison, and results are not directly
comparable across different input modalities or models.

## Outputs and limits

Private output defaults to this case's ignored `runs/` directory; use
`--output-dir` to choose another location.

```powershell
python -m genesia verify "use_cases\Specification & Screenshot Review\runs\RUN_ID"
python -m genesia report "use_cases\Specification & Screenshot Review\runs\RUN_ID" --open
```

Review `report.html` / `report.md`, `appendix.html`, the actual environment build,
and `analysis_provenance.json`. A complete run means required execution finished,
not that the synthetic feedback is representative or every interpretation is true.

The default protocol uses twenty Personas, at most eighteen review steps each,
ten questions in two batches, no follow-ups, complete encountered-image evidence,
and up to five concurrent Personas/model calls. Global ceilings are 1200 calls,
30 million reservation units and one hour; reservations are not billed tokens
or a cost promise. The count option does not resize those ceilings.
Model responses have at most two validation attempts within the same global
budget. Failed transport requests and partial studies are not silently replayed.
The analysis chunk target is 60,000 within a configured 128,000-token context
window. Match both settings to your provider's actual capacity; the runtime
uses conservative size estimates rather than a billing-token calculation.

Saved runs contain profiles and model evidence. Do not publish them without a
separate review. The included materials are synthetic and carry the source
prototype's [MIT license](materials/LICENSE.txt). Their
[provenance](materials/provenance.json) records capture hashes, scope and the
26 navigation relations checked against the local UI. The source PRD's planned
capabilities are not presented as implemented behavior.

## Report languages

Read the complete [English report translation](report-en.md) or the
[archival Chinese original](sample/report.md). The translation is not new analysis and
lives outside `sample/` to preserve its immutable publication files and hashes.

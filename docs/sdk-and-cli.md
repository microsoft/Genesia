# SDK and CLI Guide

The public Python SDK and CLI share one runtime. Start with the
[quick start](../README.md#quick-start) for installation and a first Live study,
or [research preparation](user-research-preparation.md) for study design.
The [architecture guide](architecture.md#capability-coverage-and-limits) describes
supported capabilities and their limits.

## Model Configuration

Choose a model available at your own OpenAI-compatible endpoint. Image-based
studies require a model that supports images. Store API keys in the environment,
never in task files:

```powershell
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:GENESIA_MODEL = "YOUR_MODEL_ID"
# Optional when creating tasks for another compatible service:
$env:OPENAI_BASE_URL = "https://api.example.com/v1"
```

An existing task records its endpoint, exact model and key-variable name:

```yaml
model:
  provider: openai_compatible
  base_url: https://api.openai.com/v1
  model: YOUR_MODEL_ID
  api_key_env: OPENAI_API_KEY
  token_limit_field: max_completion_tokens
```

Remote APIs require HTTPS. Set `token_limit_field: max_tokens` only for compatible
services that require that older field. Review the endpoint, model, permissions
and budget before running. A local proxy may still forward requests to a remote
provider; a localhost URL is not proof of offline processing.

## Direct SDK Use

```python
from genesia import load_task, preflight, run

task = load_task("examples/task.yaml")
checks = preflight(task, network=True)
if not checks["ok"]:
    raise ValueError(checks["issues"])
result = run(task)
print(result.status, result.output_dir)
```

Paths loaded from YAML resolve relative to the task file. Direct `TaskSpec`
construction uses caller-supplied paths. SDK integrations can inject a
`ModelGateway` and an `environment_factory` for offline tests or custom adapters.
The SDK is synchronous to its caller, with opt-in bounded concurrency across
Personas and sequential execution within each Persona.

## CLI Lifecycle

```powershell
genesia preflight examples\task.yaml
genesia preflight examples\task.yaml --network
genesia prepare examples\overview.yaml
genesia run examples\overview.yaml
genesia verify runs\RUN_ID
genesia schema task
genesia schema result
```

The example tasks explicitly select the
[fictional public Persona pool](../data/README.md), not representative or
verified human participants. Research execution invokes the configured model
and may incur charges.

`preflight` performs structural checks without inference; `--network` also checks
the configured model catalog. `run` performs model-catalog readiness checks when
using its own gateway; Live additionally needs an available disposable prototype.
`prepare` builds materials and reviews readiness in its own output directory,
without creating Persona sessions. `run` builds and reviews its own inputs rather
than automatically reusing preparation output. Live and profile-only Survey
bypass material compilation.

The [Persona generation guide](persona-generation.md) covers the separate
planning, confirmation, generation and approval lifecycle. Generating a cohort
does not start a study.

## Inputs and Methods

Documents, images, authorized Figma nodes, video and chronological frame manifests
can be compiled using `environment.mode: auto`. Numbered Cards and Canonical
Graphs remain advanced prepared inputs. Use the
[recording guide](../.github/skills/genesia-recorded-prototype/references/recording-inputs.md)
for trace timestamps, sampling limits and frame manifests.

For Figma, configure `kind: figma`, the file key in `path`, and the exact
`figma_nodes`. Enable `permissions.fetch_figma` only after authorization and set
`FIGMA_ACCESS_TOKEN` outside the task. This exports named nodes, not a complete
Figma interaction graph. PDF/DOCX extraction reads text; scanned pages need image
inputs. Figma API tests use mocks rather than proving access to a real account.

Research methods include `interview`, `survey`, `design_review` and
`task_outcome_review`. Question conditions use `ask_if`; skipped answers retain
null values. `batch_size` bounds questions per request, and `max_images` bounds
screenshot attachments while retaining structured episode evidence. Interview
`max_followups` defaults to zero. See the
[preparation guide](user-research-preparation.md) for complete configuration.

## Saved Artifacts and Trust

Keep the complete run directory together:

| Artifact | Purpose |
|---|---|
| `run_manifest.json` | Task/model configuration, lineage, hashes, budget and status |
| `episodes/`, `research/` | Participant experience, methods, batches and follow-ups |
| `artifacts/`, `evidence.json`, `events.jsonl` | Content-addressed evidence, ownership and lifecycle events |
| `research_result.json` | Typed responses, metrics, synthesis and report context |
| `report.html`, `report.md` | The same decision-first report in two formats |
| `appendix.html`, `appendix.md` | Original answers, traces and audits |
| `analysis_input.json`, `analysis_provenance.json` | Answer corpus and analysis coverage/lineage |
| `evidence_verification.json` | Integrity verification |
| `ui_cards.json`, `ui_cards/`, `state_graph.json`, `states.mmd` | Card-backed environment artifacts when applicable |
| `study_review.json` | Deterministic and optional model-assisted study findings |

Survey output retains `insight_report.md` as a compatibility alias.
Invalid method responses are retained but excluded from synthesis. The CLI
returns a nonzero exit code for partial or failed runs. Model attempts are
bounded and recorded; browser actions are not automatically retried.

Research questions are withheld during experience; the same logical Persona
answers afterward from its episode and prior answers. Schema validity, hash
integrity and execution success do not establish truth or human validity.
Participant task completion remains self-report. Priority factors are advisory,
not measured impact; segment statistics are descriptive, not population estimates.
Budget reservations and separately reported provider usage are not billing caps.

For rendering, reanalysis and report interpretation, use
[Analysis and reports](analysis-and-reports.md). Original answers and historical
reports are not silently translated or rewritten.

## Dependencies, Privacy and Development

Genesia does not vendor third-party source under `src/`. Installation resolves
the dependencies declared in [pyproject.toml](../pyproject.toml), each under its
own license. Data and media have separate publication notices in the
[data guide](../data/README.md); see the
[project license and notices](../README.md#license-and-notices).

There is no Microsoft usage-telemetry client in Genesia. User-configured model
and Figma requests are explicit integrations. Runs retain profiles, prompts,
screenshots and answers locally, so filesystem permissions and retention remain
the caller's responsibility. The ignored `local/` and `runs/` directories are
not access controls. See [Security](../SECURITY.md#project-specific-data-handling).

Offline development and optional release validation are documented in
[Contributing](../CONTRIBUTING.md#development-setup) and [CI configuration](ci.md).
Conda is optional; it provides the Python environment, while npm is needed only
for a separate JavaScript prototype. If a Conda installation cannot load native
DLLs in the build tool's temporary environment, use `python -m build --no-isolation`
only after installing the declared build dependencies.

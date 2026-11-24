# Genesia

![Genesia: synthetic Persona research, from product experience to insights](docs/figures/Genesia_banner.svg)

## From What to Build to What Comes Next

**Accelerate research and decisions across the product lifecycle.**

Genesia brings synthetic user perspectives into the questions that move a product forward:
which needs to explore, which ideas to pursue, how a design works, and what to improve next.
Its Python SDK and CLI connect **Persona Agents, product environments and research tasks**
so teams can explore, learn and revisit decisions as their product evolves.

> Synthetic research complements, rather than replaces, research with real people.

[Quick start](#quick-start) · [See an example](#see-an-example) · [Workflow guides](#choose-your-workflow)

## Why Genesia?

- **Accelerate More Than the Build.** AI agents speed up building, but discovering needs and validating ideas still take time. Genesia automates Persona sessions and analysis to accelerate research and decisions across the product lifecycle.

- **Personas That Experience Before They Answer.** Personas bring individual backgrounds, goals and preferences to their experience. The same Persona then answers from what it encountered, connecting feedback to its own journey.

- **Turn What You Have into a Research Environment.** Build review environments from concepts, documents, screens and recordings, or let Personas interact directly with an isolated live prototype.

- **Turn Individual Feedback into Actionable Insights.** Use interviews, surveys and reviews to surface shared needs, differing perspectives and design tradeoffs. Trace findings and recommendations back to original answers and supporting evidence.

- **Make Research Easier to Start and Reuse.** Compose studies from reusable Personas, environments and tasks. A public Persona pool, examples and your own model provider help individuals and small teams get started.

Read more: [The ideas behind Genesia](docs/why-genesia.md).

## How It Works

![Genesia architecture: Persona Agents, environments, research methods and evidence-linked outputs](docs/figures/Genesia_architecture.svg)

See [Architecture and evidence](docs/architecture.md) for implementation details and research boundaries.

## See an Example

The Dayline comparison shows one saved study: **20 synthetic Personas, 400 answers and 340 steps** across two prototype designs.

- [Read the English overview](use_cases/Live%20Prototype%20Comparison/sample/README.md).
- [Watch one complete A-to-B journey](use_cases/Live%20Prototype%20Comparison/sample/journeys/p01-paired.gif).
- Read the native report: [English translation](use_cases/Live%20Prototype%20Comparison/report-en.md) · [Chinese original](use_cases/Live%20Prototype%20Comparison/sample/report.md).
- [Run the complete A/B case locally](use_cases/Live%20Prototype%20Comparison/README.md#run-the-bundled-case): let Persona Agents operate the bundled prototype, answer the comparison questions, and generate a new insight report using your model.

These are simulated sessions, not human-participant recordings. Open downloaded HTML reports locally; GitHub does not execute them.
Study status and source details are documented in the [sample provenance](use_cases/Live%20Prototype%20Comparison/sample/README.md#study-provenance).
The runnable case includes the frozen prototype source. No separate Dayline checkout or hosted demo is required.

## Quick Start

This first run uses **one Persona and one interview question** against your own running prototype.
You need Python 3.11+, an image-capable OpenAI-compatible model, an API key, and an isolated HTTP(S) prototype with disposable data.
Windows with Chromium is the currently verified platform.

### 1. Install from this checkout

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[live]"
python -m playwright install chromium
```

### 2. Create your study

Replace the key, model and prototype URL. The example explicitly uses the bundled fictional Persona pool.
`init` creates a task file; it does not call a model or start the prototype.

```powershell
$env:OPENAI_API_KEY = "YOUR_API_KEY"
genesia init live quickstart `
  --personas data\personas\global-digital-100\personas.json `
  --model "YOUR_VISION_MODEL" `
  --url "http://127.0.0.1:5173/" `
  --goal "Explore the available workflow according to your own needs. Stop when you have enough context or no longer want to continue." `
  --size 1
```

For another compatible service, add `--base-url "https://YOUR_ENDPOINT/v1"` and, if needed, `--api-key-env YOUR_KEY_VARIABLE`.
The task stores the variable name, never the key value.

### 3. Review and authorize data sending

Open `quickstart\task.yaml`. Review the goal, generated question, model and budget.
Only after confirming that the profiles, prototype content and screenshots may be sent to your provider, enable the relevant permissions:

```yaml
permissions:
  send_persona: true
  send_materials: true
  send_screenshots: true
```

The bundled profiles are fictional examples, not verified users or a representative sample.
Use your own authorized data when the starter pool does not fit your research.

### 4. Check, run and inspect

Keep the prototype running. Network checks inspect the model catalog and URL without inference; the study itself makes model calls and may incur charges.

```powershell
genesia doctor quickstart\task.yaml --network
genesia run quickstart\task.yaml --open
```

Proceed only when the checks pass. Open the generated report for findings, limitations, original answers and traceable evidence.
If the run is partial or failed, inspect its errors rather than treating it as a successful study.

## Choose Your Workflow

Plan the study and select Personas first, then choose a research mode and review the results.
The survey, recording and live modes are alternatives, not required steps in a sequence.

| Your goal | Start here |
|---|---|
| Define the research goal, scope and questions | [Study preparation](docs/user-research-preparation.md) |
| Select an existing cohort or create one for your study | [Public Persona pool](data/personas/global-digital-100/README.md) · [Persona generation](docs/persona-generation.md) |
| Collect profile-grounded questionnaire responses | [Persona survey guide](.github/skills/genesia-persona-survey/SKILL.md) |
| Review a fixed recording or frame sequence | [Recorded prototype guide](.github/skills/genesia-recorded-prototype/SKILL.md) |
| Let Personas try a live prototype | [Live prototype guide](.github/skills/genesia-live-prototype/SKILL.md) |
| Build a research environment from a spec and screenshots | [Material-based Dayline example](use_cases/Specification%20%26%20Screenshot%20Review/README.md) |
| Explore needs and preferences before a product exists | [Profile-grounded delegation survey](use_cases/Profile-Grounded%20Persona%20Survey/README.md) |
| Compare two or more live designs | [Comparison example](use_cases/Live%20Prototype%20Comparison/README.md) |
| Inspect results or reanalyze saved answers | [Analysis and reports](docs/analysis-and-reports.md) |

The SDK and CLI share one runtime. Copilot Skills are optional guided workflows, not a requirement for using Genesia.
Recordings support review of supplied evidence; they do not let a Persona operate the recorded application.
Reports use English fixed interface text; the generated research prose can be English or Chinese.

## Limits and Data Safety

- **Alpha software, not a hosted service.** Interfaces and artifact formats may change.
- **Synthetic, not representative.** Use results to form and inspect hypotheses, not to claim human validation or causal A/B effects.
- **Research support, not market proof.** Synthetic feedback does not establish actual demand, willingness to pay, adoption or retention.
- **Explicit data sending.** Your configured services may receive authorized profiles, materials and screenshots. Saved runs also contain research data.
- **Isolated prototypes only.** Browser actions can mutate server state; Genesia is not a security sandbox for production accounts.
- **Execution limits are not billing guarantees.** Model fees and provider behavior remain outside Genesia's control.

See [Security and data handling](SECURITY.md) and the [Persona data notice](data/README.md).
Genesia has no Microsoft usage-telemetry client; configured model and Figma requests are separate, explicit integrations.

## Development and Architecture

For offline coding, install `.[dev]` and run `python -m pytest -q`; no model key or browser is required for the default SDK suite.
See [Contributing](CONTRIBUTING.md) for optional integration tests, publication checks and release validation.
See the [SDK and CLI guide](docs/sdk-and-cli.md) for direct API use, model configuration and saved artifacts.

Use your own OpenAI-compatible model endpoint and execution budgets. The package runs locally;
model requests go to your configured provider, and saved research outputs stay in your chosen directory.
Genesia does not ship a hosted Persona Hub or multi-tenant service.
Read the [architecture guide](docs/architecture.md) for implementation details and extension boundaries.

## License and Notices

Genesia uses the [MIT License](LICENSE.txt). Third-party dependencies retain their own licenses; see [dependency declarations](pyproject.toml).
For help, use the [support guide](SUPPORT.md).

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions must not cause confusion or imply Microsoft sponsorship.
Third-party trademarks and logos remain subject to their owners' policies.

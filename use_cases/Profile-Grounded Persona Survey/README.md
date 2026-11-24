# Profile-Grounded Persona Survey

Case study: AI task delegation and human confirmation boundaries.

[Questionnaire and settings](task.yaml) | [Reviewed survey results](sample/README.md)

A survey-only example for exploring **which tasks a hypothetical assistant
might fit and where people would want confirmation** before a product exists.
It uses authorized synthetic Persona profiles, not a live site, screenshots,
recordings or fabricated product experience.

## Research design

The neutral concept promises no capability, reliability or benefit. Twelve
question definitions cover task relevance, willingness, approval boundaries,
importance, uncertainty handling, information needs, concerns, trade-offs and
next validation. Choice explanations, multi-select, matrices and open text
are included. Two exact conditional questions ask either the first possible
task or the reason for refusing; uncertainty can skip both.

Questions about priorities and delegation are hypothetical, not past usage.
Refusal, non-applicability, uncertainty and profile-insufficient answers are
valid. The approval matrix contains categories: do not average its choices or
treat them as a numeric Likert scale. The importance matrix has an ordered
scale plus an explicit non-applicable/uncertain option.

There are no automatic age, gender or occupation comparisons. The example
explores task needs and preferences without manufacturing demographic causes.

## Verified example and limitations

The [published sample](sample/README.md) uses `openai/gpt-6.1-terra` via OpenRouter
at temperature 1 with V3 answer rules in one completed public-SDK run with
20 fixed synthetic Personas:
240 question slots, 220 profile-grounded answers
and 20 conditional skips, with all 220 eligible answers analyzed. No product
environment or analysis recovery was used. The case template sets temperature 1;
the endpoint and model ID remain caller-configurable.

All twenty expressed conditional willingness and similar approval boundaries;
one would not delegate deletion. Eleven selected all six approval-information fields. These limits are
retained and discussed, not “fixed” by inventing dissent. The sample demonstrates
the workflow, not market demand, adoption prediction, field-level prioritization
or a model's general role-playing quality.

## Setup

From the repository root, use Python 3.11+ and your own JSON-output-compatible
text model. No browser, Node.js, media extra or image-capable model is needed.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:OPENAI_BASE_URL = "https://YOUR_OPENAI_COMPATIBLE_ENDPOINT/v1"
$env:GENESIA_MODEL = "YOUR_TEXT_MODEL_ID"
```

Review the questionnaire and the
[public fictional Persona pool](../../data/personas/global-digital-100/README.md).
`--allow-model-data` explicitly permits sending the chosen profiles and
questionnaire to your configured provider; screenshots remain disabled.
Keys stay in environment variables.

To use the same provider and model as the sample, set the following instead of
the endpoint/model placeholders above, and provide your own OpenRouter key in
`OPENAI_API_KEY`:

```powershell
$env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
$env:GENESIA_MODEL = "openai/gpt-6.1-terra"
```

The task and runner remain configurable; they never silently select a provider.

## Preflight and run

```powershell
python "use_cases\Profile-Grounded Persona Survey\run.py" `
  --personas data\personas\global-digital-100\personas.json --count 1 `
  --allow-model-data --preflight --network

python "use_cases\Profile-Grounded Persona Survey\run.py" `
  --personas data\personas\global-digital-100\personas.json --count 1 `
  --language en --allow-model-data
```

Preflight does not infer. A full run includes study readiness review,
profile-grounded responses, deterministic statistics and analysis. There is no
environment to compile, so `prepare` is not required.

After checking a one-Persona full run, change `--count 1` to `--count 20`.
The default size is 20. Repeat `--persona-id` for an exact cohort; a count,
when also supplied, must agree. Sampling the public pool by seed does not
reproduce an earlier study's fixed cohort.

Use `--language zh-CN` for Chinese synthesis. `--output-dir` selects a private
location; otherwise outputs go to this case's ignored `runs/`.

```powershell
python -m genesia verify "use_cases\Profile-Grounded Persona Survey\runs\RUN_ID"
python -m genesia report "use_cases\Profile-Grounded Persona Survey\runs\RUN_ID" --open
```

## Outputs and interpretation

Open the native report and appendix, descriptive statistics and analysis
provenance. `insight_report.md` is an alias of the same report, not another
analysis. A completed response is one Persona's whole method, not one question.

With 20 Personas and 12 question definitions there are 240 question slots,
not necessarily 240 answered questions. Conditional skips and unsupported
answers remain explicit; analysis covers eligible answers only. Percentages
use answered denominators per question, and multi-select totals may exceed
100%. Do not silently include skipped respondents in a branch's denominator.

Survey mode creates no product observations, steps, Cards or Graph. Answers
use profile grounding or `not_observed`, with `skipped` for inapplicable
conditions; they cannot establish actual usability, defects, adoption,
market prevalence or statistical significance.

Question batches hold up to five questions per Persona, with conditional
dependencies causing earlier flushes. Persona and model concurrency are each
limited to five. Total limits are 500 calls, 12 million reservation units and
1800 seconds; reservations are not billed tokens or money. Count changes do
not automatically change these limits. Validation attempts share the same
budget, and a failed survey is not silently restarted or resumed.

## Report languages

Read the complete [English report translation](report-en.md) or the
[archival Chinese original](sample/report.md). The translation is not new analysis and
lives outside `sample/` to preserve its immutable publication files and hashes.

Review raw profile-bearing runs before sharing. Publish only a separately
reviewed sample, not the entire output directory.

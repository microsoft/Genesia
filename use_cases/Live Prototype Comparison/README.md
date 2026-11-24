# Live Prototype Comparison

Case study: a Dayline A/B comparison of Agent-work supervision layouts.

[Sample results](sample/README.md) | [Journey GIFs](sample/index.html)

Let synthetic Persona Agents use two layouts of Dayline, a simulated workspace
for supervising Agent work. Each Persona explores A then B in isolated browser
contexts, answers the same twenty-question interview, and contributes to an
evidence-linked research report. This case uses Genesia's public SDK.

## See the results

The included sample has **20 Personas, 400 answers and 340 recorded steps**.
The main tradeoff is focused reading versus a board-level overview:
14 Personas preferred A, 4 preferred B, and 2 had no meaningful preference.
These are descriptive synthetic results, not a causal A/B effect or population estimate.

- [Sample overview](sample/README.md).
- Native report: [English translation](report-en.md) / [archival Chinese original](sample/report.md) / [archival HTML report](sample/report.html).
- [All twenty journey GIFs](sample/index.html) / [one complete journey](sample/journeys/p01-paired.gif).

The current native report uses a new `gpt-6.1-sol`, temperature-1 interview over
the same saved journeys. The complete English report translation is linked above
and lives beside this guide; it is not new findings or reanalysis. The Chinese
native report, preference data and all twenty journey GIFs remain unchanged apart
from removing obsolete historical-report references. Updated publication hashes
are recorded in the manifest. New runs default to English.
Study status, source hashes and publication scope are in the [sample provenance](sample/README.md#study-provenance).

## Run the bundled case

Use a **repository checkout**, Python 3.11+, Node.js 22 LTS, and an image-capable
OpenAI-compatible model with JSON-output support. The Python wheel and source
distribution do not include the frontend. Windows with Chromium is the
locally verified setup; CI also checks bundled-prototype readiness on Linux.

All commands below run in PowerShell from the repository root.

### 1. Install and build

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[live]"
python -m playwright install chromium
npm ci --prefix "use_cases\Live Prototype Comparison\prototype"
npm run build --prefix "use_cases\Live Prototype Comparison\prototype"
```

The MIT-licensed prototype is included and npm downloads use the public registry.
No separate Dayline checkout or model key is needed to build it.
Rebuild after changing prototype source; research runs serve the built files.

Prototype documentation: [English translation](prototype/README-en.md) /
[archival Chinese original](prototype/README.md). The hash-bound original is preserved.

### 2. Configure your model and review the study

```powershell
$env:OPENAI_API_KEY = "YOUR_API_KEY"
$env:OPENAI_BASE_URL = "https://YOUR_OPENAI_COMPATIBLE_ENDPOINT/v1"
$env:GENESIA_MODEL = "YOUR_VISION_MODEL_ID"
```

Replace the API base URL and model/deployment ID with your provider's values.
For OpenAI, the base URL is `https://api.openai.com/v1`. Genesia uses `/models`
and `/chat/completions` relative to that base; native provider APIs are not
necessarily compatible. No fallback model is selected.

Review [task.yaml](task.yaml) and the [public Persona notice](../../data/personas/global-digital-100/README.md).
The following commands explicitly select the fictional pool and use
`--allow-model-data` to authorize sending profiles, prototype content and screenshots.
Without that flag, the bundled task refuses the study. Keys stay in environment
variables, not saved tasks; `--api-key-env` selects another key variable.

### 3. Preflight without inference

```powershell
python "use_cases\Live Prototype Comparison\run.py" `
  --local-prototype --personas data\personas\global-digital-100\personas.json `
  --count 1 --language en --allow-model-data --preflight --network
```

Preflight checks the cohort, permissions and budgets, starts the built prototype
on an OS-assigned loopback port, and verifies both design markers in disposable
Chromium contexts. `--network` also checks the provider's model catalog, without
inference. Omit it for an offline check. The temporary server closes on exit.

### 4. Run experience, interview and analysis

```powershell
python "use_cases\Live Prototype Comparison\run.py" `
  --local-prototype --personas data\personas\global-digital-100\personas.json `
  --count 1 --language en --allow-model-data
```

Use `--language zh-CN` for Chinese report prose. Without this option, the task's
`insight.language` is retained; the bundled task uses `en`. This option does not
translate original participant answers or change the research questions.

The runner starts and closes its own local server, including on failure or
interruption. No separate `npm run dev` terminal is needed. Actual research uses
new Persona browser sessions, not the readiness-check browsers.

One Persona still runs the complete twenty-question study. It is an initial
end-to-end check, not a shortened or free study. To select twenty Personas,
change `--count 1` to `--count 20`. The count does not resize global budgets,
step limits or concurrency ceilings. Review the [protocol](#protocol-and-limits)
before running. Model fees depend on your provider and actual usage.

## Inspect your output

The command prints the exact run ID, status and report path. By default, output
is saved under the ignored `use_cases\Live Prototype Comparison\runs`;
`--output-dir` can select another private location.

- `report.html` / `report.md`: summary, findings, next actions and limitations.
- `appendix.html` / `appendix.md`: original answers and recorded journeys.
- `research_result.json`, evidence and screenshots: inspectable structured records.

```powershell
python -m genesia verify "use_cases\Live Prototype Comparison\runs\RUN_ID"
python -m genesia report "use_cases\Live Prototype Comparison\runs\RUN_ID" --open
```

Keep the whole run directory together for private review. It can contain full
Persona profiles, model requests and screenshots; do not publish it unreviewed.
The runner does not generate public GIF galleries.
Those are curated additions to the included sample.

If a run is partial or failed, inspect the reported errors. Where only analysis
failed and participant data are valid, analyze the saved answers into a new run:

```powershell
python -m genesia analyze "use_cases\Live Prototype Comparison\runs\RUN_ID" `
  --language en --timeout-seconds 300 --open
```

`analyze` invokes the configured model but does not repeat product experience.
`report` only renders saved results. Neither operation overwrites source status.
See [analysis and reports](../../docs/analysis-and-reports.md) for details.

## Customize the study

Use `--personas` for your authorized JSON/TSV, `--count` for seeded sampling,
or repeat `--persona-id` for an exact cohort. Explicit IDs must be unique;
if combined with `--count`, the count must match. A generated managed cohort
must pass its approval and validation checks, including any full-cohort rule.

Use `--task` with a separate YAML file to change questions, limits or study
objectives. A new sample from the public pool is not the historical fixed cohort,
and new model outputs need not reproduce the saved preference counts.

To use your own isolated prototype, omit `--local-prototype` and provide both
`--url-a` and `--url-b` on the same origin. Adapt the product description,
questions and prototype boundaries together with the URLs.

The bundled source retains its original routes: **public A uses `design=b`**,
**public B uses `design=d`**, both with `research=1`. This hides the product's
variant switch; Genesia's `advance` controls the handoff. The
[prototype contract](prototype/PROTOTYPE_CONTRACT.md) documents the upstream
variant names. Its license, original source and fixtures are preserved; npm
manifest changes make dependency downloads and the state-test command portable.

## Prototype snapshot and maintenance

The saved reports and GIFs describe the original studied snapshot, not a rerun.
Its source hashes in [prototype provenance](sample/prototype.json) are unchanged.
The original entrypoint is retained byte-for-byte in
[main.tsx.snapshot](prototype/frozen/main.tsx.snapshot); all other studied UI source
files remain unchanged.

The runnable entrypoint additionally loads [contrast-fix.css](prototype/src/contrast-fix.css).
It changes only three supporting-text colors on selected Design B board cards
(source Design D), raising their settled contrast from 4.486 to 4.619 against the
existing background. Layout, fixtures and decision semantics do not change.
This is declared maintenance, not evidence that the historical study used the
corrected colors; reports, screenshots and preference counts are not regenerated.

To rebuild the original studied UI without this maintenance stylesheet:

```powershell
Copy-Item "use_cases\Live Prototype Comparison\prototype\frozen\main.tsx.snapshot" `
  "use_cases\Live Prototype Comparison\prototype\src\main.tsx"
npm run build --prefix "use_cases\Live Prototype Comparison\prototype"
```

This deliberately changes the local runnable entrypoint; normal publication
checks expect the maintained entrypoint. The browser CI configuration uses a
production preview and reduced motion to measure settled styles rather than
transient colors during CSS transitions.

## Protocol and limits

- Fixed A-to-B order with isolated browser state; the same Persona retains its own experience.
- Natural exploration and stopping, with no minimum action count or mandatory feature tour.
- Up to fifty steps and complete screenshot evidence, with a fifty-one-image bound.
- Twenty questions in 8+8+4 batches, no follow-ups.
- Up to five concurrent Personas and five model calls.
- Global ceilings: 2000 calls, 60 million reservation units and one hour.
  Reservation units are not actual tokens or money. Stage deadlines are measured
  from run start, not renewed for queued participants.
- All tasks, accounts, Agent work and external actions are simulated.
  Fixed order and different self-chosen paths do not establish causal A/B effects.

## Troubleshooting

- **Prototype not built:** run the npm install/build commands from step 1.
- **Chromium missing:** install the live extra and run `python -m playwright install chromium`.
- **HTTP 401/403:** check endpoint/key pairing and resource/model access.
- **HTTP 404:** check the API base URL and `/models` support.
- **HTTP 429:** check provider quota or rate limits before retrying.
- **Model absent from catalog:** use the exact catalog model/deployment ID.

## Maintaining the included publication

[export_sample.py](export_sample.py) rebuilds the **historical sample only**.
It requires the original private study, separate analysis, paired-media provenance
and snapshot records. It is not a general exporter for new A/B runs and is not
a step in the setup above. `--help` documents its maintainer inputs.
No private source inputs are required to run the bundled study or inspect your
own native report, appendix and screenshots.

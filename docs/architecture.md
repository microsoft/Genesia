# Architecture and Evidence Provenance

## Module Responsibilities

![Current Genesia architecture](figures/Genesia_architecture.svg)

The core **Task Validation** stage checks task structure, permissions, materials,
the Cohort and research mappings. The public **Pre-flight** feature runs this
validation separately through `preflight(task)` or `genesia preflight`; with
`--network`, it also checks the model catalog. `prepare` and `run` reuse Task
Validation, but do not internally “execute the Pre-flight feature”: `prepare`
then builds the environment and reviews readiness/fidelity, while `run` proceeds
to Persona experience and research.

`api.py` provides deterministic lifecycle orchestration; `agents.py` handles
Persona decisions and post-experience research answers; `environments.py`
handles bounded material reading, model-assisted environment-graph construction
and deterministic recorded-state transitions; `live.py` manages Playwright
resources and browser restrictions; `runtime.py` handles OpenAI-compatible calls,
budget reservations, immutable artifact contents and mutable run checkpoints.
`persona_generation/` (submodules: plan, cohort, candidates, prompts, budget,
concurrency, checkpoint, pipeline) and `cli_personas.py` provide independent,
pre-study Cohort Plans, confirmation, generation and validation.
`insight_report.py` and `insight_support.py` handle per-question analysis,
evidence-bound cross-question composition and provenance; `schemas.py` defines
the public versioned contracts.

Code enforces the research gate. Environment construction and action prompts
do not receive research questions. The research stage continues with the same
Agent object and session ID rather than resampling the Persona. The system does
not rely on the model provider to retain conversational memory: each request
carries the identity and evidence context it needs.

Input type, interaction mode and research method are independent. Ordinary users
can supply raw documents, images/Figma, video/recordings, a Live URL or a
questionnaire. With `mode: auto`, `EnvironmentBuilderAgent` normalizes sources
and sends text, images and provenance to the model. A typed
`EnvironmentAssessment` identifies UI states, candidate transitions, citations
and limitations. A document may contain only a concept or describe multiple
detailed UI states; images and videos do not necessarily contain UI either.
Mixed materials are assessed jointly. Numbered Cards and Canonical Graphs are
prepared/debug inputs, not prerequisites for ordinary users. Importing a
Canonical Graph explicitly bypasses content assessment.

Code checks state IDs, transition endpoints, source references and verbatim
quotation matches. Model-proposed transitions require textual evidence.
Runtime-generated `recorded_order` edges can connect only adjacent identified
frames with increasing timestamps in the same recording. File order and
different recordings do not establish transitions. Citations are necessary,
but do not prove correct semantic understanding. A Graph must have an entry
that can reach every state; otherwise the system retains reviewable Cards and
reports the limitation. Model or provider failures remain failures rather than
being disguised as insufficient materials followed by a silent downgrade.

`EnvironmentBuildResult` records Context, Cards or a Graph, together with the
assessment and issues. Materials not bound to UI remain supplemental Context,
even alongside Cards or a Graph, and are labeled as background in the first
observation. Card-backed Graph nodes can bind one or more Cards, with each Card
bound exactly once. Declarative branches use captured-graph choices; a single
recorded path uses walkthrough. The Episode records the actual execution mode.
Readiness and fidelity reviews receive all three artifact levels and original
source references. Standard research reports show compilation summaries and
limitations; detailed citations remain in `environment_readiness.json` and
`environment_build.json`.

When one Spec contains UI descriptions and general background, the assessment
separately cites continuous verbatim passages for shared context, assumptions
and material limitations through `background`. Code checks sources and exact
matches, then retains those passages as Context. A whole document already cited
by a state or transition is not automatically injected as global background;
page details and navigation should not enter `background`. Background extraction
is still a model judgment: exact quotations do not prove correct semantic
classification. During preparation, manually check for missing important
limitations or accidentally included page content. Separate materials not bound
to states or transitions remain available without being sent again as extracted
passages.

A static UI state's textual evidence and screenshots appear together in one
Card. Reading order follows the earliest associated image, or text order when
there is no image. Recorded images retain separate Cards, original timestamps,
traces and chronology, including returns to the same state. Shared Spec evidence
binds to the corresponding recording Cards rather than creating extra recorded
steps without images. Graph states and edges still follow assessment and source
evidence; merging static Cards does not introduce new transitions.

Legacy explicit modes preserve caller-selected behavior, including editor-defined
Card order in `walkthrough`. Auto does not infer product navigation from
numbering. Live and Survey bypass the compiler entirely. Live runs directly
through Playwright and is not retrospectively summarized into Cards or a Graph.
Skills remain thin orchestration over the public SDK/CLI, not a second Builder
or Persona implementation.

`analysis.py` computes descriptive question/group counts and ranks recommendations
using model-estimated explicit factors and deterministic counts of cited
participants. `agents.py` supports bounded interview follow-ups, batch checkpoints
and conditional survey skips. The same participant object and session continue
throughout. Failed methods retain completed batches but are excluded as a whole
from synthesis.

When a post-experience answer explicitly supplies `basis=automation`, evidence
binding preserves that label and rebinds it to the candidate scope actually
experienced by that Persona. The answer remains auditable but does not enter
product themes or descriptive answer distributions. Reaching a step or
exploration-budget limit does not make every answer automation-based; ordinary
product feedback can remain eligible. This rule affects research-stage
classification, not Live browser execution.

Evidence IDs are valid only within one run. References owned by different
participants may share a content hash, but ownership remains separate. Findings
reference validated answer artifacts; answers in turn reference sources or
observations that the owning Persona actually encountered. `verify` checks
artifact hashes and path restrictions, not the truth of natural-language
conclusions. Actual execution records are presented separately for comparison
with Persona self-reports.

## Input-Workflow Skill Boundaries

The [genesia-persona-generation Skill](../.github/skills/genesia-persona-generation/SKILL.md)
handles the separate Cohort Plan, user confirmation, generation and validation
workflow, producing managed `personas.json` for later tasks. It does not
automatically start a study or present generation seeds/coverage as population
representativeness.

The workspace's
[genesia-live-prototype Skill](../.github/skills/genesia-live-prototype/SKILL.md)
is a lightweight user workflow for `environment.mode: live` over the public CLI
and SDK. It creates Live tasks, runs preflight/run/verify and interprets autonomous
Persona action paths. It bypasses compilation and does not create Cards/Graph
after a Live run.

The [genesia-recorded-prototype Skill](../.github/skills/genesia-recorded-prototype/SKILL.md)
defaults to `environment.mode: auto` for raw video or chronological frame
manifests and can jointly assess supplemental materials. It runs
preflight/prepare/run/verify. Before Persona sessions, it reviews sampled
evidence, assessments/citations, Context/Cards/Graph artifacts, supplemental
background and trace alignment. Actual Episodes use Context/Card review,
single-recording walkthrough or captured-graph choices according to validated
artifacts. Explicit `walkthrough` remains for caller-selected legacy/prepared
order, not automatically verified product navigation. Preparation has its own
directory; `run` rebuilds and reviews. The Skill does not describe
recorded-material research as autonomous product use.

The [genesia-persona-survey Skill](../.github/skills/genesia-persona-survey/SKILL.md)
targets `environment.mode: survey`. It creates no environment adapter,
observations or action history. The same Persona object enters the research
gate directly; answers must be profile-grounded or `not_observed`. Deterministic
statistics and synthesis then produce the insight report.

The [genesia-raw-answer-report Skill](../.github/skills/genesia-raw-answer-report/SKILL.md)
and [genesia-raw-answer-research-report Skill](../.github/skills/genesia-raw-answer-research-report/SKILL.md)
read only original answers and Episodes from one saved run. The former defaults
to a focused decision report; the latter produces a full research readout.
They use the current Agent's independent analysis, do not call the run's
configured provider, operate the prototype or rerun Personas, and do not
misrepresent their output as canonical synthesis.

In Live, recorded and Survey modes, every Persona intent, action and research
call uses the packaged `src/genesia/resources/persona_role.md` policy. It covers
Persona role-taking, a ten-dimensional profile framework and continuous role
consistency. Survey methods also receive `src/genesia/resources/survey_response.md`,
which defines completeness and question-type rules. Genesia replaces the legacy
response JSON with Pydantic answer schemas and mode-specific grounding rules.
Applicable policies are written into the model-request payload, so each run
records the prompt layers actually used. Moderator and synthesis calls do not
play participants and therefore do not receive the Persona role policy.

V3 expression rules apply only to `persona_research` answer calls. Shared role
and Survey resources remain unchanged. Initial intent, UI Card/Graph or Live
actions, stopping and phase transitions do not receive the new expression
rules. Answering uses a local copy of role wording with packaged
`persona_voice.md` appended. In the answer-time copy, Survey text-question
rules remove uniform sentence counts while preserving completeness,
question-type and consistency rules. Survey-only uses profiles and hypothetical
context; post-experience Survey remains based on the experience actually
supplied. Interview retains the existing experience instructions and interview
examples.

Answer requests expand existing base data into readable blocks and place Survey
rules before data. This formatting does not remove the complete profile, task
goal, personal intent, questions or the participant's earlier answers. Existing
image/text timelines, material adjacency, output structure, evidence binding,
conditional skips and validation are unchanged. Saved `model_request` is the
request before serialization; inspect the content actually received by the
model when diagnosing formatting. This migration changes neither model nor
sampling defaults and does not automatically rewrite historical answers or
published samples.

```text
Copilot user -> genesia-live-prototype     -> public CLI / SDK -> PersonaAgent <-> LiveEnvironment
             -> genesia-live-comparison    -> public CLI / SDK -> PersonaAgent <-> staged LiveEnvironment
             -> genesia-recorded-prototype -> public CLI / SDK -> source normalization
                                                               -> EnvironmentBuilderAgent
                                                               -> Context / Cards / Graph
                                                               -> evidence-supported review environment
                                                               -> Persona research
             -> genesia-persona-survey     -> public CLI / SDK -> PersonaAgent survey research gate
                                                               -> validated answers
                                                               -> statistics and synthesis
             -> genesia-persona-generation -> public CLI / SDK -> Cohort Plan
                                                               -> confirmed, validated personas.json
             -> genesia-raw-answer-*       -> saved original answers / Episodes
                                              -> private, non-canonical independent report
```

These Skills do not call model providers directly or implement prompt, browser
or media internals, state computation or evidence validation. Input type,
environment mode and research method remain independent: a post-experience
survey method is not the profile-only Survey workflow. Other raw materials use
`auto` through the public SDK/CLI; numbered Cards and Canonical Graphs remain
advanced prepared/debug inputs. This allows the conversational orchestration
layer to be replaced while behavioral and trust-critical rules remain in typed,
testable Python. Direct SDK users and Skill users share task schemas, budgets,
execution semantics and output contracts.

## Extension and Service Boundaries

`ModelGateway.complete` is replaceable through injection.
`run(..., environment_factory=...)` supports additional deterministic adapters.
Sources and methods currently use closed, validated types; new types require
schema and implementation changes, not implicit fallback. `load_task` and `run`
are independent, allowing applications to construct typed tasks without YAML.

A future HTTP Job layer should resolve uploaded artifacts into a confined
workspace, validate permissions/budgets, invoke the same application core and
expose status/results. Authentication, durable jobs, cancellation, multi-tenancy
and remote object storage are not implemented. Browser-session replay or resume
is not claimed either.

## Capability Coverage and Limits

This is a capability map, not a sequence of mandatory pipelines. The
[SDK and CLI guide](sdk-and-cli.md) provides the configuration and entry points.

| Capability | Implemented behavior | Boundary |
|---|---|---|
| Study setup | Typed cohorts, objectives, questions, criteria and sample requirements | Structural validation does not certify representativeness |
| Persona generation | Separate plans, confirmation, slot allocation, candidate review and exact-cohort approval | Archetype mode only; no grounded microdata or existing-pool matching |
| Auto environment | Joint assessment of documents, images and recordings into Context, Cards or a connected Graph | Citation/structure checks do not prove semantic interpretation |
| Spec and Figma | UTF-8/PDF/DOCX text, images and authorized named-node Figma exports | Scans need images; no universal Office/Figma interaction importer |
| Recording | Bounded video/frame sampling and relative input-trace alignment | Sampling may miss transient states; temporal order is not click causality |
| Live prototype | Isolated Playwright browser contexts with screenshot/DOM actions | Requires an available disposable app; shared backend state is not isolated |
| Scenario and Card walkthrough | Supplied context and caller-selected or recorded observation sequences | Not autonomous operation of the recorded product; early stops remain possible |
| Persona Agent | Continuous identity, intent, execution history and a research phase gate | Simulated sessions are not human-participant observations |
| Survey | Typed text/choice/Likert questions, conditional skips and bounded batches | No vendor-specific survey importer or inferential statistics |
| Profile-only Survey | Answers grounded in authorized profiles without fake product actions | No product-experience evidence, correlation or clustering claims |
| Interview and reviews | Episode-grounded guides, optional bounded neutral follow-ups, design/outcome review | Model-assisted judgments are not independent validity oracles |
| Preflight and preparation | Structural checks, optional network readiness, material build and optional study/fidelity reviews | Network readiness is not inference; preparation is not a run cache |
| Execution | Bounded Persona/model-call concurrency and shared budget reservations | No distributed workers or persistent browser-session resume |
| Analysis and delivery | Per-question findings, evidence-bound composition, descriptive counts and report/schema exports | Processing coverage and advisory priorities do not establish causal A/B effects |
| Saved-run analysis | Deterministic report rendering and separate lineage-linked analysis | No participant rerun or silent modification of source answers |

### Separation of Guarantees

- **Deterministic checks:** schemas, source paths and sizes, Card bindings,
  citation/quote matching, same-recording adjacency, cohort selection, answer
  options, evidence ownership and hashes.
- **Model-assisted judgments:** material readiness, UI interpretation, state
  grouping, study/fidelity concerns, participant feedback and recommendations.
  These may be wrong despite valid schemas.
- **Human review:** material completeness, meaningful boundaries, privacy rights,
  study validity, production safety and the decision to act on findings.

The fidelity reviewer may flag over-merging but does not silently rewrite
evidence. Study errors block by default; `study.block_on_errors: false` is an
explicit caller override requiring review, not proof that the findings are safe
to ignore.

Hosted jobs/authentication, distributed execution, remote Persona Hub, automated
population calibration, audio transcription/OCR, causal A/B experiments and
inferential statistics are outside this release. The repository is
[MIT-licensed](../LICENSE.txt). The [CI guide](ci.md) distinguishes the Linux
prototype job from the Windows Python SDK matrix; configured jobs do not alone
prove that a specific run passed or that the SDK supports every platform.

## Core Conclusions

A Persona is a continuous Agent. Environment construction is budgeted, validated
model inference; environment execution, orchestration, permissions and evidence
checks are deterministic code. Different sources, interactions and methods share
contracts without disguising inapplicable combinations as supported. Behavioral
rules, evidence validation and execution boundaries belong to the same SDK.
A future website can reuse the core through the same application entry point;
the service layer itself has not been built.

Auto uses `EnvironmentBuilderAgent` to jointly assess text, images and recordings,
produce states, transitions and citations, then lets code validate and construct
Context, Cards or a Graph. When UI or connected transitions are missing,
lower-level reviewable artifacts remain available. Background in mixed materials
is not discarded. Verbatim matching and recorded chronology do not establish
semantic or causal validity. Preparation reviews cover all three levels and
reports show judgments/limitations. Live/Survey do not compile, and Live has no
post-experience graph induction.

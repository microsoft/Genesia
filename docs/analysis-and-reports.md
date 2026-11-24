# Analysis and Reports

A full study uses one report: Summary, Next actions, Findings, brief Limitations,
then Appendix / Evidence. Open `report.html` locally without
a server or CDN. `report.md` contains the same content, not a second edition.
`research_result.json` stores the result and report context. `appendix.html` /
`appendix.md` expose original answers, traces, segments and audits. Keep the entire
run directory together when sharing privately: screenshots live in `artifacts/`.

Fixed report titles, navigation, labels and system notices are always English.
`insight.language` (`en` or `zh-CN`) controls model-generated research prose, not
the fixed interface. Original participant answers and quotations are not translated.
HTML language metadata continues to reflect the research-prose language. Previously
published sample reports are historical artifacts and are not rewritten.
If quotation text does not satisfy the requested research-prose language, omit
that quotation rather than translate it; the original answer remains available.

```powershell
genesia init live my-study
genesia doctor my-study/task.yaml
genesia doctor my-study/task.yaml --network
genesia run my-study/task.yaml --open
genesia verify my-study/runs/RUN_ID
genesia report my-study/runs/RUN_ID --open
genesia analyze my-study/runs/RUN_ID --language en --open
genesia analyze my-study/runs/RUN_ID --language zh-CN --focus "Version choice" --open
```

`init` supports live, recorded and survey. It prompts for missing model, goal,
authorized Persona file and URL/recording. It never invents Personas or overwrites
a task. Review its placeholder question and enable explicit permissions before
running. `init` uses a user-configured OpenAI-compatible API; set `--model`, `--base-url` (or `OPENAI_BASE_URL`) and `--api-key-env` as appropriate. `doctor --network` checks the model catalog and live URL without inference.
Newly generated tasks keep data-sending permissions disabled until authorized.
For recordings, run `prepare` and inspect the compiled material before `run`;
preparation is not a compilation cache automatically reused by `run`.

For mixed specifications and UI images, review the assessment's `background`
citations as well as states and transitions. Global context and limitations can
come from the same document as UI descriptions. Only their exact quoted passages
are attached as background when that document is already referenced by a state
or transition, not the entire specification or unseen page descriptions.
Source/quote checks do not certify that the model classified every passage correctly.
Unbound standalone materials remain available as context without duplicating
their extracted background quotes. Static states display their text evidence
and images together in one Card; recorded frames remain separate and keep
their timestamps, traces and chronology, including returns to a stable state.

`report` re-renders saved results after evidence verification, without model calls.
It does not rerun synthesis or repair a failed study.

`genesia run task.yaml --research-only` (SDK: `run(task, research_only=True)`) stops
after experience and questionnaire execution. It saves original answers, episodes
and evidence but skips synthesis and report rendering. The manifest marks
`phase: research_only`; completed status certifies execution, not simulation quality
or completed analysis. Use `analyze` later only when analysis is wanted.

`analyze` separately re-runs model analysis on saved answers, without new participant
sessions. It verifies the source evidence and answer contents, writes a new run with
source lineage, and uses a separate analysis budget; the original run is not changed.
If a valid participant run reached the configured request timeout during analysis,
use `genesia analyze RUN_DIR --timeout-seconds 300` (SDK:
`analyze(RUN_DIR, timeout_seconds=300)`) to explicitly allow a longer analysis request.
The bounded override is 1 to 600 seconds and is recorded in the derived manifest;
it does not change the source model, task, answers, retries or overall budget.
The staged pipeline analyzes all eligible answers under each exact question, splits only
an oversized question, then composes a report from evidence-bound question findings.
Question analysis follows the research objectives and configured segments, retaining
decision-relevant minority views. Composition receives distinct-Persona control counts and
first-successful-click order counts to distinguish an attempted action from a stated intention.
At most 64 control entries and 64 order pairs are supplied, with explicit omitted-entry
counts; omitted entries are not evidence of absence. Successful execution does not establish backend
success or satisfaction. Final composition first organizes findings, then derives concrete
actions in decision-priority order, and finally distills the summary from the same findings.
Summary points describe discoveries, not a duplicate action list. Headline findings expand
first; important strengths, tradeoffs and segment observations remain eligible even when
they do not require a new action. Counts alone do not determine priority.
When a question is split, composition receives answer ownership to reconcile distinct
participants across chunks; local chunk counts must not be reported as whole-cohort counts.

Finding footers report **evidence contributors** from the saved supporting and counter
answer sets. These sets can cover several questions or clauses and may overlap; their
counts are not disjoint votes or the number endorsing every sentence in a finding.
Use the question-specific descriptive counts and the proposition stated in the prose
for prevalence within this synthetic cohort. Nonselection of an optional item is not
opposition. Rendering clarifies these labels without changing saved answer IDs, synthesis
text, participant membership or numeric counts.

New synthesis stores optional `Finding.title`, `Synthesis.summary_points`, and
`recommendation_order: decision`. The renderer uses the same saved prose and order for HTML
and Markdown. The existing severity × distinct supporting Personas × confidence / effort
score remains an auxiliary calculation; it does not reorder decision-prioritized actions.
Legacy results default to `recommendation_order: score` and retain their previous report
structure and score ordering. `report` does not invent new summaries or re-prioritize old
results; use `analyze` to apply the new composition to saved answers in a separate run.
Recommendations may be empty; finding and action limits are ceilings, not quotas.
Routine uncertainty remains in expandable evidence detail and brief end-of-report
limitations. A caveat needed to prevent a misleading headline belongs in the finding or
action itself. Detailed inputs, counts and source lineage remain in the evidence section.
Use repeatable `--focus` options for the decisions or dimensions the report should
emphasize. Answer IDs and code-computed statistics remain authoritative; Personas are not
rerun. The new analysis has its own status; source_status and source_errors are preserved
in its manifest and displayed in Analysis Lineage. Successful re-analysis does not rewrite
a prior failure.
Legacy staged runs without saved `environment.candidate_labels` require explicit URL-order
labels: `genesia analyze RUN_DIR --candidate-label "Design A" --candidate-label "Design B"`.
Verify the saved start/handoff URLs and actual exposure before supplying them. This only
resolves the task for the new analysis; it does not relabel answers, modify episodes or
repair an originally misgrounded interview. Labels must match the saved question candidates
and cannot override labels already recorded in the task. The new manifest records this
explicit resolution.
For an SDK example with repeatable report focus, see
[`examples/analyze_saved_run.py`](../examples/analyze_saved_run.py).
`insight_report.md` remains a
survey compatibility alias. Success, partial results and runtime failures produce
reports; validation failures of a parsed TaskSpec write a diagnostic report and
raise an error. Malformed YAML or unwritable output locations cannot promise a report.

## Configuration

```yaml
execution:
  max_concurrent_personas: 3
  max_concurrent_model_calls: 3
insight:
  language: en
  context_window: 128000
  input_budget_ratio: 0.6
  chunk_target_tokens: 30000
  max_findings: 8
  focus:
    - "Primary product decision"
    - "Critical uncertainty"
```

Configure categorical profile dimensions with `study.segment_fields`. Integer
dimensions use concise bucket labels that are validated as complete, ordered and
non-overlapping:

```yaml
study:
  segment_fields: ["Core Identity.region", "Core Identity.seniority"]
  segments:
    region:
      source: Core Identity.region
    age_group:
      source: Core Identity.age
      buckets: ["<30", "30-39", "40-49", "50+"]
  segment_combinations:
    region_age: [region, age_group]
```

Omitting buckets groups a named segment by its categorical value. Combinations use
two or three named dimensions and show observed cells, not an exponential Cartesian
product. Preflight rejects more than 100 observed cells per combination.
Configured segment distributions for single-choice, multiple-choice and Likert questions
remain in the structured statistics. Group sizes and distributions are supplied to
composition; decision-relevant segment findings may lead the report rather than being
automatically relegated to an appendix. Groups below five answered Personas are
marked as small samples. These are descriptive synthetic-sample counts only; no
statistical significance or population claim is calculated. Open-text feedback
continues through evidence-grounded synthesis and is not converted into numeric
segment counts. Segment Feedback exposes original text/reasons and code-computed
support/counter counts for reviewed themes. This is not unsupervised clustering or
an independent demographic causal analysis.

Questions can set `candidate: Version A` (any non-empty label) and `explain: true`.
An explained answer retains its exact option(s) in `value` and natural explanation
in `reason`; code counts only value. Candidate labels are preserved in reviewed
findings and separate report sections. Individual feedback favors concrete text
over repeating overall choice tallies; exact reasons remain in the appendix/input.

## Persona-Led Comparison

Exploration builds firsthand context, not identical test paths. Retain the complete
Persona and role policy throughout intent, actions and questionnaire batches. The
participant remains a person rather than becoming an expert reviewer. Ask for each
candidate's experience and suggestions before comparative preference; do not force
different opinions or repetitive research disclaimers. Known unavailable features
remain limits. New protocols require new runs; do not rewrite historical answers.
During experience, no questionnaire or running UX critique is requested. The later
interview receives the full Persona, fixed intent, actual chronology and screenshots,
without replaying earlier reflective evaluations as prepared answers.

Default Persona concurrency is 1. Each live participant owns a browser created
and closed on its worker thread. Actions, questions, conditions and follow-ups
within a Persona stay sequential. Workers share atomic whole-study call/token
reservations and time budget; budgets are not multiplied. Model sessions are
worker-local. Injected SDK gateways/factories must be thread-safe when enabled.
Browser isolation does not isolate shared backend state: use disposable,
participant-isolated prototype data. Browser side effects are not retried.
Browser Back is offered only when the previous browser-history entry is on the permitted
origin. Unsafe Back is rejected before navigation, preserving the current SPA state and
its visible in-product navigation.
Live observation IDs are transient. Targets also carry a small DOM fingerprint; if the
framework replaces a node before an action starts, execution may rebind once only when
exactly one current element matches. It does not use coordinate force-clicks or choose
among duplicate matches. External-origin checks still run on the rebound element. Results
distinguish successful rebinding from pre-execution lookup/actionability failure. This is
automation resilience, not an automatic product retry or usability finding.

### Protected Stages

New CLI tasks and the live template enable `budget.protection`; omitted/null protection
keeps legacy shared allocation. It never raises the configured total budget:

```yaml
budget:
  max_calls: 140
  max_tokens: 4000000
  max_seconds: 2400
  protection:
    research_fraction: 0.3
    analysis_fraction: 0.25
```

Research calls/tokens are reserved per Persona, analysis separately. Exploration can
use only the remainder and released allocations. With these fractions, exploration
ends by 45% of the run time, research by 75%, analysis by the full deadline. Fractions
must leave positive exploration capacity. `exploration_budget` and `max_steps` both
save a final observation and proceed to fixed questions; neither means satisfaction.
Preflight checks question/retry/output minima and complete live frame capacity. It does
not predict all input lengths or guarantee recovery from provider/global-budget failure.
Requests use lossless compact JSON; readable immutable artifacts keep their original format.

Analysis requests use the gateway's actual prompt serialization plus a 4096-byte
validation reserve. Every exact question receives all of its eligible original answers
and reasons together when they fit. Only an oversized question is split into bounded
answer chunks. The final composition receives evidence-bound question findings rather
than all original answers again. If the compact finding set exceeds the configured
context budget, it is reduced in bounded groups without dropping its answer membership.

Configure a context window no larger than the provider's actual limit. UTF-8 bytes are a
conservative text-token upper bound, not billing usage. Output space is reserved
separately. `chunk_target_tokens` is a request-size target, not a Persona count.
Oversized individual answers or irreducible summaries fail explicitly instead of being
silently truncated. Question stages return at most three concise themes with supporting
and counter answer IDs. Final findings must cite those source finding IDs; runtime restores
the complete answer, participant and response-evidence membership. `max_findings`
defaults to 8 and is a cap, not a requested count. Embedding/KMeans clustering is
not part of this analysis.

`analysis_input.json` records stable answer IDs, questions, follow-ups, status
ledger, objectives, statistics and execution outcomes. Invalid methods are excluded
as a whole. Missing, invalid, skipped, not_observed and optional unanswered are
distinct; percentages use answered respondents, with exclusions listed. Multi-select
percentages need not sum to 100. `analysis_provenance.json` records input hashes,
strategy, stage references, processed answer IDs and failures. Processing every
answer does not prove every opinion survived summarization.

Prototype feedback questions can declare a `feedback_role`. The unified report then
shows direct post-use Feedback for each Persona before cross-participant synthesis.
Synthesis findings require an evaluative `feedback_type` and `journey_stage`, and appear
under Design Strengths, Friction and Unmet Needs, Mixed Feedback, Preferences and
Tradeoffs, or User Suggestions. An action sequence, option list, completion state or
confidence score is evidence, not a finding unless the participant explains its design
meaning. Automation-limited answers use `basis=automation`; they remain auditable but
are excluded from product themes and deterministic answer distributions. If automation
or missing observation prevents product feedback, the participant section says so.
Evidence binding preserves an explicitly supplied automation label while replacing
references with the applicable owned episode evidence. It does not classify all
answers as automation merely because exploration reached its step or budget limit.

Question analysis is answer-led: original answers/reasons, the exact question, configured
segment labels, task objectives, requested report focus and code-computed statistics.
Full action traces remain local. Identity attributes are context, not a cause of opinions.
Independent question calls use `execution.max_concurrent_model_calls` with separate HTTP
sessions and a shared budget; custom gateways without `fork()` stay serial. Question text
appears once in `question_definitions`, and original answer values are not shortened.
Final composition uses compact question findings with explicit source IDs. Findings can separately carry
`interpretation`, `design_implication`, `uncertainty` and `counter_answer_ids`; empty fields
are valid. Missing evidence is not a reason to invent a stronger Insight.

LLMs generate interpretations, not run metadata or statistics. Findings cite answer
IDs and response evidence; quotations must exactly match the answer. Code validates
IDs, ownership, quotes and advisory ranking, not free-text causality or model-written
percentages. Synthesis sees execution traces, not raw screenshots; images in the
report support human review. Self-report or a successful click is not task success.
All outputs remain **SIMULATED**, not real-user or representative population data.

## Natural Experience Protocol

For natural exploration use a goal, not a list of features to visit; leave the action
floor at zero and required URLs empty. The Windows case uses five fixed contrasting
profiles, not a representative sample. Its goal is directed Personalization exploration:
try personally relevant options, compare their effects and revisit or restore choices
to form an informed view. Simply accepting the initial configuration is not that goal.
It does not prescribe page coverage, a minimum number of changes or a fabricated need;
keeping defaults after trials and stopping when blocked or unwilling remain possible.
Dynamic follow-ups stay disabled. Session intent includes likely approach and
patience/help seeking. Action expected_result is an expectation; before/after observation
and evidence references identify what can be checked, not verified task success.

Optional `environment.prototype` supplies `scope` and `known_limitations` without prescribing
a tour. Actions give a short personal intent and expected result, not a running UX
evaluation. Optional legacy reflections remain supported and stored in
`Episode.experience_notes`, but participant-facing action history and interviews omit
them. The post-use interview receives the full Persona, fixed intent, actual action
results and a code-built `experience_timeline`. Each item binds one action, including
the participant intent and expected result, to before/after evidence and selected screenshots. Images are inserted
beside their timeline item in the multimodal message. Full raw observations and actions
remain in the Episode for audit; the model does not receive separate parallel arrays or
an isolated evidence-ID whitelist.
Images are direct `image_url` blocks with no separate label block. Persona research sees
a concise JSON output example with exact choice options, not the generated Pydantic
Schema. Personas answer naturally without annotating evidence. After return, code binds
profile grounding for context questions and candidate-scoped Episode evidence for
experience questions, then applies the full schema and semantic checks.
Model-visible timeline items contain only readable step IDs, candidate names, page or
page-transition labels, action,
intent, expected result, execution result and the roles of immediately following images.
For material environments, they also carry the text actually shown in each observation,
including supplied background that was displayed there. Each observation's text appears
once at its first timeline occurrence, labeled before or after the action. This applies
to interviews and other post-review methods, including surveys; it does not add raw live
DOM text. Unvisited materials are not loaded into these requests. Image sampling still
applies to images, not the reviewed material text; omitted image refs are not authorized
as attached evidence. Text describes supplied material, not proof of live execution.
Observation IDs, evidence/image refs, local URLs and session/Persona IDs remain internal.

Sequential Context, Cards and Walkthrough review may advance through different items
with the same Next label. Repeated-action protection distinguishes actual state/card
progress from repeated successful actions on unchanged material. Live target protection
is unchanged, and observation IDs alone are not considered progress.

Questions use `purpose: context | experience | reflection` (default: experience).
Context describes supported background; reflection expresses wishes. Research objectives
and scoring criteria stay out of participant answer prompts. The fixed guide remains a
post-task batch, not a real moderator or a pre-task baseline interview.

Journeys can set `evidence_mode: complete` and `max_images` large enough for
all frames (at most max_steps + one final observation for live). The supported bound
is 64, with a default of 8; configure within the selected provider's image and context
limits. Complete mode fails above the bound instead of silently sampling. Sampled mode
records selected/omitted images. Answer citations are limited to supplied observations.
Capturing every observation does not capture every transient screen state.

Findings use `category: experience | preference | opportunity`. The report separates
preferences and wishes from experiences, and shows source questions. Context or reflection
alone cannot establish an experience finding. Recommendations use investigate, design_change
or enhancement; a wish alone cannot justify design_change. Recommendations may be empty.
These constraints do not prove semantic entailment: review contradictions, concrete
consequences and inflated severity/confidence manually.

Known prototype placeholders, explicitly unimplemented destinations and declared
out-of-scope behavior are study boundaries, not automatic findings or implementation
recommendations. Preserve encounters and actual consequences in the evidence; do not
keep probing known unavailable interactions. Only assess prototype completeness when
it is an explicit objective. Unknown no-response behavior must remain uncertain, not
be assumed to be either a defect or a placeholder. Missing study evidence alone does
not justify new product features. These are prompt rules, not semantic guarantees.

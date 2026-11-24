# Live Result Review

## Status

- `completed`: all required responses validated, synthesis exists and no run error remains.
- `partial`: at least one valid response exists, but required work failed or errors remain.
- `failed`: no valid response was available or an earlier stage blocked the study.

Status describes pipeline completion, not real-user task success or product quality.

## Review Order

1. Run `genesia verify RUN_DIR`; hashes and path confinement are checked, not claim truth.
2. Read `run_manifest.json` for URL, task, model/provider, cohort and budgets.
3. Read `study_review.json` and `research_result.json` for readiness, actual episode mode (`live`), status, metrics and errors. No `environment_readiness.json` or `environment_build.json` is expected: Live bypasses compilation.
4. Compare each recorded action/final observation with that Persona's answers.
5. Confirm invalid methods were excluded from synthesis as a whole, even if completed batches remain in evidence.
6. Trace each finding to validated responses and then to the same participant's encountered observation evidence. Shared content hashes do not permit cross-participant evidence ownership.

Keep product observations, Persona reports, browser automation failures, model/provider failures, budget failures and research-design limits separate. Automation or API failures are not usability findings.

Review `method_batch` evidence_selection for frame omissions. Complete mode preserves
the whole encountered sequence, not unseen UI. Compare before/after refs in the action
trace with expected_result. A default landing page is not a deliberate navigation choice.
Review rejected model actions in events.jsonl as well as failed browser executions:
zero failed executions does not mean zero automation corrections or refused stop attempts.
Live targets use transient observation IDs plus a small DOM fingerprint. If a framework
replaces a target before execution, Genesia may rebind once only when the fingerprint
matches exactly one current element. It never force-clicks coordinates or guesses among
duplicates. The execution result records rebinding or the precise pre-execution failure;
classify either as automation evidence, not a product finding.
Report categories separate experience, preference and opportunity; a reflection-only
answer cannot support an experience finding. Read Source questions for every finding.
Code checks category/provenance, not every natural-language assertion. Do not promote
a suggested confirmation UI to a major problem without a concrete event and consequence.

`exploration_budget` and `max_steps` are system terminations, not self-reported completion;
both normally proceed to fixed research. Inspect budget-plan and stage usage separately.
Review `experience_notes` against their bound previous-action/current-state evidence.
These optional legacy reflections are participant interpretations, not required
outputs. Current experience calls do not request them or replay them in the interview.

For `run --research-only`, synthesis and reports are deliberately skipped. Inspect
the original answers, full Persona, intent, paths, images and untried areas before
accepting role realism. `completed` certifies execution, not simulation quality.
The participant request should contain one code-built `experience_timeline`: each
action is bound to its compact before/after state and adjacent images. Raw Episode
observations remain the audit source. Separate `representative_states`,
`executed_actions` and `allowed_evidence_refs` in the model payload indicate an old run.
The model-visible projection uses readable step IDs, candidate names and page/page-transition labels; observation IDs,
evidence/image refs, local URLs and session IDs stay internal and are code-bound later.
Asymmetric exploration is valid; it does not establish superiority over an untried
counterpart. Do not require different opinions or matched actions to demonstrate roles.

Inspect `analysis_provenance.json` before accepting support counts. Its question stages
must collectively cover every eligible answer exactly once unless an oversized question
is explicitly split. Final findings cite question finding IDs; code restores answer,
participant and response-evidence membership. Known prototype limits remain limitations,
not product recommendations.

Question stages should contain all answers and reasons for one exact question, not full
reports with quotations or recommendations. `insight.max_findings` caps final output; it
is not a target. Final composition receives evidence-bound question findings and code
statistics rather than all original answers again. Inspect stage input/output refs and
answer IDs; original answers remain intact. Coverage and valid references do not certify
model interpretation quality.

`valid_responses`, `invalid_responses` and `missing_responses` count Persona-method responses. Expected responses are selected Personas times configured methods; these counts are not unique participant counts or individual-question counts. URL coverage and successful browser actions do not by themselves establish task success.

## Sharing

A reviewed sample should identify source run ID/status, provider/model, date, participant/response counts, failed actions/errors, synthetic-study limits and hashes/evidence refs for derived media. Never combine separate runs into one apparent study.

# Survey Insight Review

## Output Roles

- `report.html` / `report.md`: one unified TL;DR-first report; `insight_report.md` is an alias.
- `appendix.html` / `appendix.md`: individual profile-grounded answers, segments, readiness and errors.
- `analysis_input.json` / `analysis_provenance.json`: answer IDs, status ledger,
  question-stage coverage and final finding sources.
- `study_review.json`: design/sample readiness, without environment compilation or experience.
- `research_result.json`: complete typed result contract.
- `run_manifest.json`: exact questionnaire, cohort snapshot, provider and budgets.
- `evidence.json`: response/model artifact ownership and hashes.

## Review Order

1. Verify the run with `genesia verify RUN_DIR`; this validates hashes and path confinement, not answer truth.
2. Check requested Personas and expected/valid/invalid/missing Persona-method responses separately. Expected responses equal selected Personas times configured methods, not question count.
3. Review per-question `n_answered`, missing/not-observed/skipped counts and distributions.
4. Check segment group sizes before discussing differences.
5. Trace findings to validated response artifacts owned by that Persona/session. Survey-only grounding uses the profile or `not_observed`, plus `skipped` for inapplicable conditions; never substitute product observations from another run.
6. Separate deterministic counts from model-generated interpretation and recommendations.

For `run --research-only`, report, appendix and analysis artifacts are deliberately
absent. Review `research_result.json`, response evidence and the manifest phase instead;
`completed` means response execution completed, not that analysis or Persona realism
was validated.

## Claims

Prefer:

- “3 of 5 synthetic Personas selected Weekly.”
- “Within this supplied Persona cohort...”
- “The synthesis suggests...”

Avoid:

- “60% of users...”
- statistical significance or population prevalence;
- claims about actual product use when answers are profile-grounded;
- demographic stereotypes not supported by responses;
- treating model-estimated recommendation priority as measured impact.

## Partial Runs

Keep invalid and missing responses visible. Synthesis uses valid responses only; failed methods are excluded as a whole even when completed batch evidence remains. Do not rerun failures and merge them into the same apparent survey. A separate retry is a separate run unless a future Genesia resume contract explicitly records continuity.

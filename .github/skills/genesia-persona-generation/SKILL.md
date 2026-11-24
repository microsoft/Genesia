---
name: genesia-persona-generation
description: 'Plan, confirm, generate, review, approve, validate, and hand off an auditable synthetic Persona cohort with the Genesia SDK and CLI. Use when the user needs a new research-specific Persona JSON rather than selecting from an existing authorized pool. Covers eligibility, segments, quotas, Diversity Anchors, assumptions, all-candidate risk review, cohort quality review, human approval, immutable artifacts, and managed-cohort preflight. Does not run a study.'
argument-hint: '<research need or persona-request.yaml, sample size, cohort requirements, model, and output directory>'
user-invocable: true
disable-model-invocation: false
---

# Genesia Persona Generation

Use Genesia's public Persona planning and generation workflow to create a new auditable
synthetic cohort. Generation and research are separate jobs: this Skill stops after a
validated `personas.json` and never starts a live, recorded, comparison or survey study.

Read [Persona generation](../../../docs/persona-generation.md) for the Phase 1 contract.
Phase 1 supports archetype generation. Grounded microdata, existing-pool matching and a
hosted UI remain future work and must not be presented as available.

## Boundary

Use this Skill when the user has a research need but no suitable authorized Persona file
and explicitly wants Genesia to generate one. If the user already has an authorized JSON
or TSV pool and only needs selection, filtering or sampling, use the relevant study Skill
instead.

The workflow is:

```text
research need -> draft Cohort Plan -> user review -> explicit confirmation
              -> immutable generation -> exact cohort review -> approval
              -> validation -> managed personas.json
```

Do not silently infer a cohort and run research. Do not invent profiles in the Skill,
call a provider directly, copy the packaged generation policy, edit generated Personas
to make validation pass, or treat a random seed as population grounding.

## Required Inputs

Resolve:

1. Product, workflow and decision being researched.
2. Eligibility conditions.
3. Research-relevant segments and exact sample size.
4. Hard versus soft quotas.
5. Diversity Anchors and their research rationale.
6. Necessary and authorized sensitive attributes.
7. Assumptions and known grounding limitations.
8. Output location and deployment model.

Ask only for blocking information. Do not use demographics as proxies for behavior,
technical ability, personality or product attitude. Synthetic cohort coverage is not
population prevalence or statistical representativeness.

Keep engineering purposes such as regression testing in execution metadata, not in the participant's
research description or personal goals. Reuse the existing plan's soft Diversity Anchors for relevant
coverage differences; do not prescribe product opinions or add a new generation stage.

## Procedure

### 1. Create A Draft Plan

For conversational intake:

```powershell
$env:GENESIA_MODEL = "EXACT_MODEL_ID"
python -m genesia personas create --output persona-plan
```

For a structured request, start from
[`examples/persona-request.yaml`](../../../examples/persona-request.yaml):

```powershell
python -m genesia personas plan examples/persona-request.yaml --output persona-plan
```

Planning may invoke the configured deployment model when segments are not already
specified. Never silently switch models. The output directory must be new; Genesia
refuses to overwrite an existing `cohort-plan.yaml`.

### 2. Review With The User

```powershell
python -m genesia personas review persona-plan/cohort-plan.yaml
```

Present the concise plan: eligibility, segment allocations, hard/soft quotas, Diversity
Anchors, assumptions, limitations and feasibility issues. Check that segment quotas sum
to the sample size, every hard requirement is feasible, and independently allocated
anchors do not create contradictory reviewer contexts. When compatibility matters,
prefer one explicit composite anchor over several ambiguous cross-products.

The default is one initial candidate per requested slot. A request for 100
Personas starts with 100 candidates, not an upfront pool of 300. Check
`candidates_per_slot` even when reusing an older example: never silently choose
an upfront multi-candidate pool. More than one candidate per slot is an explicit
advanced choice that needs a reviewed rationale and cost scope.

Before confirmation, show the initial candidate count separately from the final
cohort size and bounded repair/provider-attempt ceilings. Report conservative
reservation units as reservations, not actual tokens, money or a promised runtime.

Do not confirm on the user's behalf. Obtain explicit approval of this exact plan. If the
user changes the research population or requirements, revise or create a new draft and
review it again.

### 3. Confirm The Exact Plan

Only after explicit user approval:

```powershell
python -m genesia personas confirm persona-plan/cohort-plan.yaml
```

Confirmation records the immutable plan hash. Do not edit the confirmed plan manually;
create and confirm a new plan when requirements change.

### 4. Generate

```powershell
python -m genesia personas generate persona-plan/cohort-plan.yaml `
  --output persona-generations/my-cohort --workers 5 --open
```

Generation uses the confirmed allocation and first writes one candidate per slot
under the default policy, followed by deterministic gates, semantic risk review,
selection decisions, evidence and immutable execution metadata. Explicit
multi-candidate plans retain their recorded allocation. Failed or partial jobs
keep diagnostics but do not publish a study-ready `personas.json`.

Generation and candidate review use bounded slot-level concurrency. Every completed slot
is persisted in `generation-checkpoint.json`. If a process is interrupted, continue the
same plan, model, and output directory instead of starting another job:

```powershell
python -m genesia personas generate persona-plan/cohort-plan.yaml `
  --output persona-generations/my-cohort --workers 5 --resume
```

For a confirmed one-candidate-per-slot plan, finish the initial batch before
bounded repair of genuinely deficient slots. Preserve healthy slots and the
original failure/rejection/review evidence. A repair is not an extra initial
candidate pool: report generation, review and repair attempts separately.
Exhausted repair or blocking cohort quality must remain an explicit failure,
not trigger another whole-cohort run or a weaker threshold.

Do not edit a confirmed multi-candidate plan to continue it under the new
single-candidate default, and do not splice its outputs into a fresh job.

Never merge candidates or outputs from different generation jobs. Never repair a failed
job by editing `personas.json`, its plan, manifest or companion artifacts.

For a terminal original single-candidate partial job, the public transport-only
recovery can continue saved requests only when every remaining slot has a recorded
`ReadTimeout` and unused provider attempts. Explain the new timeout, remaining
original budget and possible duplicate remote charges before explicitly invoking:

```powershell
python -m genesia personas recover persona-generations/my-cohort `
  --output persona-generations/my-cohort-recovered --workers 2 `
  --timeout-seconds 600 --allow-transport-replay
```

This derives one hash-bound continuation from one source, retaining returned
profiles, their IDs and reviews. It does not increase logical slot/refill limits
or create new variation keys. Keep the original artifacts unchanged. Do not
chain recoveries, use it for quality rejections or claim remote cancellation.
For interruption before a terminal manifest, repeat the identical recovery
command with `--resume`; recorded replay requests are never blindly reissued.
Complete-cohort review and separate human approval still apply.

### 5. Review And Approve The Exact Cohort

Open `report.html`, inspect every selected profile and review `quality-report.json`.
Confirm candidate-review coverage, selected/unselected/rejected counts, anchor coverage,
profile distributions, pairwise similarities, warnings and errors. A completed generation
is not study-ready until the user approves this exact cohort.

Also inspect the selected-cohort semantic review. It checks cross-anchor contradictions,
template repetition, insufficient behavioral diversity, demographic-to-behavior coupling
and overall cohort realism after deterministic selection. A high-severity result blocks
`personas.json` publication.

Do not infer approval from the earlier Cohort Plan confirmation. Plan confirmation
authorizes generation; cohort approval accepts the actual generated people.

Only after explicit user approval:

```powershell
python -m genesia personas approve persona-generations/my-cohort
```

Approval is hash-bound to the exact generation manifest, Persona file and selected IDs.
Never approve on the user's behalf or edit profiles to make the cohort acceptable.

### 6. Validate

```powershell
python -m genesia personas validate persona-generations/my-cohort
```

Require a valid result before study use. Inspect at minimum:

- `generation-manifest.json` for status, selected IDs, hashes and full-cohort policy;
- `cohort-plan.yaml` for confirmed plan and assumptions;
- `execution-snapshot.json` for exact model and budget;
- `quality-report.json` for allocation deviations and failures;
- `candidate-personas.json` for selection and risk-review provenance;
- `report.html` for cohort coverage and limitations;
- `cohort-approval.json` for the exact human-approved manifest and Persona hashes;
- `evidence.json` for artifact integrity.

Validation checks integrity and managed-cohort constraints; it does not prove realism,
representativeness or suitability for every research question.

### 7. Hand Off Without Running Research

Reference the validated file from a study task:

```yaml
cohort:
  source: ../persona-generations/my-cohort/personas.json
  size: 12
  seed: 42
```

If the manifest requires the complete cohort, use every selected generated Persona.
Do not sample a subset and assume the approved quotas survive. Generate a new confirmed
cohort for a different size or composition. Study preflight rechecks the managed
manifest, plan confirmation, hashes and full-cohort constraint.

## Privacy And Publication

Treat plans, candidates, generated profiles, model evidence and reports as private by
default. Do not commit them or publish profile details without explicit authorization.
Generation must not create real contact details, real-world identity claims, medical
history or unsupported sensitive traits.

## Completion Report

Return:

- plan path, ID, status and confirmed sample size;
- exact model and generation directory;
- generation ID/status and selected count;
- generation/review attempt counts, worker count, and any resumed checkpoint;
- segment, quota and Diversity Anchor coverage;
- surfaced assumptions, limitations, retries or deviations;
- validation result and evidence integrity;
- candidate review coverage, cohort quality errors/warnings and approval status;
- study-facing `personas.json` path and any full-cohort requirement;
- confirmation that no research study was started.

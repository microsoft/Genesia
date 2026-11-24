# Persona Generation and Cohort Planning

> Status: Phase 1 implemented. Grounded microdata, existing-pool matching and a hosted UI remain future work.

## 1. Summary

Genesia loads an authorized Persona JSON or TSV file through `CohortSpec`, applies exact
filters or deterministic sampling, and uses the selected profiles in a study. Phase 1 also creates
auditable synthetic Personas through a separate, explicitly confirmed generation workflow.

The Persona generation workflow is:

```text
User research need
  -> conversational intake
  -> system-compiled Cohort Plan
  -> one-page user confirmation
  -> immutable plan and execution snapshots
  -> Persona skeleton allocation
  -> plan-grounded candidate generation
  -> deterministic and model-assisted quality checks
  -> cohort-level diversity selection
  -> accepted Persona JSON consumed by the existing study runtime
```

The central product decision is that Genesia must not silently infer a cohort and immediately run a
study. It first explains who it proposes to generate, why those people are relevant, which assumptions
it made, and which claims the available grounding cannot support. The ordinary user reviews a concise
research plan, not provider IDs, token limits, hashes or retry settings. Genesia records those technical
details automatically in a separate execution snapshot.

Generation and research remain separate jobs. The generated Persona file is an auditable input to the
existing runtime, not an ephemeral side effect of `genesia run`.

### Current implementation

Phase 1 includes conversational or structured planning, one-page confirmation, deterministic segment,
quota and Diversity Anchor allocation, one initial candidate per slot by default, all-candidate semantic risk
review, bounded cohort-level selection, profile-distribution and pairwise-similarity audits, exact-cohort
semantic review, exact-cohort approval, immutable generation artifacts, managed-manifest preflight checks
and the existing `Persona` JSON output contract. Candidate generation uses the packaged
`src/genesia/resources/persona_generation.md` policy and a typed ten-dimension profile schema. The CLI is
available under `genesia personas`.

```powershell
$env:GENESIA_MODEL = "YOUR_MAESTRO_MODEL"
genesia personas create

# Or start from the tracked structured example.
genesia personas plan examples/persona-request.yaml --output persona-plan
genesia personas review persona-plan/cohort-plan.yaml
genesia personas confirm persona-plan/cohort-plan.yaml
genesia personas generate persona-plan/cohort-plan.yaml --output persona-generations/demo
genesia personas approve persona-generations/demo
genesia personas validate persona-generations/demo
```

Generation accepts `--workers` for bounded slot-level concurrency. The default is five.
Each completed generation and review stage is written to `generation-checkpoint.json`.
After interruption, rerun the same plan, model and output directory with `--resume`;
completed slot work is not invoked again. Resume verifies evidence integrity and reconciles completed
responses by candidate ID, including interleaved concurrent responses and responses persisted after
the last checkpoint. A saved high-risk rejection remains rejected across interruption. All initial
generation work and reviews finish before refill generation starts. Only missing/invalid generation,
high-risk candidates or cross-slot duplicate deficits can receive one additional generation operation
per affected slot; passing, nonduplicate slots are retained. A refill must pass the same gates and
review. Requests, failures, previous profiles and reviews remain auditable even without a checkpoint.
An interrupted refill request without a saved response consumes its allowance: resume fails that slot
honestly rather than risking another paid generation. Existing `semantic-repair-1` evidence is supported.

After complete cohort selection, a full-name collision or excessive surname concentration can trigger
one batched model request to replace only the conflicting display names. The other profile attributes,
slot assignments, IDs, and original candidate evidence stay unchanged. Fixed or retained names are not
replaced. The report records the changes, and the final names must pass the same checks before
exact-cohort review. Resume reuses a saved repair response rather than paying for another repair; an
unsuccessful or interrupted repair leaves the original publication errors in place.

The SDK's `estimate_generation_budget(plan, model)` can preview a draft plan's conservative budget
without confirming or modifying that plan. It covers the initial batch, at most one refill per slot,
at most two review operations per profile version, and one optional name-repair operation for a
multi-person cohort, including bounded provider attempts. A transient
review failure retries the same saved profile, never blindly regenerates it. Exhausted review or refill
allowances keep failed/partial diagnostics and prevent study-ready publication.
Estimation is not authorization: both SDK generation and CLI generation still require the exact
confirmed plan before any provider work.

For an original terminal single-candidate partial job whose remaining slots
have recorded `ReadTimeout` failures, Genesia provides explicit transport-only
recovery. It requires unused provider attempts for every affected saved request
and capacity within the original whole-job call, reservation and wall-time
ceilings:

```powershell
genesia personas recover persona-generations/demo `
  --output persona-generations/demo-recovered --workers 2 `
  --timeout-seconds 600 --allow-transport-replay
```

This is a single-source continuation, not a merged cohort or another candidate
pool. The source remains immutable and is archived with its hashes. The new
execution snapshot records the timeout and remaining budget. Returned profiles,
published IDs, review evidence and logical initial/refill counts are preserved.
Each eligible failed payload gets at most one further provider call, bounded by
its original provider-attempt allowance; no new variation key is invented.
Remote cancellation is unknown, so replay can duplicate model charges.

An interrupted recovery can use the identical command with `--resume`.
Already-recorded replay requests are not reissued, even if no response was saved.
Terminal recoveries cannot be resumed, chained to reset limits or used to retry
returned/high-risk/duplicate profiles. New profiles pass ordinary review and
cannot displace retained profiles. The complete cohort must still pass its
normal semantic review and separately receive human approval.

SDK callers can use `genesia.recover_personas(source, output, timeout_seconds=600)`.
It executes the same checks and explicit recovery action; it does not approve
the resulting cohort.

After generation, `report.html` shows every selected profile and the exact-cohort semantic review.
Review these alongside `candidate-personas.json` and `quality-report.json` before separately approving
the actual cohort. A confirmed plan is not cohort approval; managed study preflight requires the
hash-bound approval of the complete selected cohort.

The deployment supplies the model through `GENESIA_MODEL`; ordinary confirmation does not expose model,
provider, budget or hash controls. Phase 1 uses archetype mode. Sections describing grounded and pool
modes define planned extensions, not current support.

## 2. Goals

The module should:

1. Turn a natural-language research request into a structured, reviewable Cohort Plan.
2. Cover research-relevant differences, not only demographic variety.
3. Honor requested cohort size and hard quotas exactly when feasible.
4. Produce internally consistent, distinct and research-relevant Persona profiles.
5. Prefer grounded population structure over model-invented population structure.
6. Record all assumptions, seeds, hashes, prompts, model calls and selection decisions.
7. Produce `Persona` records that the existing `load_cohort()` path can consume unchanged.
8. Fail visibly when required quotas or quality requirements cannot be met.

## 3. Non-goals

The first version will not:

- claim that synthetic Personas are real research participants;
- infer population prevalence from an LLM;
- certify statistical representativeness;
- replace recruiting, surveys or interviews with real participants;
- infer protected or consequential traits from demographic or behavioral proxies;
- generate real contact details, real-world identity claims or medical history;
- automatically start a research run after generation;
- update a generated Persona over time from behavioral telemetry;
- provide a general-purpose demographic simulation engine.

## 4. Core Concepts

### 4.1 Eligibility

Eligibility determines who belongs in the target population.

Examples:

- has used meeting recap in the last 90 days;
- manages a team of at least five people;
- uses the product at least monthly;
- participates in the workflow being studied.

Eligibility is a boundary, not a diversity target. A generated Persona that fails a required eligibility
condition is invalid.

### 4.2 Research Segment

A segment captures a difference expected to affect the research question.

Examples:

- frequent managers who review and share recaps;
- occasional individual contributors who only read recaps;
- first-time users learning an onboarding flow;
- experienced administrators managing a complex configuration.

Segments should normally be based on role, workflow, behavior, product familiarity or usage context.
They answer: "Why is this participant relevant to this study?"

### 4.3 Demographic Quota

A demographic quota controls cohort composition for fields such as region, age band, gender,
education or seniority. It answers: "How should the selected cohort be balanced?"

A quota can be:

- `hard`: exact count required; generation blocks if infeasible;
- `soft`: best-effort target; deviations require an explanation.

Demographic attributes must not implicitly determine behavior, technical ability, personality or product
attitude.

### 4.4 Diversity Anchor

A Diversity Anchor is a research-relevant axis along which the cohort should include meaningfully
different perspectives. It is proposed from the research goal and reviewed by the user.

Typical anchors include:

- product familiarity: novice, regular, expert;
- usage frequency: daily, weekly, occasional;
- technical confidence: low, medium, high;
- workflow style: individual, collaborative, approval-driven;
- decision style: quick accept, careful verify, consultative;
- AI attitude: confident, cautious, skeptical;
- device context: desktop, mobile, mixed;
- accessibility or environmental constraints, when relevant and authorized.

Anchors are not universal. A payment study and an onboarding study should not receive the same default
anchors. Every proposed anchor must include a rationale tied to the research request.

### 4.5 Random Seed and Grounding Seed

These are different concepts:

- A **random seed** makes quota rounding, candidate variation and final selection reproducible.
- A **grounding seed** is an authorized evidence row, profile, aggregate distribution or other factual
  basis used to constrain a Persona.

A random seed cannot make an ungrounded Persona representative. It only makes the same assumptions
repeatable.

## 5. User Experience

### 5.1 Phase A: Conversational Intake

The user starts with ordinary language:

> Generate 12 Personas for a Teams meeting recap study. Include managers and individual contributors,
> frequent and occasional users, split between the US and Europe.

The intake agent extracts known constraints and asks only blocking questions whose answers materially
affect the plan. It should ask no more than two or three questions at once and should normally need only
one clarification round. The preferred question order is:

1. What product, feature, workflow or decision is being researched?
2. What must participants have done, used or experienced to be eligible?
3. Which roles, behaviors or usage patterns must be covered?
4. How many Personas are needed?
5. Which distributions are hard requirements and which are preferences?
6. Is there an authorized Persona pool, respondent dataset, public microdata or aggregate distribution?
7. Are any sensitive attributes necessary, authorized and appropriate?

The intake should infer obvious context but expose it as an assumption. It should not ask the user to
learn the internal Cohort Plan schema. Non-blocking choices receive safe defaults: inferred diversity
targets are soft, names are omitted, technical settings use product defaults, and advanced controls stay
collapsed. The system asks again only when it cannot safely determine eligibility, cohort size, a hard
quota, sensitive-data use, data destination or an applicable cost boundary.

### 5.2 Phase B: Plan Proposal

Genesia produces a one-page draft plan with:

- target population and eligibility;
- sample size;
- research segments and integer allocations;
- demographic hard and soft quotas;
- proposed Diversity Anchors and rationales;
- assumptions and unresolved questions;
- feasibility warnings;
- a plain-language time or cost indication when applicable;
- a plain-language data-use notice when materials leave the local environment.

Provider, model, seed, token budget, retry policy, prompt hash and other audit fields are recorded by the
system but remain under Advanced details. They are not ordinary review requirements.

The review must answer four questions clearly:

1. Who will be generated?
2. Why are these differences relevant?
3. What did the system assume?
4. What cannot be claimed from this cohort?

### 5.3 Phase C: User Review

The user can:

- confirm the plan and start generation;
- change cohort size;
- add, remove or edit segments;
- promote a soft target to a hard quota;
- remove a proposed Diversity Anchor;
- request another plan proposal;
- cancel without making model generation calls.

The default review presents a short summary and two actions: **Modify plan** and **Confirm and generate**.
Users do not approve each anchor, slot, provider setting or Persona individually.

Confirmation freezes the user-facing research plan and records its SHA-256. The system then freezes a
separate technical execution snapshot containing provider, model, permissions, source hashes, prompt and
schema hashes, budgets and retry policy. Technical details are auditable without becoming user homework.

Another user confirmation is required only when a change materially affects who will be generated, the
use of sensitive attributes, the external recipient of supplied data, or a user-visible cost boundary.
Routine retries, model deployment revisions within an approved product configuration, generated IDs and
other operational details do not trigger another prompt.

### 5.4 Phase D: Generation, Cohort Review and Validation

After confirmation, Genesia:

1. expands the plan into exact Persona slots;
2. assigns immutable constraints and Diversity Anchors to each slot;
3. generates exactly one initial candidate for each slot by default;
4. rejects candidates that fail hard validation;
5. performs semantic risk review for every successfully generated candidate;
6. retains valid, nonduplicate slots and refills only deficient slots once, after the complete initial
   generation/review batch; explicitly configured multi-candidate plans instead use bounded cohort-level
   combination search;
7. audits review coverage, anchor coverage, profile distributions, repeated synthetic
   naming, and pairwise research/published-profile similarity;
8. performs a selected-cohort semantic review for anchor conflict, template repetition,
   behavioral diversity, demographic coupling and cohort realism;
9. writes the Persona file, manifest and review report only when quality gates pass.

On successful generation, the user sees a compact result summary such as "12 Personas generated; all
required quotas met; every candidate reviewed." The user must then inspect the exact selected profiles
and quality report and explicitly approve the hash-bound cohort. Plan confirmation authorizes generation;
cohort approval accepts the actual generated people. Managed study preflight rejects new generated
cohorts until this approval exists.

#### Review-policy details

- With the default `candidates_per_slot: 1`, a missing/invalid, high-risk or later duplicate slot may
  be regenerated once after all initial work completes. High-risk repair uses the saved review feedback;
  duplicate repair must avoid retained profiles without displacing them. Rejected evidence stays in
  repair history. Repeated profiles, repeated failures and a second high-risk review block publication.
- Candidate review transport failures get at most one extra review operation on the same saved profile,
  within provider/budget limits. They do not authorize a replacement profile. A high-severity
  selected-cohort review is never retried or repaired into success.
- Broad constraints such as an age band, region or occupation family do not fix
  the exact age, city or occupation. Unsupported source labels are normalized to
  synthetic assumptions, and some explanations are replaced with standardized
  provenance text. This normalization is not proof that a value was independently
  generated; reviewers should also inspect the preserved original model response.
- Selected-cohort review uses publishable values rather than internal provenance
  explanations. Its prompt treats exact narrative repetition as blocking when a
  value covers at least 20% of the cohort, or the deterministic similarity summary
  breaches the confirmed threshold. This is a model-review instruction, not a
  deterministic 20% hard gate or a guarantee of behavioral diversity.
- Public request, `create` and `plan` defaults are one initial candidate per slot and a `0.88`
  duplicate-similarity threshold. Explicit advanced plans with 2–5 candidates per slot retain their
  candidate-pool behavior. Existing confirmed three-candidate plans are not reinterpreted, edited or
  mixed with a new single-candidate job; their hashes and resume bindings remain intact.
- Output distinguishes requested/selected cohort size, initial candidate count, generation attempts,
  successful profile versions, refill attempts and review attempts, including per-slot evidence refs.
  For example, 100 initial slots plus four refills means 104 generation operations, not “only 100
  generated”; unsuccessful operations may produce fewer than 104 valid profile versions.

## 6. Cohort Plan Contract

The YAML below illustrates the implemented Phase 1 contract. It is intentionally separate from the current
`CohortSpec`, which describes how a study loads an existing Persona file.

```yaml
version: 1
id: meeting-recap-us-eu
status: draft
description: Evaluate review, correction, and sharing of AI-generated meeting recaps.
sample_size: 12
seed: 1813573689
candidates_per_slot: 1
duplicate_similarity_threshold: 0.88
eligibility:
  product_user: "yes"
  meeting_frequency: weekly_or_more

segments:
  - id: frequent_manager
    description: Managers who frequently review or share meeting recaps
    quota: 3
    required: true
    constraints:
      role: manager
      usage_frequency: daily
  - id: occasional_manager
    description: Managers who use recap occasionally
    quota: 3
    required: true
    constraints:
      role: manager
      usage_frequency: monthly
  - id: frequent_ic
    description: Individual contributors who frequently consume or edit recaps
    quota: 3
    required: true
    constraints:
      role: individual_contributor
      usage_frequency: daily
  - id: occasional_ic
    description: Individual contributors with occasional recap use
    quota: 3
    required: true
    constraints:
      role: individual_contributor
      usage_frequency: monthly

quotas:
  - field: region
    policy: hard
    counts:
      US: 6
      Europe: 6
  - field: gender
    policy: soft
    counts:
      female: 6
      male: 6

diversity_anchors:
  - field: verification_style
    values: [quick_accept, careful_verify, collaborative_review]
    policy: soft
    scope: cohort
    minimum_per_value: 1
    rationale: The study evaluates trust, correction and sharing of AI-generated content.
  - field: technical_confidence
    values: [low, medium, high]
    policy: soft
    scope: cohort
    minimum_per_value: 1
    rationale: Confidence may affect feature discovery and willingness to correct generated content.
  - field: ai_attitude
    values: [confident, cautious, skeptical]
    policy: soft
    scope: cohort
    minimum_per_value: 1
    rationale: The feature contains AI-generated information that users may verify differently.

assumptions: []
limitations:
  - Archetype coverage is designed for perspective diversity, not population representation.
plan_sha256: null
```

## 7. Plan Construction

### 7.1 Deriving Segments

The planner should derive candidate segments in this order:

1. explicit user requirements;
2. eligibility and target role;
3. workflow position and decision authority;
4. product familiarity and usage frequency;
5. research-specific behavior likely to change the observed experience.

The planner must not introduce segments solely because they are common Persona-writing conventions.
Each inferred segment includes a rationale and confidence.

### 7.2 Suggesting Diversity Anchors

The planner maps the research context to a small set of candidate anchors:

| Research characteristic | Candidate anchors |
|---|---|
| Onboarding or learnability | prior experience, learning style, technical confidence |
| AI-generated output | AI familiarity, trust, verification style |
| Collaboration | team role, collaboration style, decision authority |
| Mobile or cross-device workflow | primary device, interruption context, connectivity |
| Administration | environment complexity, governance responsibility, risk tolerance |
| Accessibility objective | relevant assistive technology or access need, only when authorized |
| Purchasing or upgrade decision | purchase authority, budget sensitivity, organization size |

The planner should normally propose two to four anchors. Too many anchors create sparse combinations,
inflate the required sample and encourage superficial differences.

An anchor is accepted only when:

- it could plausibly change behavior or feedback for the stated task;
- its values are understandable and non-overlapping;
- it does not encode a stereotype through a demographic proxy;
- the planned cohort is large enough to cover it meaningfully.

Each accepted anchor states whether it is hard or soft, whether coverage applies to the whole cohort or
inside each segment, and its minimum count per value. The ordinary review renders these rules as a few
editable chips and expected counts; the underlying fields are available under Advanced details.

Anchors describe background or behavioral variation, not expected findings. A plan may include cautious
and confident AI users, but it must not encode that a participant will distrust a particular feature,
encounter a particular problem or prefer a particular design. Prior findings, desired conclusions and
review checklists are excluded from blind Persona generation prompts.

### 7.3 Quota Allocation

Phase 1 accepts integer counts for each independent marginal distribution. The conversational planner
converts explicitly requested percentages into reviewable integer counts whose total equals
`sample_size`; structured requests provide those counts directly. The allocator then assigns every
field deterministically across the precompiled segment slots. Hard counts are exact or planning blocks;
soft counts report deviations caused by fixed segment constraints.

Phase 1 does not infer correlations between fields. Region, gender, age, education and similar margins
are allocated independently except where a segment fixes a value. The review discloses that independence
assumption. Joint cells, cross-tabulations, microdata weighting and maximum-entropy joint allocation are
future grounded-mode capabilities. They must not be simulated by multiplying margins.

### 7.4 Feasibility Review

Before confirmation, deterministic checks validate:

- segment quotas sum to `sample_size`;
- every quota field sums to `sample_size`;
- fixed segment values do not conflict with hard quotas or eligibility;
- hard anchor coverage fits in the available slots;
- a stable complete slot allocation can be produced.

The generation command separately creates and records the technical budget and execution snapshot.
Grounding-source authorization and sensitive-attribute policy checks are required additions before the
future grounded and pool modes are enabled.

## 8. Planned Grounding Modes

The modes in this section are future extensions and are not accepted by the Phase 1 request schema.

### 8.1 Grounded Mode

Grounded mode starts from authorized row-level profiles, survey respondents, public microdata or another
documented source. The source provides population structure or factual constraints. The LLM may turn
supported facts into a coherent research profile, but it must not change fixed source facts.

Each Persona records which source row or aggregate cell grounded it. Source values may be minimized or
redacted in the generated profile while their hashes and field lineage remain in the private manifest.

Grounded mode can support calibrated composition claims only to the extent justified by the source and
weighting method. It still does not turn synthetic responses into real-user evidence.

### 8.2 Pool Mode

Pool mode selects and optionally normalizes Personas from an existing authorized pool. It should prefer
matching over regeneration when profiles already satisfy the plan.

Selection records:

- pool hash;
- matching criteria;
- selection seed;
- eligible candidate count per segment;
- selected IDs;
- unmet quotas and fallback decisions.

### 8.3 Archetype Mode

Archetype mode is used when no grounding rows or Persona pool are available. It creates constrained
research archetypes from the confirmed plan.

In this mode:

- demographic values come from explicit plan slots;
- behavior comes from confirmed research segments and Diversity Anchors;
- prevalence is not inferred;
- unsupported details are omitted rather than made vivid;
- reports state that the cohort is designed for perspective coverage, not population representation.

## 9. Persona Slot and Skeleton

The allocator expands the confirmed plan into exact slots before calling a model:

```json
{
  "slot_id": "slot-007",
  "segment_id": "frequent_ic",
  "fixed": {
    "region": "Europe",
    "age_band": "35-44",
    "gender": "female",
    "education": "bachelor",
    "seniority": "senior_ic",
    "usage_frequency": "daily"
  },
  "anchors": {
    "verification_style": "collaborative_review",
    "technical_confidence": "medium",
    "ai_attitude": "cautious"
  },
  "assumptions": [
    "Anchor combination was allocated for cohort coverage, not inferred from demographics."
  ]
}
```

Fixed values cannot be changed by the model. Phase 1 generates all ten dimensions:

1. Core Identity, including education and physical attributes;
2. Personality & Cognitive Style;
3. Digital Behavior & Online Habits;
4. Interests & Preferences;
5. Economic & Financial Profile;
6. Social & Relational Dynamics;
7. Daily & Lifestyle Patterns;
8. Balance & Self-Management;
9. Decision-Making & Behavioral Insights;
10. Other Unique Attributes.

Inside candidate and audit artifacts, every leaf attribute contains a concrete `value`, a one-sentence
`explanation`, and a `basis` of `fixed`, `anchor`, `research_request`, or `synthetic_assumption`.
Archetype mode uses independent synthetic assumptions to complete attributes that are not fixed by the
slot, including demographic, physical, personality, economic, relational and lifestyle fields. These
values must not be inferred from another demographic or behavioral signal and are never treated as
observed or grounded facts. The schema retains `unknown` for future grounded and pool workflows, but
archetype generation rejects it. The published `personas.json` unwraps these records to direct values.

## 10. Candidate Generation

By default, the system first issues exactly N logical generation operations for N slots at candidate
index zero. Every initial slot is attempted before any refill, and all valid initial candidates receive
semantic risk review. Only deficient slots can receive one additional generation operation; valid slots
are not regenerated to manufacture variety. Explicit advanced plans can request 2–5 candidates per slot.
The model receives:

- the immutable slot skeleton;
- research context;
- the packaged ten-dimension Persona generation policy;
- allowed profile schema;
- explicit instructions not to infer protected or unrelated attributes;
- a cohort target summary derived entirely from the frozen slot matrix;
- the required output schema.

The policy is adapted from a behavioral-data Persona template, but the current input is a confirmed
single Persona slot rather than Reddit history. It contains no Reddit-specific instructions and no
`Privacy Constraints` section. Code-level size, contact-detail and prompt-pattern gates remain active;
removing that prompt section does not disable runtime safety checks.

Candidate requests use stable variation keys derived from:

```text
plan hash + random seed + slot ID + candidate index
```

The key makes requests and artifact ownership traceable, but it does not guarantee that a remote model
will return identical text on a later call. Reproducibility means deterministic planning and selection
over preserved candidate artifacts. Exact replay uses saved responses rather than calling the model
again. Slots are generated independently from the same frozen matrix so concurrency and completion order
cannot change later prompts.

Temperature alone is not a diversity strategy. It can vary wording without producing meaningfully
different research perspectives.

## 11. Quality and Diversity

### 11.1 Deterministic Hard Gates

A candidate is rejected when:

- it does not validate as the required JSON schema;
- a fixed slot value is missing or changed;
- a machine-checkable eligibility rule fails;
- a field or the complete profile exceeds its schema size bound;
- detectable URL, email, phone number, street address, control character or known prompt-instruction
  pattern appears;
- it duplicates an existing ID;
- required research fields are empty;

These checks are code-owned and do not depend on an LLM quality score. They are bounded pattern checks,
not general PII detection: names, employers, obfuscated text and semantic variants can still escape them
and therefore remain part of semantic risk review and optional human inspection.

### 11.2 Semantic Risk Review

Natural-language contradiction, unsupported sensitive inference, stereotype risk, prompt-like content
and unsupported detail are not fully provable by deterministic code. A separate model-assisted review
flags these risks and preserves its explanation. High-confidence policy matches may reject a candidate;
ambiguous cases remain visible for optional human inspection. "No issue detected" is not a certification
of truth, safety or representativeness.

### 11.3 Phase 1 Candidate Review And Selection

Phase 1 first applies deterministic schema, slot/basis, size, contact-detail and prompt-pattern gates.
A separate model reviews **every successfully generated candidate**; `high` risk rejects a candidate,
while `low` and `medium` remain visible in issues. Exact duplicates within a slot are rejected.
When a confirmed plan uses one candidate per slot, the system retains all passing nonduplicate initial
profiles, even when an earlier slot is missing. Later cross-slot duplicates, invalid/missing generation
and high candidate risk are the only refill deficits. Each affected slot can receive one extra generation
operation after all initial work and reviews finish. A repaired slot cannot displace a retained profile.
Transport failures during review retry only the same saved profile, at most once. No full-cohort semantic
failure triggers regeneration. Evidence and repair history retain prior versions; final slot candidate
counts are accompanied by actual generation/refill/review attempt counts and successful profile-version
counts so replacements are never hidden.

In explicitly configured multi-candidate mode, remaining candidates enter a deterministic bounded beam
search over complete slot combinations. The
selection objective minimizes maximum and total token-Jaccard research-behavior similarity while
respecting the configured duplicate threshold. The research-behavior surface includes fixed fields,
anchors and research-relevant behavioral attributes while excluding low-value biography. The algorithm
is cohort-level and bounded rather than greedy, but it is not an exhaustive optimizer for arbitrarily
large cohorts.

After selection, code separately audits the published profiles. This audit reports exact age, gender,
nationality, residence, occupation and surname distributions without treating those attributes as causes
of behavior. Repeated full names, extreme synthetic surname concentration, incomplete candidate-review
coverage or missing required anchor coverage block publication. Other unrequested concentration remains
a warning for human review.

A final selected-cohort model review evaluates cross-anchor contradictions, repeated narrative templates,
insufficient behavioral diversity, demographic-to-behavior coupling and overall cohort realism. `high`
severity blocks Persona publication; `low` and `medium` remain visible for human review. This review is
recorded with request/response evidence and cannot certify real-world validity.

### 11.4 Planned Advanced Semantic Scoring

A future phase may add independently reviewed scores for constraint fidelity, grounding fidelity,
internal consistency, research relevance, behavioral specificity, stereotype risk and unsupported-detail
rate. A possible constrained objective is:

$$
S(p) = Q(p) - \lambda \max_{s \in C} \operatorname{similarity}(p, s)
       + \mu \operatorname{coverageGain}(p, C)
$$

where:

- $Q(p)$ is candidate quality;
- $C$ is the already selected cohort;
- similarity combines structured overlap and semantic profile similarity;
- coverage gain rewards missing confirmed anchor values.

Hard quotas would remain constraints, not weighted preferences. Phase 1 now performs bounded global
combination search with deterministic token similarity; learned quality scores, embeddings and the
weighted objective above remain future work.

### 11.5 Audit Coverage

Phase 1 preserves the slot matrix, all candidates, selected IDs, all-candidate risk reviews, rejected
reasons, unselected status, allocation issues, pairwise similarities, profile distributions and summary
counts. Repeated-narrative embedding analysis and demographic-to-behavior correlation audits remain
Phase 2 work. Correlation auditing is particularly important because a cohort can look balanced while
repeatedly assigning technical confidence, authority or risk tolerance according to age, gender or
region.

## 12. Outputs

A generation job writes an immutable directory. Failed or partial jobs keep diagnostic candidates but
do not publish a study-ready `personas.json`:

```text
persona-generations/<generation-id>/
  cohort-plan.yaml
  plan-review.json
  execution-snapshot.json
  slots.json
  candidate-personas.json
  personas.json                 # completed jobs only
  generation-manifest.json
  quality-report.json
  report.html
  cohort-approval.json          # after explicit review and approval
  evidence.json
  events.jsonl
  artifacts/
    <content-sha256>.json
    <content-sha256>.txt
```

### 12.1 `personas.json`

The study-facing file uses the current public contract:

```json
[
  {
    "id": "persona-001",
    "profile": {
      "Core Identity": {
        "full_name": "Avery Rowan",
        "age": "41",
        "gender": "Nonbinary",
        "nationality": "Canadian",
        "occupation": "manager",
        "region": "US"
      },
      "Psychographics & Personality": {
        "personality_traits": {
          "openness": "High",
          "conscientiousness": "High"
        },
        "cognitive_style": "Evidence-oriented and sequential"
      }
    }
  }
]
```

The study-facing profile follows the existing Persona-pool style: dimensions contain direct values, not
`value`/`basis`/`explanation` wrappers. Generation metadata, distribution ownership and review evidence
stay in `cohort-plan.yaml`, `slots.json`, and `candidate-personas.json`. Fixed cohort fields such as
`region`, `role`, or `usage_frequency` remain available as ordinary profile values for downstream
filtering and segmentation. The study-facing file is written only after every required slot, hard quota
and deterministic gate passes.

`age_band` quotas retain both a concrete numeric `age` inside the band and the explicit
`age_band` metadata. A macro `region` remains a separate filtering field and does not replace the
fictional city-level `current_residence`. The published Core Identity also includes
`research_segment` and configured Diversity Anchor values so downstream studies can select or
describe cohorts without reconstructing generation artifacts.

### 12.2 `generation-manifest.json`

The Phase 1 manifest is intentionally compact. It records:

- generation ID and status;
- confirmed plan hash and technical execution snapshot hash;
- final Persona file hash when completed;
- selected Persona IDs and the full-cohort requirement;
- attempted, generated, reviewed, rejected, unselected and selected candidate counts;
- whether exact cohort approval is required;
- hashes for every required companion artifact;
- surfaced issues.

Companion artifacts carry the detail: `execution-snapshot.json` records model, budget, generator version,
candidate settings and schema hashes; `slots.json` records the allocation; `candidate-personas.json`
records candidate ownership, selected/unselected/rejected status, evidence refs and all risk reviews;
`quality-report.json` records candidate-review coverage, selection algorithm, anchor coverage, profile
distributions, pairwise similarities, selected-cohort semantic review, quality errors and warnings.
Model request evidence preserves the exact prompt payload and schema. Phase 1 archetype mode has no
grounding-source hashes; those become mandatory with future grounded and pool modes.

### 12.3 Human Review Report

The HTML report should prioritize decisions:

1. plan summary and confirmation status;
2. generated cohort distribution;
3. segment and anchor coverage;
4. assumptions and grounding limitations;
5. quality failures, retries and deviations;
6. compact Persona summaries;
7. provenance and technical appendix.

It must repeat that synthetic Persona coverage is not population prevalence or human-participant
evidence.

## 13. SDK and CLI

The public API should keep planning, generation and research explicit:

```python
from genesia import (
    approve_persona_generation,
    confirm_persona_plan,
    generate_personas,
    plan_personas,
)

draft = plan_personas(request, gateway=gateway)
confirmed = confirm_persona_plan(draft)
manifest = generate_personas(confirmed, "persona-generations/demo", gateway=gateway)
approval = approve_persona_generation("persona-generations/demo")
```

The SDK returns a `PersonaGenerationManifest`. Use the CLI `personas validate` command for complete
directory and evidence verification.

Proposed CLI:

```powershell
genesia personas plan request.yaml --output persona-plan
genesia personas review persona-plan/cohort-plan.yaml
genesia personas confirm persona-plan/cohort-plan.yaml
genesia personas generate persona-plan/cohort-plan.yaml --open
genesia personas approve persona-generations/GENERATION_ID
genesia personas validate persona-generations/GENERATION_ID
```

For an interactive entry point:

```powershell
genesia personas create
```

This command conducts intake and writes a draft plan. It does not bypass plan confirmation.

Plan confirmation and exact-cohort approval are separate one-action decisions in the ordinary flow.
An optional non-interactive or enterprise form may record reviewer identity and expected hashes. A stale
or edited hash must fail, but ordinary users are not required to understand or enter a hash.

## 14. Integration with Existing Genesia

The generated `personas.json` is referenced by the existing task:

```yaml
cohort:
  source: ../persona-generations/GENERATION_ID/personas.json
  size: 12
  seed: 42
```

The two seeds have different roles:

- generation seed controls allocation and candidate selection;
- `CohortSpec.seed` controls sampling when a study uses only a subset of the generated file.

When all generated Personas should participate, the task should select all generated IDs or set the
study cohort size to the generated count. If a task references a managed generation directory,
`preflight` must verify that the manifest status is completed, the Persona file hash matches, explicit
cohort approval is bound to the exact manifest and Persona hashes, and the selected IDs preserve required
generated-cohort constraints. A random subset is not assumed to preserve the approved quotas. External
Persona files remain supported without a Genesia generation manifest; they continue through the existing
external-file path without managed-generation checks.

## 15. Failure and Fallback Semantics

The plan uses:

- `draft`: plan exists but is not confirmed;
- `confirmed`: user-facing plan hash and technical execution snapshot are frozen;

Persisted generation manifests use:

- `completed`: all required slots and hard quality gates passed;
- `partial`: diagnostic candidates exist, but no study-ready Persona file is published;
- `failed`: execution started but no valid deliverable can be produced.

An infeasible plan, missing provider or unavailable required input stops before generation with a concise
CLI error and does not create a manifest. Phase 1 does not persist a `running` status.

Fallback rules are part of the confirmed plan. Examples:

- a hard quota shortfall blocks;
- a soft quota shortfall may complete with a visible deviation when the confirmed policy permits it;
- failure to cover an optional anchor is reported and follows its confirmed soft policy;
- model/provider failure does not switch providers silently;
- exhausted candidate retries preserve all attempts but never publish an incomplete cohort as
  study-ready.

## 16. Safety, Privacy and Research Integrity

The planner and generator must:

- minimize collected and generated attributes;
- require justification for sensitive attributes;
- avoid inferring protected traits from behavioral proxies;
- keep private grounding records out of study-facing profiles when unnecessary;
- support source-level retention and redaction policies;
- label all generated profiles as synthetic in manifests and reports;
- treat model output as untrusted data;
- prevent generated profile text from overriding runtime instructions;
- never describe synthetic consensus as prevalence;
- never present generation quality scores as proof of external validity.

Stable pseudonymous IDs remain the actual Persona identifiers. The required `full_name` profile field
contains a fictional synthetic name; it is never treated as a real identity or grounding evidence.
Generation preserves the model-provided name, including Unicode, rather than assigning a name from
a code-owned list. Blank names are rejected. The existing full-name uniqueness and surname-concentration
publication gates still apply; removing a name list does not weaken cohort review or authorize retries.
Demographics, companies, institutions and physical attributes follow the same independent
synthetic-assumption rule unless explicitly fixed by the confirmed plan.

## 17. Evaluation Strategy

### 17.1 Offline Deterministic Tests

Tests should cover:

- exact integer allocation and deterministic tie-breaking;
- incompatible hard quotas;
- plan confirmation invalidation after edits;
- slot constraint preservation;
- stable generation IDs and seed derivation;
- duplicate and contradiction rejection;
- prompt-injection content rejection or neutralization;
- manifest and Persona file hash verification;
- blocked, partial and completed status transitions;
- loading generated output through the existing `load_cohort()`.

### 17.2 Quality Benchmarks

Curated benchmark plans should test:

- demographic-only requests;
- behavior-first requests;
- mixed hard and soft quotas;
- marginal distributions without joint data;
- grounded microdata and pool selection;
- small cohorts where anchor coverage is impossible;
- sensitive-trait requests;
- highly similar generated candidates;
- stereotype correlation traps.

Human reviewers should compare candidate cohorts without knowing which generation strategy produced
them. Evaluation should measure constraint fidelity, usefulness for the research task, redundancy,
unsupported detail and stereotype risk separately.

### 17.3 End-to-End Acceptance

An acceptance run should demonstrate:

1. natural-language intake;
2. plan proposal and user edits;
3. hash-bound confirmation handled by the system;
4. reproducible slot allocation;
5. bounded generation and retries;
6. completed quality and diversity audit;
7. successful loading by `CohortSpec`;
8. unchanged existing research behavior;
9. evidence verification for all generation artifacts.

## 18. Implementation Phases

### Phase 1: Deterministic Planner and Archetype Generation

- `PersonaGenerationRequest`, `CohortPlan`, `PersonaSlot` and result schemas;
- structured request file plus model-assisted conversational planning;
- deterministic quota allocator;
- plan review, confirmation and system-managed hashes;
- typed ten-dimension Persona generation schema with per-attribute explanations and basis labels;
- one initial candidate per slot, bounded deficit-only refills, explicit advanced multi-candidate plans,
  duplicate checks and anchor coverage validation;
- hard validation, semantic risk review, retries and JSON output;
- manifest and HTML report;
- existing `load_cohort()` compatibility plus manifest-aware preflight for managed generations.

### Phase 2: Advanced Cohort Quality and Diversity

- advanced structured and semantic similarity checks;
- cohort-level constrained selection;
- anchor coverage and stereotype-correlation audits;
- model-assisted quality review with retained explanations.

### Phase 3: Grounded and Pool Modes

- existing Persona pool matching;
- authorized row-level grounding;
- marginal calibration and weighting;
- field-level lineage and minimization;
- feasibility and source coverage reports.

### Phase 4: Product Integration

- interactive UI for intake and plan review;
- generation job service and cancellation;
- manifest-aware study preflight;
- private artifact storage and retention controls;
- comparison of generated cohorts across plan versions.

## 19. Decisions Recommended for Version 1

1. Require one-page plan confirmation before generation without exposing routine technical settings.
2. Keep generation separate from `genesia run`.
3. Support archetype mode first, but label its representativeness limitation prominently.
4. Use research segments as the primary structure and demographics as balancing constraints.
5. Let the planner propose two to four editable Diversity Anchors with explicit soft coverage defaults.
6. Generate concrete values for all ten Persona dimensions while labeling unsupported details as
  independent synthetic assumptions.
7. Use deterministic code for allocation and hard gates; use models for planning assistance, profile
   narration and advisory quality review.
8. Write existing `Persona` JSON and add managed-generation manifest checks to preflight.
9. Preserve plan, source, prompt, model, candidate and selection provenance.
10. Treat quota infeasibility as a visible failure.

## 20. Open Questions

The following decisions need product review before implementation:

1. Should version 1 support only archetype mode, or include selection from an existing Persona pool?
2. Which deployments require authenticated confirmation identity beyond the default one-click flow?
3. Which sensitive attributes are prohibited by default versus allowed with justification?
4. Should model-assisted quality scoring be enabled by default or opt-in because of cost?
5. Which embedding or similarity implementation is acceptable for an optional dependency-free core?
6. What is the maximum supported cohort size and candidate multiplier for version 1?
8. Should a completed generation be immutable, requiring a new generation ID for every change?
9. Which grounding sources and licenses are acceptable for bundled examples?
10. How should the UI explain the difference between perspective coverage and population
    representativeness?

## 21. Reference Lessons

This proposal incorporates useful patterns found in adjacent internal prototypes without copying their
limitations:

- the existing Persona generation scripts demonstrate initial and incremental prompt-driven profile
  generation, strict JSON cleanup and separate quality scoring;
- Emma demonstrates research-purpose, role, task and archetype-first selection plus strong execution
  provenance and explicit simulated-evidence labeling;
- current Genesia provides deterministic Persona loading, fixed-seed cohort sampling, readiness checks,
  evidence hashing and strict separation between synthetic reports and real-user evidence.

The proposal strengthens those patterns with an explicit plan contract, hard and soft quotas,
reproducible allocation, cohort-level diversity checks, plan confirmation before generation, and
hash-bound approval of the exact selected cohort before research use.
# Dayline Spec + Screenshots Sample

[中文](README_CN.md) | [Run the case](../README.md) | [Research report](report.md)

A reviewed public edition of one **completed, full 20-Persona study** using the
current specification-and-screenshots workflow. Environment construction,
material review, interview and analysis completed in the same run. No
analysis-only recovery or participant pooling was used. This study uses
`gpt-6.1-sol`, temperature 1, and the V3 answer-stage policy.

## What ran

| Item | Result |
|---|---|
| Input | One specification and eleven static screenshots of Design A |
| Constructed environment | 11 states, 11 image-backed Cards, 26 text-supported transitions |
| Shared background | 13 exact quoted passages retained as supplied context |
| Cohort | 20 fixed authorized synthetic Personas from the public pool |
| Research | 10 questions per Persona, in two batches, without follow-ups |
| Execution | 110 steps; 20 valid responses; no invalid/missing responses or failed actions |
| Analysis | All 200 eligible answers processed; 6 findings and 4 recommendations |
| Verification | 882 evidence entries passed integrity checks |

Personas chose paths among captured states, not actions in a live application.
Each interview request included the text and images actually reviewed by that
Persona. This selected intact run had no model validation corrections or manual
answer edits. Previous failed attempts were retained separately and were not
merged into this study.

Fidelity review recorded two omissions in compiled state text: the displayed
action-intent expiry in Message Workstream, and the Medium risk/recall warning in
Message Result. Original screenshots remain in the source evidence. These
warnings limit textual completeness; neither expiration nor recall behavior was
tested. Citation and integrity checks do not establish semantic completeness.

## Read the result

The [report](report.md) preserves the saved Chinese synthesis, findings,
recommendations and limitations. It discusses retaining parallel context and
separate decision boundaries while improving supporting-text readability and
authorization terminology. Content, access and responsibility still need
scenario-specific verification.

| Perceived usefulness | Count |
|---|---:|
| Useful | 17 / 20 |
| Mixed | 3 / 20 |
| Not useful | 0 / 20 |
| Insufficient material | 0 / 20 |

These are descriptive choices from one synthetic cohort, not adoption estimates
or evidence that this input mode is better or worse than a live study. A new
model run need not reproduce the same paths, answers or counts. Seed-based
sampling from the full public pool does not select this exact historical cohort.

## Publication boundaries

The public report removes local run headings, private appendix links and
operational metadata. It adds a publication note explaining how to read merged
evidence counts. The saved research prose is otherwise unchanged; this is not
a second model analysis or an independent replication.

The [manifest](manifest.json) records source status, hashes, model/provider
configuration for this sample and publication transformations. The case itself
remains user-configurable. The provider did not record an underlying immutable
model snapshot, so the upstream model ID is not a fixed version guarantee.

Complete profiles, original Persona/session IDs, answers, model requests and
raw run files are not included. They remain in private research records.
Static materials do not verify acceptance, authorization, delivery, persistence,
real Agents, mobile behavior or assistive-technology usability. All feedback is
synthetic, not research with human participants or a representative population.

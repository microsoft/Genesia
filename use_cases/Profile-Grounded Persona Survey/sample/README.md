# Task Delegation Survey Sample

[中文](README_CN.md) | [Run the case](../README.md) | [Saved synthesis](report.md) | [Question distributions](distributions.json)

A reviewed public edition of one completed survey with **20 fixed authorized
synthetic Personas**, using profiles and a neutral hypothetical concept only.
This sample uses **`openai/gpt-6.1-terra` via OpenRouter, temperature 1**,
with the new V3 answer-stage policy.
No prototype, product observations, screenshots, Cards or Graph were supplied.

## What completed

| Item | Result |
|---|---|
| Questionnaire | 12 definitions: multi-select, single choice with explanations, matrices and open text |
| Conditional logic | Separate first-task and refusal questions gated by delegation position |
| Method responses | 20 valid; none invalid or missing |
| Question slots | 240 total: 220 answered, 20 conditionally skipped |
| Grounding | 220 profile-grounded answers; no product evidence references |
| Analysis | 220/220 eligible answers processed; 8 findings and 6 recommendations |
| Product interaction | No environment construction, observations or actions |
| Integrity | 465 evidence entries verified |

All twenty selected “Would consider delegating at least one task,” so each
answered the first-task branch and skipped the refusal branch. No negative
response was invented to populate that branch. Offline tests separately cover
refusal, uncertainty, unsupported answers and their denominators.

All model outputs passed on their first validation attempt. There was no manual
answer editing, analysis recovery or whole-survey restart.

## Selected descriptive results

| Question | Choices in this synthetic cohort |
|---|---|
| Create a draft without sending/publishing | 20 would allow within explicit limits without per-action confirmation |
| Modify an existing document | 20 prefer confirmation before every execution |
| Send a message | 20 prefer confirmation before every execution |
| Delete a file | 19 prefer confirmation before every execution; 1 would not delegate |
| Uncertain output | 17 prefer an uncertain draft to review; 3 prefer stopping to ask; none selected bounded continuation |
| Initial setting | 11 work; 7 personal; 2 both work/personal |

For approval information, all twenty selected content/change, recipient,
permission scope and recovery options. Thirteen selected reasons/sources and
eighteen selected version changes; eleven selected all six fields.

The [saved Chinese synthesis](report.md) interprets these as conditional openness
to reviewable preparation, not unrestricted execution. Recommendations are
concept hypotheses and validation directions, not observed defects or
instructions to ship a default permission policy.

## Research-quality limits

- **Ceiling effects:** all twenty expressed conditional willingness and selected
  similar approval boundaries; deletion has one stricter refusal. These responses do not establish
  adoption likelihood or independently validated human consensus.
- **Information selection is not ranking:** eleven selected all six information
  fields; the checkbox question does not establish their relative priority.
- **Not independent human judgments:** common model tendencies, the concept
  framing and the shared questionnaire can contribute to convergent answers.
  Complete processing does not validate synthetic realism.
- **No actual product use:** these answers cannot establish usability, benefits,
  safety, adoption, willingness to pay or market prevalence.
- **No observed refusal segment:** the refusal question has zero answered and
  twenty skipped, not twenty missing or negative answers.
- **Broad tasks:** recognizing a task as relevant does not mean willingness to
  delegate it, nor does it determine implementation order.
- **Future instrument work:** a separate most-important/forced-choice question
  and concrete task vignettes could better examine trade-offs. They were not
  added retrospectively to this run.

The [distributions](distributions.json) retain per-question answered, skipped and
unsupported counts. Multi-select totals may exceed 100%. The approval matrix is
categorical, not an averaged numeric score. Merged finding support counts are
not the number agreeing with every clause.

## Provenance and sharing

The [manifest](manifest.json) records source status, hashes, protocol and the
provider/model used for this sample. The upstream ID is not a recorded immutable
model snapshot. New runs remain user-configurable and need not reproduce these
answers.

This is one synthetic study, not evidence that the selected model is generally
better at role-playing or that more varied answers are more realistic.

The public report removes local run headings and private appendices, adds a
publication note, and otherwise retains the saved synthesis unchanged. It is
not a second model analysis. Full profiles, original Persona/session IDs, raw
answers, requests and private logs remain excluded.

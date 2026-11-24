# Dayline A/B Comparison Sample

[中文](README_CN.md) | [Run the case](../README.md) | [Journey GIFs](index.html)

A reviewed public example of **20 synthetic Personas comparing two Dayline layouts**.
It contains 400 newly generated interview answers over the original 340 recorded
steps. The current interview and report use `gpt-6.1-sol`, temperature 1, with the
V3 answer-stage policy. No participants or answers were pooled from different studies.

## Read the results

- [Native report](report.md) / [HTML report](report.html).
- [Standalone report](standalone-report.html), with one embedded complete journey.
- [All twenty journeys](index.html) / [P01 preview](journeys/p01-paired.gif).
- [Preference choices and reasons](preferences.json).

The native report is Genesia's saved Chinese synthesis of the current interview.
Its HTML and standalone editions present the same findings, not additional analyses.

## What the sample shows

| Preference | Count |
|---|---:|
| Design A | 14 / 20 |
| Design B | 4 / 20 |
| No meaningful preference | 2 / 20 |
| Insufficient experience | 0 / 20 |

The central tradeoff is focused reading versus a board-level overview. The
reports discuss preserving both strengths, improving reading space and
follow-up after declining, and making supporting information easier to inspect.
Preference counts do not establish causal superiority, adoption or real execution quality.

## Study provenance

| Item | Scope |
|---|---|
| Cohort | 20 fixed authorized synthetic Personas, shown as P01–P20 |
| Experience | A then B, isolated browser state, autonomous paths |
| Interview | 20 questions in 8+8+4 batches, no follow-ups |
| Data | 20 valid responses, 400 answers, 340 steps; zero invalid/missing responses or failed actions |
| Analysis | All 400 eligible answers processed; 10 findings and 6 recommendations |

The new interview and native analysis are **completed**. The original experience
source remains **partial**; its twenty saved participant journeys are reused
unchanged. Final answers were regenerated for all twenty participants, but
no browser interaction or initial intent was repeated. Both source statuses are
recorded without rewriting the original study.

The [publication manifest](manifest.json) records the study date, source lineage,
artifact hashes and per-frame references. Full source records, internal deployment
configuration and operational audit notes remain private. The public edition
retains research findings, recommendations, counts and limitations while removing
those internal details.

**Version mapping:** public Design A corresponds to source Design B; public Design B
corresponds to source Design D. Labels in prose, quotations and GIF headers were
explicitly relabeled. New answer choices come from the new interview; screenshot
content, action order and GIF bytes are unchanged. [Prototype provenance](prototype.json) identifies the studied
snapshot; runnable source is included in the [parent case](../README.md#run-the-bundled-case).

## Media and publication boundaries

Each GIF contains the participant's complete A-to-B journey. Frames are saved
observations **before** the labeled action. Yellow rings mark recorded click
targets, not pointer motion. Playback uses two seconds per step and a four-second
final hold, not actual elapsed time. ADVANCE and STOP are study controls, not
product features.

This sample excludes complete profiles, original Persona/session IDs, model requests,
full raw traces, private appendices, credentials and local paths. Synthetic product
fixtures and Persona-entered fictional task text remain visible in screenshots.
Run directories generated on your machine contain more information and should
not be published without a separate review.

These are synthetic sessions, not human-participant research or a representative
population sample. Fixed order, carryover and unmatched self-chosen tasks limit
comparisons. No real Agent actions, message delivery, publishing, cross-device
persistence or assistive-technology usability were validated. Hashes establish
file integrity, not the truth of every interpretation.

GitHub does not execute HTML. Download the sample to open its reports and gallery
locally. A new run follows the same workflow but uses your model and selected
cohort; it need not reproduce these answers or preference counts.

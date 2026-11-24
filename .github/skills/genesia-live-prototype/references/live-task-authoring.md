# Live Task Authoring

## Participant Contract

Write the goal as an outcome rather than an expected click path. State the starting context, what the participant wants, when they may stop or abandon, and that the target is an isolated prototype.

For directed exploration, invite hands-on use of the specified feature without giving
the participant a reporting or comparison agenda. Let the Persona choose relevant
controls and alternatives, inspect effects, adjust/revisit/restore choices, and stop
when personally finished, blocked or unwilling. Name the scope
(for example Personalization, not all Settings); do not prescribe a tour or add a
fabricated work problem. Keep a genuine task-completion study separate from this goal.

Record the supplied feature boundary in `environment.prototype.scope`, and only known
constraints in `known_limitations`. This is optional for old configurations, not a
required inventory of every button. A visible no-op with an unknown cause stays unknown.
Experience calls ask for a short personal intent and expected result, not a running
UX critique. Optional legacy reflections remain archived but are not replayed in
participant-facing action history or the post-use interview.

Map every objective to at least one neutral question. Ask about discovery, choices, hesitation, visible feedback, confidence and limits. Genesia keeps questions out of the experience phase and uses the same Persona episode afterward.

Place objectives/criteria in `study` and questions in `methods`. Interview, survey, design review and task outcome review are post-experience methods; none changes `environment.mode: live`. Use `environment.mode: survey` only for a separate profile-only questionnaire without product interaction.

Live connects directly to Playwright and bypasses environment compilation. Do not author Cards/Graph or run `prepare` as a required live conversion step. For material-only research use `auto`; for recordings use the recorded Skill. A running prototype is not post-compiled into a captured environment.

## Persona Data

`cohort.source` must point to user-supplied, authorized JSON or TSV data. Do not generate placeholder profiles and present them as research Personas. Keep private datasets ignored and outside shareable samples.

Use explicit IDs when exact cohort membership matters. Use seeded sampling for a reproducible sample from a larger dataset. Only declare `sample_requirements` for fields present in the supplied profiles.

## Live Bounds

- `width` / `height`: preserve the required layout without unnecessary image area.
- `screenshot_width`: optional width for the single saved/model JPEG. The browser
  still lays out at `width` / `height`; the capture is proportionally downsampled.
  It must not exceed `width`. `screenshot_quality` controls JPEG quality. No second
  full-resolution frame is retained.
- `handoff_urls`: optional same-origin, ordered live stages. The Persona may use the
  untargeted `advance` action when the current stage is complete. Runtime opens the
  next URL in a fresh browser context without adding study UI, isolating browser
  history and storage while preserving the same Persona episode and execution trace.
- `candidate_labels`: required when `handoff_urls` is non-empty. List labels in exact
  `start_url`, then `handoff_urls` order. Counterbalanced tasks must reverse both URLs
  and labels; questionnaire order does not determine stage identity.
- `max_steps`: hard decision limit, including stop.
- `min_actions_before_stop`: non-stop engagement floor; lower than `max_steps`.
- `required_url_fragments_before_stop`: optional live URL areas that must appear in recorded observations before `stop` validates. Use relative fragments, not full URLs.
- `evidence_mode`: `complete` preserves all encountered frames in chronological order;
  `sampled` (compatibility default) selects a bounded subset and records omissions.
  Research input binds actions, participant intent, expected results and selected
  frames into one ordered timeline; it does not ask the model to join parallel arrays.
- `max_images`: hard image attachment bound (default 8, up to 64); respect provider
  image/context limits. Complete mode errors if it cannot fit.
- `batch_size`: questions per research call.

A Persona may abandon. Failed actions remain evidence. Do not increase bounds merely to force a preferred path.

Live also supports untargeted `scroll` with value `up` or `down`. It moves the
primary visible scroll container and records the resulting observation. Live text
and targets describe viewport-visible content, so below-fold content must be
revealed before it can support an interaction claim. Use scrolling when the goal
naturally requires lower content; do not mechanically scroll for coverage.

Natural studies should leave the action floor at zero and required URL fragments empty.
Context, experienced feedback and reflection questions use explicit `purpose` values.
The participant sees neutral question text, not study objectives or scoring criteria.
Background questions in this guide are retrospective, not a pre-task baseline interview.
The pre-task intent separately records relevant preferences, likely approach, patience
and help seeking. Action `expected_result` is an expectation, never verified success.

URL coverage verifies that areas were visited, not that a setting changed or a task succeeded. Reserve it for explicitly controlled coverage studies, not personally directed exploration. Clear or redesign the fragments when changing the prototype feature.

## Permissions And Budgets

Live studies normally require:

```yaml
permissions:
  send_persona: true
  send_materials: true
  send_screenshots: true
```

Budgets are local safety ceilings. Reserved image token units deliberately overestimate usage; provider-reported tokens remain separate and are not guaranteed billing figures.

`budget.protection: {research_fraction: 0.3, analysis_fraction: 0.25}` protects each
Persona's share of the research allocation and an analysis allocation. Unused research
reservations are released after that Persona finishes. Fractions also reserve time
windows before the run deadline. Omitted/null protection retains legacy shared budgets.
Preflight checks fixed question/retry minima and `max_images >= max_steps + 1` for
complete live evidence; it cannot predict all input sizes, model behavior or failures.

## Portability

Paths in task files resolve relative to the task. Use a local ignored directory or a caller-supplied override for private Persona data. Never put API keys in YAML; configure only an environment-variable name.

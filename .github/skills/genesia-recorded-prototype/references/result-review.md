# Recorded Result Review

## Interpretation Boundary

A recorded study supports claims about the supplied material actually encountered by each Persona. `auto` may produce Context, Cards or Graph; inspect the compilation level and actual episode modes before describing the experience. A fixed walkthrough does not establish that a Persona discovered the feature or chose the recorded path. A captured-graph choice is a choice among evidence-backed states, not control of the recorded UI. Neither establishes unsampled live behavior.

Keep these separate:

- sampled frame observation;
- supplied trace event;
- chronology-derived transition;
- Persona interpretation of the recording;
- model-generated card/state description;
- supplemental Context labeled as background rather than a visited UI state;
- unverified live product behavior.

## Review Order

1. Run `genesia verify RUN_DIR`; this checks hashes and path confinement, not the truth of claims.
2. Read `run_manifest.json` for source, sampling, provider, cohort and budgets.
3. Read `environment_readiness.json` and `environment_build.json` for auto assessment, citations, output level, issues and supplemental Context. Explicit prepared modes do not promise these compiler artifacts.
4. Inspect sampled timestamps and trace attachment, plus `ui_cards.json` / `state_graph.json` when produced. Missing Cards/Graph is expected for lower output levels.
5. Read `research_result.json` and `report.md` for actual episode modes, compilation summary, readiness, status, coverage, valid/invalid responses and errors. A prior `prepare` run is not proof of the current run's compilation.
6. Trace findings to validated response artifacts and then to that Persona's encountered source or observation evidence. Do not borrow another participant's references.
7. Treat fidelity reviews and recommendations as advisory; validated citations do not prove semantic correctness or action causality.

## Status And Coverage

For a full run, `completed` means required methods and synthesis validated. For
`run --research-only`, it means required experience and responses completed while
analysis and reports were deliberately skipped. Neither status certifies recording
completeness, Persona realism or product success. Report coverage appropriate to the
episode mode: reviewed Context, seen/unseen Cards, recorded-path progress or captured
states. A sampled recording may still omit important evidence even when every available
item was visited.

Response metrics count Persona-method responses, not individual answers or unique Personas. Failed methods retain completed batch evidence but are excluded from synthesis as a whole. Keep method failures, environment/provider failures and evidence-limited Context/Cards separate; do not relabel any run status.

## Sharing

A reviewed sample should state the source run ID/status, source hash, sampling interval/frame cap, whether a trace was supplied, compilation level/limitations, actual episode modes, Persona/response counts, coverage, errors and evidence verification. Label findings as synthetic Persona research, not observed real-user behavior. Keep recordings, Persona data, extracted frames and reports private unless their owners explicitly authorize distribution.

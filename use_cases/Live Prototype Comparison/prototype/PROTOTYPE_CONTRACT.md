# Dayline Live Prototype Contract

This repository is a runnable, deterministic UI prototype that can be used as
an external live environment by Genesia or another browser-based research tool.
It is not a production service and does not connect to real Agents, files,
accounts, messages, permissions, or publishing systems.

## Source Layout

```text
index.html                 Browser entry point
src/main.tsx               React bootstrap
src/App.tsx                UI, variant routing, and research-mode behavior
src/data.ts                Synthetic deterministic demo fixtures
src/workspace.ts           Local workspace state and transitions
src/styles.css              Shared layout and visual tokens
src/design-b.css           Design B layout overrides
src/design-c.css           Design C control-room layout overrides
src/design-d.css           Design D kanban board and task-inspector layout
src/i18n/                  English and Simplified Chinese strings/state
tests/                     State and browser journey tests
vite.config.ts             Local development/build configuration
```

## URL Contract

All four variants are served from the same origin:

```text
/?design=a&research=1
/?design=b&research=1
/?design=c&research=1
/?design=d&research=1
```

- `design=a` selects Design A.
- `design=b` selects Design B.
- `design=c` selects Design C (control room).
- `design=d` selects Design D (kanban board).
- `research=1` hides the in-product A/B/C/D switch so a study tool owns the
  candidate transition.
- Without `research=1`, people may switch variants inside the prototype.

Unknown or missing design values fall back to the prototype's normal default.
Research tasks should always provide an explicit design query.

## Readiness Contract

After initialization, the application root exposes:

```html
data-prototype-ready="true"
```

A research harness may wait for this marker before attempting interaction.
The marker means the deterministic UI is initialized; it does not certify
network connectivity, external integrations, or production readiness.

## Fixture And Safety Contract

- Every task, Agent, artifact, event, decision, receipt, organization, and
  identity is synthetic demo content.
- The visible account is `Demo User`.
- Accept, request-changes, authorization, receipt, and task-creation actions
  update local prototype state only.
- No action sends a message, modifies a real file, invokes an Agent, or writes
  to an external service.
- Local persistence uses browser storage and is not cross-device state.
- Browser contexts should be isolated between research variants when state
  carryover is not intended.

## Comparison Contract

Design A, Design B, Design C, and Design D use the same task-detail components,
fixtures, and state model. They differ in presentation and task browsing:

- navigation density;
- work-list detail;
- reading-panel layout;
- action placement;
- optional summary presentation.

Design C uses horizontal dark navigation, interactive work-overview cards, a
card-based work list, and a separate result canvas. Overview cards operate the
existing work-list filters without changing the open task. Decision controls
sit above the result on desktop and return to the bottom at 720px and below.
It uses the same acceptance, revision, authorization, and simulated-receipt
boundaries as A and B.

Design D opens a three-column board: needs you, in progress, and handled.
Local drafts live behind a compact toolbar button, shown only when drafts
exist. Its expandable list does not reserve a board column; the existing
New task button and global task search still create and open local drafts.
No draft data is deleted. Work grouping is derived from the existing task model, not a second
workflow state. Clicking a card opens the shared task inspector alongside the
board; at 1100px and below the inspector replaces the board area. Back to board
and Escape close the inspector without losing session drafts or the task tab.
Switching to D from another design keeps the current task open.

The board shows three work-status columns, independently of A/B/C's preserved
list filter, and shares their text query. Column counts reflect matching work
cards, excluding local drafts. The draft list is independent of the board
filter; global task search still includes drafts.
Revision requests, scope confirmations, and authorizations awaiting a receipt
remain in progress. Returned revisions need attention again. Handled includes
accepted artifacts, declined sends, and simulated deliveries; it does not mean
every card was delivered. Local drafts never start an agent. There is no drag
operation that bypasses review or authorization.

The variants must not silently diverge in task content, available decisions, or
action consequences. A study may compare interface experience, but a fixed
variant order does not establish a causal A/B effect.

## Interaction Contract

Research automation should use visible accessible controls and text rather than
private React state or injected navigation. Supported study surfaces include:

- work-item filters and selection;
- Design D board search, card selection, and task-inspector close/reopen;
- Result, Workstream, and Context tabs;
- artifact version selection;
- Sources & scope;
- Accept;
- Request changes with specific feedback.

The research tool, not this prototype, should perform backstage transitions
between isolated variants.

## Run And Verify

```powershell
npm ci
npm run build
npm test
npm run test:ui
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

The corresponding Genesia case pins an exact commit and uses:

```yaml
environment:
  mode: live
  start_url: http://127.0.0.1:4173/?design=a&research=1
  handoff_urls:
    - http://127.0.0.1:4173/?design=b&research=1
```

## Adapting This Format

Another prototype does not need to use React or Vite. To follow this example,
it should provide:

1. stable HTTP URLs for every variant;
2. an explicit readiness signal;
3. deterministic, redistributable fixtures;
4. visible accessible interactions;
5. documented state and persistence boundaries;
6. no hidden real-world side effects;
7. one command that starts the pinned prototype;
8. tests for the journeys used by the research task.

## License

The prototype source is available under the MIT License. See [LICENSE](LICENSE).

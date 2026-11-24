# Dayline M0 Product Prototype

[Archival Chinese source](README.md)

The [maintained case](../README.md#prototype-snapshot-and-maintenance) documents
the runnable entrypoint's selected-card contrast correction and the archived
original entrypoint. The Chinese source and historical study hashes are unchanged.

A clickable Windows desktop workbench prototype based on `doc/PRD_CN.md`.
It does not connect to real Agents. Tasks, events, artifacts, approvals and
connection states in the UI are synthetic demo data.

See [PROTOTYPE_CONTRACT.md](PROTOTYPE_CONTRACT.md) for the file structure, URLs,
ready markers, fixtures, safety boundaries and interaction contract used in
external live research.

## Product Structure

V2 is one continuous workbench, no longer separate Review Queue and Workstream
pages:

```text
Work (persistent navigation)
  ├─ Work list: Needs you / In progress / All
  └─ Selected task: Result / Workstream / Context
       -> Inspect artifacts, diffs, action targets or clarification questions directly
       -> Decide within the current task
       -> Show the result in place and update list counts
       -> Select the next item manually, without module changes or a return-selection modal
```

- A/B/C initially select Needs you and a specific task, without an intermediate
  `Open workspace` button. D opens the complete status board directly; clicking
  a card opens the same task details.
- Lists and global navigation stay stable. Switching tasks preserves each task's
  tab, reading position and unsubmitted drafts within the current session.
- Acceptance leaves the result visible in place. Handled tasks appear in
  Just handled and no longer count as pending.
- Revision requests require specific feedback. An explicitly labeled demo
  button can simulate a returned version; sample text does not automatically
  implement arbitrary feedback.
- Authorization and receipts are separate. Authorizing records only the decision;
  simulated delivery appears only after explicitly generating a simulated receipt.
- `Agents` shows capability boundaries. `Activity` returns to the task owning a
  decision without replaying any action.
- Creating a task produces only a local draft and does not start a real Agent.

## Visual Design

A/B use a restrained warm-white, black/gray and light-border style: serif headings,
icons and action buttons without gradients, flat navigation and task lists.
C uses dark-green navigation, pale gray-green panels and green action buttons
to emphasize control-center sections and status. D uses a pale blue-gray board,
status dots and separate task cards to emphasize parallel work moving between
states. None copies reference-product branding or assets. All four preserve
the V2 state model and local storage without resetting task data.

### A / B / C / D Interface Comparison

The title bar's **Design A / B / C / D** switch changes presentation and browsing,
not the task state model or decision semantics:

| | A (original retained) | B (more compact results view) | C (control center) | D (status board) |
|---|---|---|---|---|
| Navigation | Icons and text | Compact icon rail with hover explanations | Dark horizontal navigation | Compact icon sidebar |
| Work overview | Pending summary and in-progress count | Pending summary and in-progress count | Clickable status cards synchronized with list filters | Three status columns with live card counts |
| Work list | Summaries and Agent shown by default | Titles first; summaries optional | Separate task cards | Needs you / In progress / Handled; drafts in a small toolbar entry |
| Task presentation | Flat split panels, conventional headings | Separate reading panel, serif headings | Cool-green panels, results canvas, segmented tabs | Click a card for details; close to return to the board |
| Action location | Bottom action bar | Right side at 1280px and above | Above the result on desktop; bottom at 720px and below | Bottom of details, preserving acceptance and authorization boundaries |

All four share the same details component and state model. Tasks, tabs, selected
artifact versions and unsubmitted feedback survive instant switching; decisions
made in one design apply in the others. A/B/C list filters survive switching to
D. D displays three work-status columns and retains text search. Local drafts
are available through a separate small entry or global task search. For safety,
recipient, bound version, risk and impact explanations never depend on the
summary toggle.

Open `/?design=a`, `/?design=b`, `/?design=c` or `/?design=d` directly. Clicking
A/B/C/D saves the choice in the local browser's `dayline-design` storage.
B's summary toggle lasts for the current session and does not change task data.
Here A/B/C/D are design comparisons of one workbench, not the earlier names for
the Workstream / Review Queue features. C's status cards change only the existing
list filter; they do not navigate tasks or start an Agent.

#### D Board Interaction

- Opening D directly shows Needs you / In progress / Handled columns, prioritizing
  work requiring attention. Switching from another design retains the current
  task and opens its details.
- Wide screens show the board beside details. At 1100px and below, details replace
  the board area; Back to board or Escape returns. Closing and reopening retains
  the session's tabs, reading positions and drafts.
- New task remains at the upper right. New tasks are still local drafts, without
  starting an Agent, but no longer occupy a separate board column. When drafts
  exist, a compact Drafts count button in the toolbar opens a small list; without
  drafts the entry is hidden. Existing drafts are not deleted.
- Existing states automatically place work cards in columns. Dragging cannot
  bypass acceptance or authorization.
- Revision requests move to In progress; a simulated returned version moves back
  to Needs you; acceptance moves to Handled.
- Authorization is not delivery. Authorized work stays In progress awaiting a
  receipt, moving to Handled only after a simulated receipt is generated.
- Handled includes declined sending, so it does not mean everything was
  delivered; cards retain specific status. Confirmed research scope stays
  In progress.
- Board search filters all three work columns and updates counts. It does not
  close the current task or clear unsubmitted content. The draft list is separate
  from board filters; global Search tasks can still find drafts.

For external research, add `research=1`:

```text
/?design=a&research=1
/?design=b&research=1
/?design=c&research=1
/?design=d&research=1
```

Research mode locks the design specified in the query and hides the in-page
A/B/C/D switch, preventing participants from bypassing the research tool's
handoff. It changes no tasks, content, state model or decisions. The root
`data-prototype-ready="true"` marker confirms that initialization has completed.

## Interface Language

The prototype supports English and Simplified Chinese. First launch defaults
to English; switch through Settings on the left. The choice is saved in browser
storage on the current device.

## Run Locally

```bash
npm install
npm run dev
```

Production build:

```bash
npm run build
```

State regression tests (Node's built-in test runner):

```bash
npm test
```

Browser journey tests (using an installed Microsoft Edge):

```bash
npm run test:ui
```

Browser tests run in isolated contexts on a `127.0.0.1:4174` server without
changing development-preview data. They cover task switching, feedback drafts,
acceptance, rework versions, authorization/receipts, language, persistence,
1440/1024/820/390px layouts, and contrast for main body/action text.

Continuous-workbench journeys run separately in `design-a`, `design-b` and
`design-c`; `design-d` runs board journeys. Additional checks cover shared state
across all four, actual component-size/action-location differences, B's 1280px
sidebar breakpoint, C's status cards, and D's columns/automatic movement,
details opening/closing, keyboard return, search, drafts, both languages,
narrow-screen actions and text contrast.

## Prototype Boundaries

- All external actions are frontend simulations: no messages are sent, files
  modified or real Agents called.
- Approval and successful execution remain separate in the interface.
- Observe, Delegate and Controlled demonstrate differences in connection
  capabilities only.
- Decisions, feedback, versions and new drafts persist across refreshes in this
  browser's `dayline-workbench-v2` local storage, without cross-device sync.
- Document previews, citations and execution records are synthetic examples,
  not real files or security verification.

## License

This prototype source uses the [MIT License](LICENSE). `package.json` remains
`private: true` to prevent accidental npm publication; this does not restrict
use of the repository source under MIT.

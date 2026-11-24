# Dayline Design A: specification and captured screens

## Product concept and implemented scope

Dayline is a work-supervision workspace for an individual using several Agents.
It brings task status, work results, revision history and human decisions into one
place. The product concept is to help people inspect work and understand what
needs attention without reconstructing context across separate conversations.
This is a product hypothesis, not a proven benefit.

The supplied Design A is the compact list-and-reading-panel layout. The workspace
has a left work-item list, a central detail area, and a decision panel on the right
at the captured desktop size. Result, Workstream and Context are views of the
selected work item. Agents and Activity are separate global views.

The materials describe the existing synthetic prototype, not all capabilities in
the broader product requirements. Public Design A corresponds to the prototype's
internal `design=b` route, as in the paired comparison case.

## Evidence and interaction boundaries

- Eleven screenshots were captured from the actual local prototype at 1440 by
  900 pixels, using fresh browser state and English UI. They contain synthetic
  tasks, organizations, artifacts and a Demo User, not real customer data.
- This study receives a written spec and PNG images. It does not open a live
  website for the Persona, execute JavaScript, or connect to a real Agent.
- A constructed state graph lets a Persona choose which supplied state to
  inspect next. Its transitions represent navigation through the captured
  material, not proof of real application execution.
- The screenshots show the initial, unmodified work items. No acceptance,
  authorization, message delivery, revision submission or completed-work
  outcome was captured. A visible control does not establish its outcome.
- Some content extends below the viewport. No additional content is implied by
  a screenshot. The package does not provide free scrolling, editable fields,
  arbitrary new tasks, persistence checks or timing measurements.
- The Activity screenshot is empty because no decisions were made during
  capture. It is not evidence that the implemented prototype lacks history.
- The Agents page explicitly says the configurations are demonstrations and
  not connected. The broader product concept must not override this limitation.
- Filenames and file order identify sources, not a recorded chronological
  journey. Only the navigation statements below support declared transitions.

## Captured states

### review-result: Document result

Image: `screenshots/review-result.png`.
The selected item is "Update project overview and quick start", marked ready
for review. Result is selected. The screen shows earlier feedback, a synthetic
README v3 artifact, and a right-side decision panel. "Request changes" and
"Accept v3" are visible, with a warning that acceptance publishes nothing.
Only the shown portion of the artifact is supplied.

### review-workstream: Document workstream

Image: `screenshots/review-workstream.png`.
The same document task is selected with Workstream open. It shows the recorded
synthetic feedback and revision events rather than the result document.
The task and decision scope remain visible. Saving a new note is not captured.

### review-context: Document context

Image: `screenshots/review-context.png`.
The same document task is selected with Context open. This view presents its
goal, definition of done and reference-material labels. References are synthetic
labels, not access to real files. It offers a route back to the result.

### research-result: Research scope

Image: `screenshots/research-result.png`.
"Research agent desktop products" is selected and needs clarification. Result
presents a scope choice and its stated consequence. Confirming a scope is a
visible possibility, but this package contains no submitted choice or outcome.

### research-workstream: Research workstream

Image: `screenshots/research-workstream.png`.
The research task's Workstream shows its synthetic progress and scope question.
The capture describes what was presented, not verified execution of research.

### research-context: Research context

Image: `screenshots/research-context.png`.
The research task's Context shows its goal, definition of done and reference
labels. It distinguishes human acceptance from external authorization and
describes the intended role of receipts. No actual receipt is supplied.

### message-result: Message authorization

Image: `screenshots/message-result.png`.
"Prepare this week's project update" is selected and needs authorization.
The visible action is `message.publish`, with a synthetic destination,
`weekly-update.md` v2 and a one-time permission boundary. The panel separates
accepted content from permission to send; it says authorization is not a
delivery receipt. Decline and Authorize once are visible. Neither is exercised
by this material-based study.

### message-workstream: Message workstream

Image: `screenshots/message-workstream.png`.
The message task's Workstream presents its content-acceptance and authorization
history as synthetic events. This is not a record of a real message being sent.

### message-context: Message context

Image: `screenshots/message-context.png`.
The message task's Context presents its goal, definition of done and supporting
reference labels. The actual destination and action scope are inspected in the
message-result state, not inferred from a generic status.

### agents: Agent configurations

Image: `screenshots/agents.png`.
The Agents page lists Forge Local, Atlas Research, Courier HTTP and Sentinel.
It labels their modes and says the configurations are not connected. The page
states that it collects no credentials, discovers no other computers and starts
no Agents in this prototype phase.

### activity: Activity overview

Image: `screenshots/activity.png`.
The Activity page describes local decisions, feedback and simulated receipts.
It is currently empty and says decisions will appear here. Opening an entry
would not replay an action, but no populated entry was captured.

## Capture-backed navigation

These are supported navigation relations from the implementation and browser
capture checks. A statement that names a work item and tab can require two
visible control selections. It is a review transition, not a hidden product
action. Each target identifies the captured presentation of that state.

- From review-result, selecting Workstream opens review-workstream.
- From review-workstream, selecting Result opens review-result.
- From review-result, selecting Context opens review-context.
- From review-context, selecting Result opens review-result.
- From review-workstream, selecting Context opens review-context.
- From review-context, selecting Workstream opens review-workstream.
- From research-result, selecting Workstream opens research-workstream.
- From research-workstream, selecting Result opens research-result.
- From research-result, selecting Context opens research-context.
- From research-context, selecting Result opens research-result.
- From research-workstream, selecting Context opens research-context.
- From research-context, selecting Workstream opens research-workstream.
- From message-result, selecting Workstream opens message-workstream.
- From message-workstream, selecting Result opens message-result.
- From message-result, selecting Context opens message-context.
- From message-context, selecting Result opens message-result.
- From message-workstream, selecting Context opens message-context.
- From message-context, selecting Workstream opens message-workstream.
- From review-result, selecting "Research agent desktop products" and then Result opens research-result.
- From research-result, selecting "Update project overview and quick start" and then Result opens review-result.
- From review-result, selecting "Prepare this week's project update" and then Result opens message-result.
- From message-result, selecting "Update project overview and quick start" and then Result opens review-result.
- From review-result, opening Agents from global navigation opens agents.
- From agents, opening Work and selecting the document task's Result tab opens review-result.
- From review-result, opening Activity from global navigation opens activity.
- From activity, opening Work and selecting the document task's Result tab opens review-result.

There are no declared transitions for Accept, Request changes, Confirm scope,
Authorize once, Decline, editable notes, version selection or New task in this
package. These may be visible in the prototype, but their interactive outcomes
are outside this captured-material scope. The spec does not prescribe a Persona
itinerary or require every captured state to be visited.

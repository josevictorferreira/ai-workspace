# Glyph — Feature Product Specification

## Product intent

Glyph is a visual workspace for designing dependable AI workflows.

An AI workflow is often described as a sequence of prompts. That is insufficient. A useful workflow also makes its inputs, decisions, dependencies, timing, tools, and outcomes visible. Glyph gives those things a physical clarity: each step is an object, each connection has meaning, and every run can be understood after it has happened.

The product should feel quiet and direct. The canvas is the place where work is composed; the run history is the place where work is understood. Neither should require the user to infer hidden behaviour.

## Product principles

1. **The workflow is legible at a glance.** A person should be able to understand what enters, what happens, what depends on what, and what leaves the workflow by looking at its canvas.
2. **Progressive disclosure preserves calm.** The canvas exposes structure. Inspectors expose detail only when requested.
3. **Connections are contracts.** A link between two steps explicitly states which output is supplied to which input.
4. **A run is evidence.** Every execution preserves its timing, inputs, outputs, messages, agent session content, and errors.
5. **Manual control remains available.** Scheduled work is useful; an immediate manual run is always possible.
6. **The system prevents ambiguity before execution.** Missing required inputs, incomplete step configuration, invalid links, and invalid schedules are clearly identified before a workflow is activated.

---

## Users and permissions

### Workflow author
Creates, edits, schedules, and manually triggers workflows. The author can inspect any run of a workflow they can access.

### Workflow observer
Can view workflow canvases, configuration, and run history, but cannot change a workflow or start a run.

> The first release may ship with a single authenticated owner. The product language and screen structure should nevertheless distinguish viewing from editing so permissions can be introduced without changing the interaction model.

---

## Core product objects

### Workflow
A named, described automation composed of one or more connected steps. A workflow has a draft or active state and may have a schedule.

**Workflow fields**
- Name — required; concise human-facing label.
- Description — optional; explains purpose, scope, or expected outcome.
- Status — `Draft`, `Active`, `Paused`, or `Needs attention`.
- Schedule — optional periodicity definition.
- Last run — most recent run state and time, when one exists.
- Next run — calculated next scheduled time, when active and scheduled.
- Canvas — the visual arrangement of steps and their connections.

### Step
A single AI operation in a workflow. A step turns defined inputs into a defined output.

**Step fields**
- Name — required; a short action-oriented label, such as “Summarise research”.
- Description — optional clarification of the step’s responsibility.
- Inputs — named values the step accepts.
- Prompt — required instruction given to the agent.
- Additional context — optional supporting material appended or made available to the agent.
- Tools — zero or more permitted agent tools.
- Model configuration — selected model and its relevant settings.
- Expected output — required description of the result the step must produce.
- Output definition — named output exposed for downstream connections.

### Input
A named value required or accepted by a step. It receives its value in one of two ways:

- **Workflow value:** supplied when a workflow is manually run, or defined by its scheduled configuration.
- **Connected value:** supplied from the named output of an upstream step.

An input may be required or optional. A required input must have one unambiguous source before the workflow can be activated or run.

### Connection
A directed visual link from one step output to one input on another step. Connections define execution dependency: the receiving step does not begin until all of its required connected inputs are available.

### Run
One execution of a workflow, initiated manually or by schedule. A run contains ordered step runs, supplied workflow inputs, timestamps, outcomes, and diagnostic information.

**Run states**
- `Queued` — accepted and awaiting background execution.
- `Running` — one or more steps are executing.
- `Succeeded` — all required steps completed successfully.
- `Failed` — a step failed and the workflow could not complete.
- `Cancelled` — stopped before completion, if cancellation is introduced.

### Step run
The immutable record of a step’s behaviour during one workflow run.

**Step run fields**
- Status — `Queued`, `Running`, `Succeeded`, `Failed`, or `Skipped`.
- Start and end timestamps.
- Elapsed time.
- Resolved input values.
- Produced output value.
- Agent messages.
- Agent session content.
- Error details, when unsuccessful.

---

## Information architecture

### Workflows
The landing area is a list of workflows. It gives a person confidence about what exists and what is happening now.

Each workflow row shows:
- Workflow name and description.
- Status.
- Last run result and relative time.
- Next scheduled run, or “No schedule”.
- A concise Run now action for people with edit permission.

The page provides:
- **New workflow** — starts an empty draft.
- **Search** — filters by workflow name and description.
- **Status filtering** — All, Active, Draft, Paused, and Needs attention.

### Workflow editor
The editor is the principal design surface.

- The **canvas** occupies the central area and is used to arrange and connect steps.
- A compact **workflow header** shows the workflow name, status, save state, and primary actions.
- A contextual **inspector** opens when the workflow or a step is selected.
- A **validation summary** appears when there are unresolved configuration problems.

### Workflow detail
A saved workflow can be viewed in two complementary modes:

- **Design** — the canvas and configuration.
- **Runs** — operational history, schedule state, and individual run detail.

The visual arrangement of the canvas is retained between modes. The runs view therefore remains anchored to the workflow the person designed.

---

## User flows

## 1. Create a workflow

**Goal:** Turn an initial idea into a named draft ready for visual composition.

1. The author opens **Workflows**.
2. They select **New workflow**.
3. Glyph creates an untitled draft and opens the workflow editor.
4. The canvas contains an empty-state message: “Add a step to begin.”
5. The workflow inspector is open by default with fields for name and description.
6. The author enters a name. The workflow is saved as a draft.
7. The author may add a description now or later.

**Success state**
- The workflow exists as a draft.
- Its name is visible in the header and workflows list.
- The author is ready to add its first step.

**Validation and recovery**
- A blank name cannot be saved. The name field explains what is needed without obscuring the canvas.
- If the author leaves with unsaved changes, Glyph gives a clear choice to keep editing, discard changes, or save the draft.

---

## 2. Add and configure a step

**Goal:** Define one intelligible unit of AI work.

1. From the empty canvas or canvas toolbar, the author selects **Add step**.
2. A new step appears on the canvas, selected and ready to name.
3. The step inspector opens alongside the canvas.
4. The author provides the step name, prompt, and expected output.
5. The author defines one or more inputs, when the prompt needs external or upstream information.
6. The author optionally adds additional context, chooses available tools, and selects a model and applicable model settings.
7. The author defines the step output name and its expected shape or description.
8. The author saves or moves focus away; Glyph persists the configuration and reflects completion on the step card.

**Step card on the canvas**
- Displays its name.
- Shows a brief prompt or purpose summary.
- Presents inputs on the left edge and output on the right edge.
- Shows a compact configuration state: complete, incomplete, running, succeeded, or failed when appropriate.
- Never attempts to display the entire prompt or output. Detail belongs in the inspector.

**Configuration details**

### Inputs
For each input, the author specifies:
- Name.
- Whether it is required.
- Optional description or example.

The inspector indicates the input’s current source:
- `Not connected`.
- `Workflow value`.
- `Output from [step name]`.

### Prompt and additional context
- The prompt is the primary instruction for the AI.
- Additional context accepts supplementary information that should be available to the agent but is distinct from the instruction itself.
- The editor preserves authored text exactly and makes it easy to read long instructions.

### Tools
- The author may enable only the tools appropriate to the step.
- A step with no enabled tools remains valid.
- Tool names and descriptions explain the capability being granted before it is enabled.

### Model selection
- The model picker presents the models currently available to the workspace.
- The picker identifies the selected provider and model.
- Only model-related settings supported by the selected model are shown.
- If a previously selected model is unavailable, the step is marked `Needs attention`; its prior choice remains visible until the author selects a replacement.

### Expected output
- The expected output explains what a successful response should contain and in what form.
- It is visible to the author during configuration and retained with each run so the resulting output can be judged in context.

**Validation and recovery**
- A step is incomplete when it lacks a name, prompt, expected output, output definition, or required input source.
- Incomplete steps remain on the canvas but are visibly identified. They cannot participate in an active runnable workflow until completed.
- If the author removes configuration used by an existing connection, Glyph warns that the connection will be removed and requires confirmation.

---

## 3. Arrange the canvas

**Goal:** Make the workflow’s logic easy to see without changing its behaviour.

1. The author drags a step card to a new location.
2. The canvas retains its new position.
3. The author can select a card to inspect it, or click empty canvas to return to the workflow inspector.
4. The author can use standard canvas controls to pan and zoom.

**Behaviour**
- Position is presentation, not execution order. Execution order is determined by connections.
- The canvas remains usable for large workflows through panning, zooming, and fit-to-workflow.
- The author may select and delete a step. Glyph identifies the affected outgoing and incoming connections before deletion.

**Deletion flow**
1. The author selects a step and chooses **Delete step**.
2. Glyph states the step name and the number of connections that will be removed.
3. The author confirms deletion.
4. Glyph removes the step and its connections; dependent required inputs become visibly unresolved.

---

## 4. Connect steps

**Goal:** Pass a specific output from one step into a specific input of another, creating a visible dependency.

1. The author begins dragging from the output connector of an upstream step.
2. Glyph highlights compatible input connectors on other steps.
3. The author drops the connection on the intended input.
4. Glyph creates an arrow from the source output to the receiving input.
5. The receiving input now identifies its source in the step inspector.
6. The canvas validates the resulting graph immediately.

**Connection rules**
- A connection must have a source output and destination input.
- A required input may have only one active source.
- A step cannot connect to itself.
- The graph cannot contain a cycle. Glyph prevents the final connection that would create one and explains why.
- Connections may only join compatible values when output and input types or shapes are defined. If type information is not yet supported, Glyph treats compatibility as author-declared and makes the mapping explicit.

**Reconnect or remove**
- Selecting a connection reveals its source and destination.
- The author may delete the connection.
- To replace an input’s existing source, the author makes a new connection; Glyph asks whether to replace the current source.

**Success state**
- The dependency is visible on the canvas.
- The receiving step waits for its upstream dependency during a run.
- The connection is recorded in the workflow design.

---

## 5. Resolve workflow inputs

**Goal:** Make every required value available at execution time.

1. Glyph identifies all required step inputs that have no upstream connection.
2. The author chooses each input’s source as a workflow-level value.
3. Glyph presents a workflow input definition with name, description, and required status.
4. The workflow inspector shows the resulting workflow inputs as a concise list.

When multiple step inputs refer to the same workflow value, the author deliberately maps them to it. Glyph does not silently merge values based on matching names.

**Success state**
- Every required input is either connected from an upstream output or mapped to a required workflow value.
- The workflow can be manually run once all other validation requirements are met.

---

## 6. Finish and activate a workflow

**Goal:** Move a draft from design into dependable operation.

1. The author selects **Review workflow** or **Activate**.
2. Glyph checks the workflow for readiness:
   - A workflow name exists.
   - At least one step exists.
   - Every step has required configuration.
   - Every required input has a source.
   - The connection graph is valid.
   - The schedule, if present, is valid.
3. Glyph presents a review summary with the workflow’s name, description, step count, unresolved items, and schedule state.
4. If there are issues, the author selects an issue to return directly to the relevant step or workflow field.
5. When no blocking issues remain, the author selects **Activate workflow**.
6. Glyph marks the workflow Active and calculates its next run when scheduled.

**Status semantics**
- **Draft:** Not yet activated. It cannot be scheduled, though it may be tested manually if fully configured.
- **Active:** Ready to run manually and, when scheduled, automatically.
- **Paused:** Preserves configuration and run history but does not begin scheduled runs.
- **Needs attention:** Active intent is preserved, but configuration or dependency changes prevent reliable scheduled execution. Glyph explains the exact issue.

---

## 7. Define periodicity

**Goal:** Establish when an active workflow runs without concealing the next execution.

1. In the workflow inspector, the author opens **Schedule**.
2. They select either **No schedule** or **Run periodically**.
3. For periodic execution, the author defines the recurrence using the supported scheduling interface.
4. Glyph shows a human-readable schedule summary and the calculated next run time.
5. The author saves the schedule.
6. For an active workflow, Glyph prepares future scheduled execution.

**Schedule controls**
- Edit schedule.
- Pause schedule without changing its recurrence.
- Resume schedule.
- Remove schedule.

**Validation and recovery**
- An invalid recurrence cannot be saved.
- A paused workflow does not report a next run; it reports that its schedule is paused.
- If the workflow later becomes incomplete, scheduled execution stops and the workflow enters Needs attention rather than running with missing information.

---

## 8. Manually trigger a workflow

**Goal:** Run a workflow now for testing or immediate work.

1. The author selects **Run now** from the workflow list, workflow header, or runs view.
2. Glyph validates the current workflow configuration.
3. If workflow-level values are required, Glyph opens a run sheet listing each value, its description, and whether it is required.
4. The author provides values and selects **Start run**.
5. Glyph creates a run in `Queued` state and confirms that it has been accepted.
6. The runs view updates to show the new run. Its state progresses as background processing begins.

**Run now without a schedule**
- A workflow does not need a schedule to be run manually.

**Manual run validation**
- Missing required run values prevent starting the run and are identified beside their fields.
- A draft that is completely configured may be run as a test. Glyph labels the run as originating from a draft; it does not silently activate the workflow.
- A workflow with unresolved validation errors cannot run. Glyph routes the author to the relevant design issue.

---

## 9. Execute a workflow

**Goal:** Produce a traceable result from the canvas design.

This is system behaviour made visible to the user.

1. Glyph accepts a manual or scheduled trigger and creates a workflow run.
2. Root steps whose required inputs are available become eligible to execute.
3. Glyph starts eligible steps.
4. Each step runs using its resolved inputs, prompt, additional context, permitted tools, selected model configuration, and expected output.
5. When a step succeeds, Glyph stores its output and makes it available to connected downstream inputs.
6. Any downstream step with all required inputs available becomes eligible to execute.
7. Independent branches may execute concurrently.
8. When all required steps succeed, the workflow run becomes `Succeeded`.

**Failure behaviour**
1. If a step fails, its step run records the error and available session content.
2. The workflow run becomes `Failed` when it cannot proceed to a required outcome.
3. Steps dependent on the failed output are marked `Skipped`, with the reason that their dependency did not complete.
4. Independent steps may complete if already eligible and running; Glyph reports their actual outcome rather than implying the entire run stopped instantaneously.

The initial product does not imply retry, replay, resume, or partial rerun behaviour. These are valuable future capabilities but must be explicitly designed before being exposed.

---

## 10. View workflow runs

**Goal:** Understand what has happened, what is happening, and what will happen next.

1. The observer or author opens a workflow and selects **Runs**.
2. Glyph presents the workflow’s current operational summary:
   - Current workflow status.
   - Last run result and completion time.
   - Next scheduled run, or the reason one is absent.
   - A Run now action for authors.
3. Below the summary, Glyph lists runs newest first.
4. Each run row shows:
   - Status.
   - Start time or queued time.
   - Trigger source: Manual or Scheduled.
   - Elapsed time when completed.
   - A succinct error indicator when failed.
5. The user selects a run to inspect it.

**Empty state**
- A workflow with no runs states that it has not run yet and offers Run now to an author.

**Live updates**
- While a run is queued or running, its status and elapsed time update without requiring page refresh.
- The interface must not reorder the run the user is actively inspecting in a disruptive way.

---

## 11. Inspect a run

**Goal:** Reconstruct the execution without leaving the product or guessing what the agent received.

1. The user selects a run from the runs list.
2. Glyph opens the run detail view.
3. The run header shows status, trigger source, queued/start/end times, elapsed time, and the workflow version or configuration snapshot used.
4. Glyph displays the workflow structure with execution state applied to each step.
5. The user selects a step to view its step-run detail.

**Run visualisation**
- Uses the familiar workflow canvas structure.
- Marks each step with its run state.
- Shows timing and failure state without replacing the underlying design structure.
- Makes skipped downstream work distinct from a failed step.

**Step-run detail**
The detail panel contains, in this order:
1. Status and start/end timestamps.
2. Elapsed time.
3. Resolved inputs, including the value and its source.
4. Prompt and additional context used for this run.
5. Model and enabled tools used.
6. Expected output.
7. Actual output, when produced.
8. Agent messages.
9. Agent session content.
10. Error details, when present.

Long values, prompts, outputs, and sessions should be readable, selectable, and copyable. Collapsed sections preserve scanability while allowing complete inspection.

---

## 12. Diagnose a failed run

**Goal:** Move from an observed failure to a specific, intelligible cause.

1. The user opens a failed run.
2. Glyph identifies the first failed step in the run visualisation and run summary.
3. The user selects that step.
4. Glyph shows the error, agent messages, session content, resolved inputs, and timing.
5. The user can return to the workflow’s Design mode to inspect or change the corresponding step configuration.

**Diagnostic language**
- Explain the failure at the level of the event: “The Research step could not complete because the selected model is unavailable.”
- Preserve the underlying technical message in the detail panel.
- Do not characterize a skipped step as failed. State that it did not run because an upstream dependency failed.

---

## 13. Edit an existing workflow

**Goal:** Improve a workflow while preserving confidence in its historical record.

1. The author opens a workflow in Design mode.
2. They modify workflow configuration, steps, inputs, connections, or schedule.
3. Glyph validates the edited design immediately.
4. The author saves the changes.
5. If the changes make an Active workflow invalid, Glyph changes its operational state to Needs attention and stops its scheduled execution until corrected.
6. Existing runs remain unchanged and inspectable with the configuration snapshot that produced them.

**Editing while runs exist**
- Changes affect future runs only.
- A run in progress continues against the configuration captured at its creation.
- Run history always identifies the version or configuration snapshot used, so later edits cannot rewrite the meaning of past evidence.

---

## 14. Pause, resume, and retire a workflow

**Pause**
1. The author selects **Pause**.
2. Glyph explains that future scheduled runs will stop; run history and design are retained.
3. The author confirms.
4. The workflow becomes Paused. Manual execution remains available if the workflow is valid.

**Resume**
1. The author selects **Resume**.
2. Glyph validates the workflow.
3. If valid, the workflow becomes Active and Glyph calculates the next scheduled run.
4. If invalid, Glyph marks it Needs attention and lists the issues to resolve.

**Retire or delete**
Deletion is a consequential action. Glyph must avoid silently removing operational evidence. If deletion is provided, it should require confirmation, explain the effect on run history, and distinguish removing a draft from retiring an operational workflow.

---

## States, feedback, and language

### Save state
The editor should make persistence calm and unambiguous:
- `Saving…`
- `Saved`
- `Unable to save` with a retry action and a clear explanation

### Time
- Relative time is useful for recency: “Ran 12 minutes ago.”
- Exact timestamps are necessary in run detail.
- Elapsed time is shown while running and after completion.
- Next run is stated in human language and supported by an exact timestamp on inspection.

### Empty states
Empty states are invitations, not dead ends:
- No workflows: explain the value of a first workflow and offer New workflow.
- Empty canvas: offer Add step.
- No runs: explain that no execution has occurred and offer Run now when permitted.
- No schedule: explain that the workflow runs only when manually triggered.

### Confirmation
Confirm destructive or consequential actions—deleting a step, removing a connection that invalidates an input, pausing scheduled work, and retiring a workflow. Do not ask for confirmation when the action is easy to reverse and causes no operational loss.

---

## Acceptance criteria

The feature is complete when a workflow author can:

1. Create a named workflow draft from an empty state.
2. Add any practical number of AI steps to a visual canvas.
3. Configure each step’s inputs, prompt, additional context, tools, model configuration, expected output, and output definition.
4. Connect a named step output to a named input of another step and see the dependency on the canvas.
5. Be prevented from creating invalid or cyclic dependency graphs.
6. Define unresolved required values as workflow-level run inputs.
7. Validate, activate, pause, resume, and schedule a workflow.
8. See when an active scheduled workflow will run next.
9. Trigger a valid workflow manually, supplying required run inputs.
10. Observe queued and running work update in the runs view.
11. Inspect every run’s status, trigger source, timestamps, elapsed time, and step outcomes.
12. Inspect every step run’s resolved inputs, output, messages, agent session content, and errors.
13. Understand precisely why a run or downstream step did not complete.
14. Edit a workflow without altering the evidence captured by its prior runs.

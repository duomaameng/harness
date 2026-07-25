# SPEC-webui.md

# WebUI Developer Workbench Specification

## 1. Purpose

This document defines the WebUI for the Context-Aware Coding Agent Harness. It is a focused supplement to `SPEC.md` and does not replace the existing system specification.

The WebUI is a developer workbench for observing, approving, demonstrating, and exporting evidence from harness runs. It does not implement the agent loop. Agent execution remains owned by `AgentRunner`; orchestration remains owned by `CoreService`; safety remains owned by Guardrail and approval records.

The WebUI must make the harness mechanisms visible enough for both real development use and AI4SE course demonstration.

## 2. Design Position

The WebUI uses a developer workbench model with a mixed dashboard:

- It is the user-facing frontend for the backend harness, not the harness itself.
- It organizes tasks by repository so users choose a work context before creating or continuing work.
- It supports task creation and run inspection.
- It provides a deterministic MockLLM demo run for course demonstration.
- It displays recent runs and mechanism evidence.
- It supports human approval decisions for pending approval requests.
- It exports redacted reports.
- It displays credential configuration status without accepting or revealing secrets.

The WebUI must not become a second agent framework. It must call `CoreService` or FastAPI endpoints and must not directly execute tools, parse LLM actions, bypass guardrails, or mutate storage outside service boundaries.

## 3. Users

- Developers who want to inspect why a harness run selected context, executed actions, stopped, or asked for approval.
- Safety-conscious users who need a clear approval surface before risky actions execute.
- AI4SE course reviewers who need visible evidence for context selection, guardrails, feedback-driven repair, memory, reports, and credential safety.

## 4. Scope

### 4.1 In Scope

- Dashboard page.
- Run Detail page.
- Repository-scoped task navigation in the left sidebar.
- Fixed deterministic MockLLM demo run entry.
- Task creation through the WebUI.
- Recent run summary.
- Mechanism evidence summary.
- Run timeline.
- Context package viewer.
- Pending approval approve/reject forms.
- Redacted Markdown and JSON report export.
- Credential status display.
- Error and empty states.
- Open Design assisted interface design during the later implementation phase.

### 4.2 Out of Scope

- Starting real LLM runs from the WebUI.
- Entering, updating, clearing, or viewing API keys in the WebUI.
- Editing LLM actions before approval.
- Direct shell execution from the WebUI.
- Implementing agent loop logic in frontend or template code.
- Exposing model, subagent, prompt-template, tool, sandbox, MCP, or hook configuration as user-facing task controls.
- Reading raw unredacted JSONL logs as the primary UI data source.
- A large admin console with independent Memory, Settings, or Reports modules.

## 5. Relationship To Existing Harness

The WebUI depends on the existing harness architecture:

- `CoreService` is the WebUI boundary for creating tasks, starting the fixed MockLLM demo, reading status, recording approvals, and exporting reports.
- `AgentRunner` owns the run loop.
- `HarnessStorage` owns persisted tasks, runs, context packages, actions, tool results, feedback, approval requests, memory, and audit events.
- `Guardrail` owns safety classification.
- `ToolDispatcher` owns controlled tool execution.
- `FeedbackEngine` owns validation feedback and repeated-failure decisions.
- `ReportExporter` owns Markdown and JSON report redaction.
- `CredentialService` owns credential status.

The WebUI may display data from these modules only through service/API abstractions.

## 6. Page Information Architecture

### 6.1 Dashboard

The Dashboard is the first screen and acts as both a workbench entry point and course demonstration surface.

It contains:

- Header: project name, current harness/service status, and credential status.
- Repository/task sidebar: groups recent tasks under their repository, marks the current repository, provides an add-repository entry, and provides per-repository task creation.
- Task creation panel: creates a task record in the current repository context but does not start a real LLM run.
- Mock demo panel: starts or opens the fixed deterministic MockLLM demo run.
- Recent runs list: shows run status, task title, round, timestamps, pending approval flag, and report availability.
- Mechanism evidence summary: shows whether recent or selected runs contain context packages, actions, guardrail events, feedback events, memory evidence, and reports.
- Security notice: explains credential status and `.env` fallback risk without displaying secrets.

### 6.2 Run Detail

Run Detail presents one run as an ordered evidence chain.

The default Run Detail example and primary happy path should show a completed run. Pending approval is a conditional state, not the default detail-page state.

It contains:

- Run overview: task title, task description, run status, current round, stop reason, timestamps, and report export actions.
- Timeline: ordered events for task creation, context selection, action receipt, guardrail decision, approval decision, tool completion, feedback generation, and run finish.
- Context package viewer: selected context items with kind, source path, symbol, summary, selection reason, and metadata such as score or source.
- Approval panel: visible only when pending approval exists, with approve/reject actions; completed runs show approval decisions as read-only timeline/status evidence.
- Report export panel: Markdown and JSON export actions using redacted report output.

## 7. Primary User Flows

### 7.1 Course Demonstration Flow

1. User opens Dashboard.
2. User clicks the fixed MockLLM demo action.
3. WebUI starts or opens a deterministic demo run.
4. User lands on Run Detail.
5. User follows the timeline to explain context selection, structured action handling, guardrail interception, feedback-driven repair, and report export.

### 7.2 Real Run Observation Flow

1. A real run is created or started through CLI/API.
2. User opens Dashboard.
3. User selects the recent run.
4. Run Detail displays status, timeline, context, feedback, approvals, and report availability.

### 7.3 Human Approval Flow

1. A run enters `waiting_approval`.
2. Dashboard marks the run as pending approval.
3. User opens Run Detail.
4. Approval panel displays action, risk level, reason, and current status.
5. User approves or rejects.
6. WebUI calls the service/API to record the decision.
7. Storage and audit records are updated.

### 7.4 Report Export Flow

1. User opens Run Detail for a completed, failed, or stopped run.
2. User exports Markdown or JSON.
3. Exported content is generated through `ReportExporter`.
4. Export contains only redacted, bounded evidence.

## 8. Components

### 8.1 TaskCreatePanel

Inputs:

- task title;
- task description.

Context:

- The repository is inherited from the currently selected repository in the sidebar.
- The panel may display the current repository name and path as read-only context.
- The panel must not require users to re-enter or select a repository after they are already inside a repository context.

Behavior:

- Creates a task record.
- Does not start a real LLM run.
- Shows a link to the created task or run if available.

### 8.1a RepositorySidebar

Displays:

- registered repositories;
- repository display name;
- repository path or compact identifier;
- recent tasks grouped under each repository;
- active repository and active task state;
- add-repository action;
- per-repository new-task action.

Behavior:

- Selecting a repository sets the current task creation context.
- Selecting a task opens or focuses its latest run.
- Adding a repository records a local repository context for future tasks.

Prohibited behavior:

- It must not expose agent model, subagent, prompt-template, tool, sandbox, MCP, or hook configuration.
- It must not turn repository navigation into a broad project-management or admin console.

### 8.2 MockDemoPanel

Inputs:

- none from the user.

Behavior:

- Starts or opens one fixed deterministic MockLLM demo run.
- The run must not require network access or real credentials.
- The run must be repeatable.

Expected evidence:

- context package construction;
- dangerous action guardrail handling;
- feedback or repair evidence;
- final report availability.

### 8.3 RunSummaryList

Displays:

- task title;
- run status;
- current round;
- timestamps;
- pending approval marker;
- report availability.

Behavior:

- Opens Run Detail for the selected run.

### 8.4 MechanismEvidenceSummary

Displays mechanism evidence counts or presence indicators:

- context items;
- actions;
- guardrail decisions;
- tool results;
- feedback entries;
- approval decisions;
- report availability;
- memory evidence when available.

Purpose:

- Make course mechanism coverage visible from the Dashboard.

### 8.5 RunTimeline

Displays ordered run events:

- `task.created`;
- `context.selected`;
- `action.received`;
- `schema.invalid`;
- `guardrail.blocked`;
- `approval.requested`;
- `approval.decided`;
- `tool.completed`;
- `feedback.generated`;
- `run.finished`.

Each event should show:

- timestamp;
- event type;
- short status label;
- summary;
- relevant redacted excerpt;
- links or anchors to related context, action, feedback, or report sections.

### 8.6 ContextPackageViewer

Displays:

- context item kind;
- source path;
- symbol when present;
- summary;
- selection reason;
- score/source metadata when available.

The viewer must make it clear why each context item was selected.

### 8.7 ApprovalPanel

Displays:

- action type;
- action arguments summary;
- risk level;
- guardrail reason;
- approval status.

Behavior:

- Allows approve or reject for pending approvals.
- Records the decision through service/API.

Prohibited behavior:

- editing action content;
- executing the action directly;
- bypassing guardrails;
- repeated decision submission after approval status is no longer pending.

### 8.8 ReportExportPanel

Displays:

- report availability;
- Markdown export action;
- JSON export action;
- export failure state.

Constraints:

- Output must come from `ReportExporter`.
- Output must be redacted.
- Secret-like strings must not appear.

### 8.9 CredentialStatusBadge

Displays:

- `configured`;
- `missing`;
- `env_fallback`;
- optional short risk notice.

Constraints:

- No API key input.
- No API key display.
- No credential clear operation.
- No raw environment variable value display.

## 9. Data Contracts

The WebUI requires service/API access to these data shapes:

- task summary;
- task run summary;
- run detail;
- context package and context item references;
- action trace;
- tool result excerpts;
- feedback entries;
- approval requests;
- audit timeline events;
- report export payloads;
- credential status.

All displayed excerpts must be pre-redacted and size-limited by backend logic. The UI may mark an excerpt as truncated, but must not offer an unredacted or unlimited raw view.

## 10. Security Requirements

- WebUI must never display API keys, bearer tokens, passwords, private keys, or secret-like values.
- WebUI must never accept API key entry.
- WebUI must never store secrets in browser state, templates, query strings, local storage, or logs.
- Credential status must be status-only.
- `.env` fallback may be shown as a risk state, not as a value.
- Approve/reject actions must operate only on existing pending approval requests.
- Approval decisions must be persisted and auditable.
- WebUI must not directly execute shell commands or tools.
- MockLLM demo must not require real LLM credentials.
- Error messages must not expose tracebacks containing sensitive paths or values.

## 11. Error And Empty States

Dashboard:

- If service/API is unavailable, show a service unavailable state.
- If no runs exist, show an empty state with the MockLLM demo action.
- If credential status cannot be read, show unknown status without exposing details.

Run Detail:

- If a run is missing, show a not-found state.
- If a run failed, show stop reason, last feedback, and report export if available.
- If report export fails, show a recoverable error.
- If approval has already been decided, disable approve/reject and show final status.
- If output is truncated, label it as truncated.

## 12. Visual And Interaction Design Direction

The WebUI should use a balanced style:

- Dashboard is demonstration-friendly, with clear section hierarchy and visible mechanism evidence.
- Run Detail is denser and more like an engineering console.
- Status labels should be compact and scannable.
- Timeline events should be easy to explain during a presentation.
- Approval controls should be visually distinct from passive status views.
- Credential warnings should be visible but not alarming when configuration is safe.

The later implementation phase should use Open Design to assist with interface design. This SPEC defines information architecture, component requirements, state behavior, and acceptance criteria; it does not generate the visual design artifact itself.

## 13. Acceptance Criteria

- Opening the WebUI shows the Dashboard.
- Dashboard displays harness/service status and credential status.
- Dashboard left sidebar groups tasks by repository and includes an add-repository action.
- Creating a task from inside a repository context does not show a repository input; the task inherits the current repository.
- Dashboard provides a fixed MockLLM demo entry.
- The fixed MockLLM demo can create or open a deterministic run without real credentials or network access.
- Dashboard displays recent runs with status and pending approval markers.
- Dashboard displays mechanism evidence summary.
- The default Run Detail presentation supports completed runs without showing approve/reject controls.
- Run Detail displays run overview and stop reason when present.
- Run Detail displays a timeline containing context, action, guardrail, tool, feedback, approval, and finish events when those events exist.
- ContextPackageViewer displays selected context and selection reasons.
- Pending approval can be approved or rejected from Run Detail only when a pending approval exists.
- Approval decisions are persisted and auditable.
- Reports can be exported as Markdown and JSON.
- Exported report content is redacted.
- API keys and secret-like values do not appear anywhere in WebUI-rendered content.
- WebUI does not implement agent loop logic.
- WebUI does not start real LLM runs.
- WebUI does not accept, update, clear, or display API keys.
- WebUI design notes identify Open Design as the later UI design assistance path.

## 14. Risks And Mitigations

### 14.1 WebUI Scope Growth

Risk: The workbench grows into a large admin product and distracts from the harness core.

Mitigation: Use only Dashboard and Run Detail pages for the first implementation. Keep Memory, Reports, Settings, and Approvals embedded in run context rather than separate modules.

### 14.2 Real LLM Safety Complexity

Risk: Starting real LLM runs from the WebUI adds provider, credential, long-running task, and recovery complexity.

Mitigation: WebUI starts only the fixed MockLLM demo run. Real LLM runs are observed through WebUI but started through CLI/API.

### 14.3 Secret Leakage

Risk: Stored tool output or reports may contain credentials.

Mitigation: Display only redacted backend fields and redacted report exports. Credential status is status-only.

### 14.4 Weak Course Demonstration

Risk: A generic dashboard may not clearly demonstrate the harness contribution.

Mitigation: Include a fixed MockLLM demo and mechanism evidence summary. Run Detail timeline must expose context, guardrail, feedback, and report events.

## 15. Course Requirement Mapping

- WebUI access: Dashboard and Run Detail provide the required accessible WebUI surface.
- Superpowers process: this SPEC was produced through brainstorming and confirmed section by section before implementation planning.
- UI design requirement: later implementation should use Open Design assistance and document the selected design system and skill usage.
- Harness mechanism evidence: the MockLLM demo and timeline expose context selection, dangerous action governance, feedback-driven repair, and report export.
- Credential security: WebUI never accepts or displays secrets and shows credential status only.
- Distribution readiness: WebUI must be runnable through the same local or Docker distribution path as the CLI/API.

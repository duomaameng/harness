# Open Design Brief: Harness WebUI Developer Workbench

## 1. Goal

Design a WebUI for the Context-Aware Coding Agent Harness. The interface should feel like a focused developer workbench: clear, trustworthy, technical, and useful for both day-to-day inspection and AI4SE course demonstration.

The WebUI is not a marketing page and not a generic landing page. The first screen must be the actual product dashboard.

## 2. Product Context

The harness is a local coding-agent control system. It receives a repository task, builds explicit context, asks an LLM for structured actions, checks each action with guardrails, executes approved tools, converts validation failures into feedback, and records audit/report evidence.

The WebUI does not implement the agent loop. It visualizes and controls selected service operations:

- organize user-visible tasks by repository;
- create task records;
- run one fixed deterministic MockLLM demo;
- inspect recent runs;
- inspect one run in detail;
- approve or reject pending approval requests;
- export redacted reports;
- display credential status without showing secrets.

## 3. Target Users

- A developer inspecting why a harness run selected files, executed actions, stopped, or asked for approval.
- A safety-conscious user deciding whether to approve a risky action.
- A course reviewer watching a deterministic demonstration of context selection, guardrails, feedback, and reports.

## 4. Design Direction

Use a balanced style:

- Dashboard: slightly demonstration-friendly, clear enough for a course reviewer to understand quickly.
- Run Detail: denser engineering-console style for serious inspection.
- Overall tone: precise, calm, technical, and trustworthy.

Avoid:

- marketing hero sections;
- large decorative illustrations;
- playful consumer-app styling;
- oversized cards everywhere;
- nested cards;
- bright one-note palettes;
- purple/blue gradient-heavy AI styling;
- secret-looking fake keys or real key examples.

## 5. Information Architecture

The first implementation has only two page types:

1. Dashboard
2. Run Detail

The Dashboard uses a repository-scoped workbench structure. The left sidebar groups tasks under repositories, exposes an add-repository action, and lets users create or continue tasks inside the selected repository. The task creation card should not ask for a repository when a repository is already selected; it may show the current repository as read-only context.

Do not design separate full pages for Memory, Reports, Settings, or Approvals. Those capabilities should appear inside Dashboard or Run Detail.

## 6. Dashboard Requirements

The Dashboard is the first screen. It should communicate: "Choose a repository, create or continue a task, and inspect what the backend harness did."

Required sections:

### 6.1 Header

Show:

- product name: "Context-Aware Harness";
- service status: Ready / Unavailable / Unknown;
- credential status: Configured / Missing / Env fallback;
- compact navigation or breadcrumb if needed.

Credential status must never show an API key or any secret value.

### 6.2 Task Creation

A compact form for:

- task title;
- task description;
- read-only current repository indicator.

The form creates a task record. It does not start a real LLM run.

Do not include a repository input field in the task creation card when the user is already inside a repository context.

### 6.3 MockLLM Demo

A prominent but not flashy action:

- label: "Run MockLLM Demo";
- supporting text: "Deterministic local demo. No real API key required.";

This action starts or opens a fixed deterministic demo run.

### 6.4 Recent Runs

Show a scannable list or table with:

- task title;
- run status;
- current round;
- started/finished time;
- pending approval marker;
- report availability;
- action to open Run Detail.

### 6.5 Mechanism Evidence Summary

Show compact evidence indicators:

- Context;
- Actions;
- Guardrails;
- Feedback;
- Approvals;
- Report;
- Memory, if available.

These can be small metric tiles, status chips, or a concise checklist. The goal is to show course evidence at a glance.

### 6.6 Security Notice

A quiet notice explaining credential status and `.env` fallback risk. It must not dominate the page unless the status is unsafe or missing.

## 7. Run Detail Requirements

Run Detail tells the story of one harness run. The main layout should make the run easy to explain in order.

The default Run Detail mockup should show a completed run: final status, complete timeline, validation or feedback result, context explanation, file/action evidence, and report export. Waiting-for-approval is a secondary conditional state.

Required sections:

### 7.1 Run Overview

Show:

- task title;
- task description;
- run status;
- current round;
- stop reason, if present;
- timestamps;
- report export actions.

### 7.2 Timeline

The timeline is the central element.

Show ordered events such as:

- task created;
- context selected;
- action received;
- schema invalid;
- guardrail blocked;
- approval requested;
- approval decided;
- tool completed;
- feedback generated;
- run finished.

Each timeline item should have:

- timestamp;
- event type label;
- status/risk badge;
- short summary;
- redacted excerpt when useful;
- link or anchor to deeper details.

The timeline should make it obvious that the harness, not the LLM, controls action validation, guardrails, tools, feedback, and stop conditions.

### 7.3 Context Package

Display selected context items with:

- kind;
- source path;
- symbol, if present;
- summary;
- selection reason;
- score/source metadata when available.

This section must answer: "Why did the harness include this context?"

### 7.4 Approval Panel

When a pending approval exists, show:

- action type;
- summarized action arguments;
- risk level;
- guardrail reason;
- approve button;
- reject button.

Do not provide action editing. Do not provide direct shell execution.

If approval was already decided, buttons should be disabled and final status should be visible. If the run is completed and no approval is pending, do not show approve/reject controls; show approval history as read-only evidence in the timeline or status area.

### 7.5 Report Export

Show:

- Markdown export;
- JSON export;
- report unavailable or export error state.

All report output must be redacted by backend logic.

## 8. Component Guidance

Use these component patterns:

- repository/task sidebar for work context;
- status badges for run states;
- risk badges for guardrail severity;
- timeline for run events;
- dense table or list for recent runs;
- compact metric/status tiles for mechanism evidence;
- form controls for task creation;
- clear primary action for MockLLM demo;
- destructive-looking but controlled styling for reject;
- calm confirmation styling for approve;
- warning style for env fallback credential status.

Prefer common icons where useful:

- play icon for MockLLM demo;
- shield for guardrails;
- check/cross for approval decisions;
- file/text icon for reports;
- clock or activity icon for run timeline;
- key or lock icon for credential status.

## 9. States To Represent

Run statuses:

- pending;
- running;
- waiting_approval;
- succeeded;
- failed;
- stopped.

Credential statuses:

- configured;
- missing;
- env_fallback;
- unknown.

Event states:

- success;
- blocked;
- pending;
- rejected;
- warning;
- error;
- truncated.

## 10. Safety And Privacy Constraints

The design must not include:

- visible API keys;
- fake examples that look like real API keys;
- raw unredacted logs;
- controls for entering API keys;
- controls for editing LLM actions;
- controls for launching real LLM runs;
- controls for direct shell execution.

If a command output or report excerpt is shown, mark it as redacted/truncated when applicable.

## 11. Visual Style Constraints

Use a restrained technical palette. Suggested direction:

- neutral background;
- high-contrast text;
- one primary accent for actions;
- separate semantic colors for success, warning, danger, and info;
- avoid dominant purple or blue-purple gradients;
- avoid purely decorative background blobs or orbs.

Layout:

- no landing-page hero;
- no nested cards;
- no oversized ornamental cards;
- keep repeated items compact;
- use stable dimensions for badges, rows, and timeline items;
- make text fit on desktop and mobile.

## 12. Responsive Behavior

Desktop:

- Dashboard can use a two-column or three-zone layout.
- Recent runs and mechanism evidence should be visible without excessive scrolling.
- Run Detail can use a main timeline column plus side panels.

Mobile:

- Stack sections vertically.
- Keep task creation, MockLLM demo, and recent runs near the top.
- Timeline items should remain readable and not overlap.
- Approval buttons should be easy to tap and clearly separated.

## 13. Desired Output From Open Design

Create an editable design for:

1. Dashboard screen.
2. Run Detail screen with representative timeline events.

Include realistic but safe sample content:

- task title: "Add calculator edge-case tests";
- run status: "waiting_approval" or "succeeded";
- context item paths like `src/calculator.py` and `tests/test_calculator.py`;
- redacted excerpt labels such as `[REDACTED]` or "output truncated";
- no real secrets and no fake API-key-shaped strings.

The design should be ready to guide a later FastAPI-rendered WebUI implementation.

# SPEC.md

# Context-Aware Coding Agent Harness

## 1. Problem Statement

General-purpose LLMs can produce useful code, but they often lack a stable engineering layer when working inside an existing repository. They may choose the wrong files, ignore project conventions, forget prior decisions, retry after failures without a clear signal, or request unsafe actions. Existing coding agents usually hide these decisions inside a black box, making it hard for a user or reviewer to understand why a context was selected, why an action was executed, and why a later repair attempt changed direction.

This project builds a medium-scale, context-aware Coding Agent Harness for single-repository feature development. The harness accepts a user feature request, profiles the task, retrieves relevant context from code structure, project conventions, and decision memory, then drives an LLM through a strict structured action protocol. The harness, not the LLM, controls the task lifecycle, validates actions, enforces guardrails, dispatches tools, runs objective verification commands, and feeds structured failures back into the next repair round.

The primary contribution is the context mechanism: the system makes repository context explicit, inspectable, persistent, and testable. Self-repair is a secondary capability built on top of objective validation feedback.

## 2. Target Users

- Independent developers or students who want an LLM to help implement verifiable feature changes while still understanding what context and actions were used.
- Engineers maintaining existing repositories who need a controlled agent that respects project conventions, repository boundaries, and safety rules.
- AI4SE course reviewers who need evidence that the harness mechanisms are implemented as deterministic code and can be tested with a mock LLM.

## 3. Scope

The harness supports single-repository feature development tasks. A task may touch related modules and may include medium-sized local refactoring such as extracting functions, adjusting module boundaries, splitting oversized files, or migrating a local interface. Every task must be verifiable through tests, lint, type checks, build commands, or a clear combination of those signals.

The harness does not support cross-repository development, external service deployment, large architecture rewrites, or a large multi-agent orchestration platform. The first version runs one main agent loop, while keeping module boundaries clear enough for future extension.

## 4. User Stories

1. As a developer, I want to submit a single-repository feature request and have the harness identify the task type, likely modules, and validation strategy, so the agent does not begin from an empty context.

2. As a developer, I want to inspect the context package before and during execution, so I can see which files, project conventions, and historical decisions were selected and why.

3. As a developer, I want the LLM to operate only through structured actions, so file changes, shell commands, memory writes, and final reports are validated, audited, and testable.

4. As a developer, I want test, lint, typecheck, build, schema validation, and guardrail failures to be converted into structured feedback, so the agent can perform bounded self-repair instead of blindly retrying.

5. As a safety-conscious user, I want dangerous actions to be intercepted before execution, so file deletion, out-of-repository access, suspicious shell commands, and sensitive file access require denial or approval at the harness layer.

6. As a course reviewer, I want the core mechanisms to run with MockLLM, so I can verify context retrieval, action parsing, tool dispatch, guardrails, feedback, and repair loops without a real LLM or network access.

## 5. Functional Specification

### 5.1 CLI, WebUI, and API

The interaction layer consists of a CLI, a WebUI, and API endpoints. These entry points submit tasks, query status, view context packages, inspect action traces, process approval requests, and export reports. They do not implement agent logic directly.

Expected CLI commands include:

- `init`: initialize harness metadata for a repository.
- `run`: submit and run a feature task.
- `status`: inspect task and run state.
- `auth set/status/clear`: manage LLM provider credentials.
- `memory`: inspect or manage long-term memory.
- `export`: export a redacted run report.

The WebUI focuses on observability and approval. It shows the current task state, selected context, action history, validation feedback, pending approvals, and final report.

### 5.2 Core Service

Core Service is the unified boundary between interaction entry points and the harness internals. It creates tasks, starts task runs, queries status, records approvals, and exposes read-only run information for the WebUI.

CLI and WebUI call Core Service instead of calling Agent Runner directly.

### 5.3 Task Profiler

Task Profiler analyzes the user request and extracts:

- task type;
- keywords and symbols;
- likely modules;
- likely validation requirements;
- whether the request appears too large and should be split.

If the request appears to require cross-repository work, external deployment, or large architecture rewriting, Task Profiler marks the task as out of scope and asks the user to decompose it.

### 5.4 Repository Index and Context Engine

Repository Index scans the repository and records code structure, file paths, module summaries, dependency signals, test mappings, README/configuration conventions, and relevant historical memory.

Context Engine builds context packages from three prioritized sources:

1. Code structure context: file tree, module responsibilities, entry points, dependencies, and related tests.
2. Project convention context: coding style, test commands, safety boundaries, configuration rules, and repository norms.
3. Historical decision context: accepted design decisions, rejected alternatives, prior task summaries, and known pitfalls.

Context retrieval is code-driven first. The harness generates candidates using static structure, dependency signals, test mappings, keyword matching, and stored memory. LLM assistance may be used only to rank or explain candidates, not as the sole mechanism for discovering context.

Every ContextPackage records selected items, sources, scores, selection reasons, and an estimated context size. If the context exceeds budget, it is trimmed by priority: task-critical code and tests first, then conventions, then historical decisions.

### 5.5 LLM Provider and MockLLM

The harness defines a common `LLMClient` abstraction. The first real provider supports OpenAI-compatible Chat Completions with configurable `base_url`, `model`, and API key. The test provider is MockLLM, which returns a predefined sequence of structured actions.

LLMClient only sends messages and returns model output. It does not execute tools, judge safety, mutate memory, or decide task completion.

### 5.6 Agent Runner and Structured Action Protocol

Agent Runner is the core main loop. It controls task lifecycle, constructs model inputs, calls LLMClient, parses actions, sends actions through guardrails, dispatches tools, records results, runs verification, and decides whether to continue or stop.

The LLM must return a structured JSON action. Example:

```json
{
  "thought_summary": "Need to inspect parser tests before editing.",
  "action": "read_file",
  "args": {
    "path": "tests/test_parser.py"
  }
}
```

The first version supports these action types:

- `read_file`;
- `write_file`;
- `search`;
- `list_files`;
- `run_command`;
- `show_diff`;
- `record_memory`;
- `finish`.

Action arguments are validated with this schema:

| Action | Required args | Optional args | Types and notes |
| --- | --- | --- | --- |
| `read_file` | `path` | none | `path`: string repository-relative path |
| `write_file` | `path`, `content` | none | `path`: string repository-relative path; `content`: string full file content |
| `search` | `query` | `path` | `query`: string search pattern; `path`: optional repository-relative directory or file scope |
| `list_files` | none | `path` | `path`: optional repository-relative directory scope |
| `run_command` | `command` | none | `command`: string shell command to evaluate through guardrails before execution |
| `show_diff` | none | `path` | `path`: optional repository-relative file or directory scope |
| `record_memory` | `kind`, `content` | none | `kind`: one of the MemoryKind values in section 8.9; `content`: string memory text |
| `finish` | `summary` | none | `summary`: string user-facing completion or failure summary |

`thought_summary`, `action`, and `args` are required top-level fields. `thought_summary` and `action` must be strings, and `args` must be a JSON object.

Invalid JSON, unknown action types, missing fields, invalid argument types, and schema violations are not executed. They become structured feedback to the next loop.

### 5.7 Guardrail and Approval

Guardrail evaluates every action before execution. It returns one of:

- `allow`;
- `deny`;
- `require_approval`.

Guardrail checks include:

- canonical path must remain inside repository root;
- sensitive files such as `.env`, key files, and credential-like paths require denial or approval;
- deletion, overwrite of critical configuration, and broad file changes are high risk;
- unknown shell commands require approval;
- network, publish, install, and Git history modification commands are high risk;
- extremely dangerous commands are denied.

Actions requiring approval move the TaskRun to `waiting_approval`. CLI/WebUI can approve or reject the request. A rejected request is fed back as guardrail feedback.

### 5.8 Tool Dispatcher

Tool Dispatcher executes only actions that passed schema validation and guardrail checks. It provides controlled access to file reads, file writes, repository search, directory listing, shell commands, diff inspection, and memory recording.

All tool results are recorded with status, excerpts, exit codes, changed files, duration, and redaction metadata. Tool output is size-limited and secret-redacted before storage, display, or prompt inclusion.

### 5.9 Feedback Engine and Self-Repair

Feedback Engine runs configured or automatically discovered validation commands:

- tests;
- lint;
- type checks;
- build commands;
- action schema validation;
- guardrail feedback.

Validation command discovery is configuration-first. If not configured, the harness infers commands from files such as `package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml`, or common repository conventions.

The harness supports up to six repair rounds by default. Each round must be based on new objective feedback. If two consecutive rounds produce the same failure category and key location, the harness stops early and generates a failure report.

Successful completion requires a final validation pass or an explicitly configured success condition.

### 5.10 Memory

MemoryEntry stores long-term repository knowledge:

- module responsibilities;
- project conventions;
- historical decisions;
- rejected alternatives;
- recurring failure patterns;
- task summaries.

Memory entries include source task, confidence, timestamps, and supersession metadata. Conflicting memory is not silently overwritten; newer entries can supersede older ones while keeping an audit trail.

### 5.11 Reports and Export

The harness generates success and failure reports. A report includes:

- task request;
- selected context and reasons;
- action trace;
- changed files;
- validation commands and results;
- repair rounds;
- approval decisions;
- final status;
- stop reason if failed.

Reports can be exported as redacted Markdown or JSON for course evidence and debugging.

## 6. Domain and Mechanism Design

### 6.1 Coding Domain Tools

In the coding domain, useful actions include reading files, writing files, searching code, listing files, running verification commands, viewing diffs, recording memory, and completing or failing a task. These are implemented as harness tools behind a structured action protocol.

The LLM cannot call the operating system directly. It can only propose structured actions, and the harness decides whether and how to execute them.

### 6.2 Objective Feedback Signals

Objective feedback signals include:

- test failures;
- lint failures;
- type errors;
- build failures;
- invalid action schema;
- guardrail denial;
- approval rejection;
- command timeout.

Feedback Engine converts these signals into structured feedback containing source, category, summary, locations, and a redacted raw excerpt.

### 6.3 Dangerous Actions

Dangerous actions include:

- reading or writing outside repository root;
- accessing credential files;
- deleting files;
- overwriting critical configuration;
- running unknown shell commands;
- installing dependencies;
- publishing artifacts;
- modifying Git history;
- executing network-related commands.

Dangerous action handling is implemented in code. Prompt instructions alone do not count as safety implementation.

### 6.4 Memory as the Main Contribution

The main contribution is a structured context and memory mechanism. It turns repository knowledge into queryable, auditable context items and context packages. Context selection can be tested with fixture repositories and MockLLM.

The mechanism remains meaningful without a real LLM: candidate generation, scoring, source tracing, budget trimming, and context package creation are implemented by code. LLM assistance is optional and limited to ranking or explanation.

### 6.5 Self-Repair

Self-repair is controlled by Agent Runner and Feedback Engine. The LLM does not decide unbounded retries. The harness decides whether feedback is new, whether another round is allowed, and whether the run should stop.

## 7. System Architecture and Data Flow

The system is divided into these layers:

- interaction entry layer: CLI, WebUI, API;
- task orchestration layer: Core Service, Agent Runner, Task Profiler;
- context layer: Context Engine, Repository Index, Project Conventions, Decision Memory;
- model invocation layer: LLMClient;
- tool execution layer: Action Parser, Guardrail, Tool Dispatcher;
- validation feedback layer: Feedback Engine;
- storage and audit layer: SQLite, JSONL Audit Store.

Agent Runner is the core main loop.

CLI and WebUI submit tasks, query status, and handle approvals. Core Service creates tasks, starts runs, queries state, and records approval decisions. Task Profiler analyzes the user request. Context Engine builds the context package. LLMClient invokes either a real model or MockLLM. Action Parser validates JSON actions. Guardrail decides whether actions are allowed, denied, or require approval. Tool Dispatcher executes approved actions. Feedback Engine runs validation and returns structured feedback. Audit Store records the full run.

The complete task flow is:

1. User submits a task.
2. Core Service creates Task and TaskRun.
3. Task Profiler analyzes the request.
4. Context Engine builds a context package.
5. Agent Runner calls LLMClient.
6. LLM returns a structured action.
7. Action Parser validates format and schema.
8. Guardrail evaluates safety.
9. Tool Dispatcher executes allowed actions.
10. Feedback Engine runs verification when required.
11. Results are fed back to Agent Runner.
12. Agent Runner continues repair or ends the run.
13. The harness generates a completion or failure report.

The most important boundary is: the LLM proposes structured actions; Agent Runner controls lifecycle; Guardrail handles safety; Tool Dispatcher executes tools; Feedback Engine judges progress using real validation signals.

## 8. Data Model

### 8.1 Task

Represents a user feature request.

Fields:

- `id`;
- `title`;
- `description`;
- `repo_path`;
- `status`;
- `created_at`.

One Task may have multiple TaskRuns. Only one active TaskRun is expected by default.

### 8.2 TaskRun

Represents one execution attempt.

Fields:

- `id`;
- `task_id`;
- `status`;
- `max_repair_rounds`;
- `current_round`;
- `stop_reason`;
- `started_at`;
- `finished_at`.

Statuses include `pending`, `running`, `waiting_approval`, `succeeded`, `failed`, and `stopped`.

### 8.3 ContextItem

Represents a retrievable context unit.

Fields:

- `id`;
- `repo_path`;
- `kind`;
- `source_path`;
- `symbol`;
- `summary`;
- `content_ref`;
- `metadata`;
- `updated_at`.

Kinds include `code_structure`, `project_convention`, `decision_memory`, and `test_mapping`.

### 8.4 ContextPackage

Represents context selected for one round.

Fields:

- `id`;
- `task_run_id`;
- `round_index`;
- `items`;
- `token_estimate`;
- `selection_reason`;
- `created_at`.

`items` is an ordered list of references to `ContextItem` records, not inline item objects. Implementations may store this relationship with a join table. Each referenced item must preserve source and selection reason.

### 8.5 Action

Represents one LLM action.

Fields:

- `id`;
- `task_run_id`;
- `round_index`;
- `action_type`;
- `args_json`;
- `schema_status`;
- `guardrail_status`;
- `created_at`.

`thought_summary` is validated as part of the structured action protocol, but it is not stored on the `Action` record. It may appear in audit excerpts or feedback if validation fails.

Invalid or unknown actions are recorded but not executed.

### 8.6 ToolResult

Represents the result of executing a tool.

Fields:

- `id`;
- `action_id`;
- `status`;
- `stdout_excerpt`;
- `stderr_excerpt`;
- `exit_code`;
- `changed_files`;
- `duration_ms`;
- `created_at`.

`status` is one of:

- `success`;
- `error`;
- `timeout`.

Output must be redacted and truncated.

### 8.7 Feedback

Represents validation or mechanism feedback.

Fields:

- `id`;
- `task_run_id`;
- `round_index`;
- `source`;
- `category`;
- `summary`;
- `locations`;
- `raw_excerpt`;
- `created_at`.

Sources include `test`, `lint`, `typecheck`, `build`, `schema_validation`, and `guardrail`.

Categories include `assertion_failure`, `syntax_error`, `type_error`, `style_violation`, `unsafe_action`, `invalid_action`, and `unknown`.

### 8.8 ApprovalRequest

Represents a pending human approval.

Fields:

- `id`;
- `task_run_id`;
- `action_id`;
- `risk_level`;
- `reason`;
- `status`;
- `decided_by`;
- `decided_at`.

The action must not execute until approved.

### 8.9 MemoryEntry

Represents long-term repository memory.

Fields:

- `id`;
- `repo_path`;
- `kind`;
- `content`;
- `source_task_id`;
- `confidence`;
- `created_at`;
- `superseded_by`.

`kind` is one of:

- `module_responsibility`;
- `project_convention`;
- `historical_decision`;
- `rejected_alternative`;
- `failure_pattern`;
- `task_summary`.

History is preserved through supersession rather than deletion.

### 8.10 JSONL Audit Events

Audit events are append-only JSONL records such as:

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

## 9. Credential and Security Design

Credentials are never hardcoded, committed to Git, logged, stored in SQLite, stored in JSONL, shown in WebUI, or included in prompts.

The preferred credential mechanism is system keyring:

- Windows Credential Manager;
- macOS Keychain;
- Linux Secret Service.

The CLI provides:

- `auth set`: record or update credentials through hidden input;
- `auth status`: show provider and configured status without revealing secrets;
- `auth clear`: delete stored credentials.

`.env` is allowed only as a development fallback. It must be ignored by Git and documented as plaintext risk. Container demonstrations may use `.env` or secret mounts, but production local use should prefer keyring.

### Threat Model

#### Credential Leakage

Threat: API keys appear in Git, logs, SQLite, JSONL, prompts, WebUI, or command output.

Mitigation: keyring-first storage, `.env` fallback warning, output redaction, WebUI status-only display, and tests for redaction.

#### Out-of-Repository Access

Threat: LLM requests paths outside repository root.

Mitigation: canonical path resolution and repository-root checks before every file operation.

#### Dangerous Commands

Threat: LLM requests destructive, network, publish, install, or Git history commands.

Mitigation: command risk classification, allowlist for validation commands, approval for unknown or high-risk commands, denial for extreme commands, timeouts, and output limits.

#### Prompt Injection from Repository Files

Threat: repository content instructs the model to ignore rules, leak credentials, or execute unsafe actions.

Mitigation: repository content is treated as untrusted context; action schema, guardrails, and credential handling remain outside model control.

#### Memory Poisoning

Threat: incorrect memory affects future tasks.

Mitigation: memory entries include source, confidence, and supersession chain. Low-confidence memories are marked tentative.

#### Audit Data Leakage

Threat: local audit data contains sensitive paths, snippets, or secrets.

Mitigation: redacted exports, truncated output, `.harness/` ignored by Git, and documentation of local data boundaries.

## 10. Non-Functional Requirements

### 10.1 Testability

Core mechanisms must be testable with MockLLM and fixture repositories. Tests must not require a real LLM, API key, or network access.

### 10.2 Observability

Every run records context selection, actions, tool results, validation feedback, approval decisions, and final status. CLI/WebUI can inspect this state, and JSONL audit logs can be exported.

### 10.3 Reliability

The harness must not loop indefinitely. It supports a default maximum of six repair rounds and stops early on repeated unchanged failures.

### 10.4 Performance

The harness should reuse existing repository indexes when possible. File content, command output, context packages, and prompt inputs must have size limits.

### 10.5 Portability

The harness supports local Python execution and Docker execution on Windows, macOS, and Linux. Docker keyring limitations are documented.

### 10.6 Maintainability

Module boundaries must remain clear:

- LLMClient does not execute tools.
- Guardrail does not call LLM.
- Tool Dispatcher does not decide task lifecycle.
- Feedback Engine does not directly modify code.
- CLI/WebUI do not implement agent loop logic.

## 11. Technology Selection

The project uses:

- Python for core harness logic, filesystem operations, validation parsing, and repository indexing.
- Typer for CLI.
- FastAPI for WebUI/API.
- SQLite for structured local state.
- JSONL for append-only audit logs.
- pytest for deterministic unit and integration tests.
- keyring for credential storage.
- OpenAI-compatible Chat Completions as the first real LLM provider.
- MockLLM for offline tests and mechanism demonstrations.
- Docker as the primary distribution artifact.

Python is chosen because it is practical for CLI tools, filesystem work, subprocess management, testing, and lightweight web APIs.

## 12. Distribution and Deployment

Docker is the primary distribution format.

The repository will provide:

- `Dockerfile`;
- commands for `docker build`;
- commands for `docker run`;
- documentation for mounting a target repository;
- documentation for mounting `.harness/` data;
- documentation for configuring provider credentials;
- WebUI access instructions.

The image must not contain real API keys.

For public demonstration, the project may deploy a WebUI to a free hosting platform such as Render, Fly.io, or Railway. Public demos should use MockLLM and a sample repository to avoid exposing real credentials or local files.

CI must include a job named `unit-test`. The CI pipeline runs pytest, uses MockLLM, avoids real API keys, and builds the Docker image.

## 13. Testing Strategy

### 13.1 Unit Tests

Unit tests cover:

- Task Profiler;
- Context Engine;
- Action Parser;
- Guardrail;
- Tool Dispatcher;
- Feedback Engine;
- Memory Store;
- credential redaction.

### 13.2 MockLLM Main Loop Tests

MockLLM tests verify:

- legal actions execute;
- invalid actions become feedback;
- dangerous actions are blocked or sent to approval;
- failed validation changes later actions;
- runs stop after success, repeated failure, or repair limit.

### 13.3 Context Mechanism Tests

Fixture repositories verify that a feature request retrieves relevant modules, tests, conventions, and decisions. Context packages must include source, score, and selection reason.

### 13.4 Feedback Parsing Tests

Fixed outputs from pytest, lint, typecheck, build, schema validation, and guardrail denial verify feedback category, summary, locations, and raw excerpt truncation.

### 13.5 Security Tests

Tests cover path traversal, sensitive files, dangerous commands, command timeout, output truncation, and secret redaction.

### 13.6 End-to-End Mechanism Demonstration

The required mechanism demonstration uses MockLLM and a sample repository to show:

1. context package construction;
2. guardrail interception of a dangerous action;
3. a failed implementation followed by structured feedback and successful repair;
4. the primary context-memory mechanism in a deterministic behavior.

## 14. Acceptance Criteria

- A user can submit a single-repository feature task through CLI.
- The harness creates Task and TaskRun records.
- Task Profiler generates a task profile.
- Context Engine builds a context package from code structure, project conventions, and decision memory.
- CLI/WebUI can display selected context and reasons.
- LLM output must pass structured action schema validation.
- Invalid action output is not executed and becomes feedback.
- Every executable action passes Guardrail before Tool Dispatcher runs it.
- Dangerous actions are denied or require approval.
- Tool results are recorded and redacted.
- Verification commands can be configured or discovered.
- Feedback Engine structures validation failures.
- Agent Runner performs at most six repair rounds and stops early on repeated unchanged failures.
- Success reports and failure reports can be exported.
- MockLLM tests cover the harness core without network or API keys.
- API keys do not appear in Git, SQLite, JSONL, WebUI plaintext, logs, or prompts.
- CI contains a `unit-test` job that runs pytest.
- CI builds a Docker image.
- README explains install, run, key configuration, distribution, and known limits.

## 15. Risks and Open Questions

### 15.1 Context Retrieval Quality

Risk: selected context may be incomplete or irrelevant.

Mitigation: combine repository structure, test mapping, keyword matching, conventions, and memory; show selection reasons in WebUI; keep context mechanism testable with fixtures.

### 15.2 Refactoring Scope Creep

Risk: a medium-sized task may become a large architecture rewrite.

Mitigation: Task Profiler flags overly broad tasks and asks for decomposition.

### 15.3 Feedback Parser Coverage

Risk: validation output differs across languages and tools.

Mitigation: first support common pytest, lint, typecheck, build, and generic exit-code parsing; unknown formats fall back to redacted output excerpts.

### 15.4 Docker and Keyring Mismatch

Risk: containers cannot naturally use host keyrings.

Mitigation: document local keyring as preferred, and container `.env` or secret mount as a demo fallback with plaintext risk.

### 15.5 WebUI Scope Growth

Risk: WebUI work distracts from the harness core.

Mitigation: WebUI only supports task submission, status, context inspection, action trace, approval, and reports.

### 15.6 Real LLM Instability

Risk: real providers return invalid JSON or unexpected content.

Mitigation: strict Action Parser, structured invalid-action feedback, and MockLLM-based mechanism tests.

## 16. Course Requirement Mapping

This SPEC satisfies the AI4SE Coding Agent Harness requirements as follows:

- It defines a self-implemented harness core rather than relying on an existing high-level agent loop.
- It includes an LLM abstraction and MockLLM.
- It defines tool/action mechanisms, feedback signals, dangerous action handling, memory, configuration, and governance.
- It makes the main contribution explicit: structured context memory and context package construction.
- It requires deterministic tests for core mechanisms without a real LLM.
- It includes credential security, threat modeling, distribution, CI, and WebUI requirements.
- It defines Docker distribution and a WebUI/API surface for demonstration.

# Context-Aware Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, testable single-repository coding agent harness with explicit context retrieval, structured actions, guardrails, tool dispatch, feedback-driven repair, memory, CLI/API/WebUI observability, reports, Docker distribution, and CI.

**Architecture:** The harness is a Python package centered on `CoreService` and `AgentRunner`. Interaction layers call the service; the runner owns lifecycle; action parsing, guardrails, tool dispatch, feedback, context, memory, persistence, and reports are separate modules with deterministic tests and MockLLM coverage.

**Tech Stack:** Python, Typer, FastAPI, SQLite, JSONL, pytest, keyring, OpenAI-compatible Chat Completions, Docker, GitHub Actions.

## Global Constraints

- Scope is single-repository feature development only.
- Core mechanisms must run with `MockLLM` without network access or API keys.
- LLM output must be structured JSON actions and must never execute tools directly.
- Every executable action passes schema validation and guardrail checks before dispatch.
- Context retrieval is code-driven first; LLM assistance may rank or explain only.
- Credentials are never hardcoded, committed, logged, stored in SQLite, stored in JSONL, shown in WebUI plaintext, or included in prompts.
- Default repair limit is six rounds.
- Stop early after two consecutive rounds with the same failure category and key location.
- `.harness/` and `.env` are local data or development fallback and must be ignored by Git.
- CI must include a job named `unit-test` that runs pytest and avoids real API keys.
- CI must build the Docker image.

---

## File Structure

- `pyproject.toml`: package metadata, dependencies, pytest config, console script.
- `.gitignore`: excludes `.harness/`, `.env`, Python caches, build artifacts.
- `README.md`: install, run, credentials, Docker, WebUI, known limits, demo flow.
- `Dockerfile`: local container distribution for CLI/API/WebUI with no secrets baked in.
- `.github/workflows/ci.yml`: `unit-test` job and Docker image build.
- `harness/domain.py`: dataclasses, enums, typed records for tasks, runs, actions, context, feedback, approvals, memory, reports.
- `harness/storage.py`: SQLite schema, repositories for domain records, JSONL audit writer.
- `harness/profiler.py`: task profiling and out-of-scope detection.
- `harness/repo_index.py`: repository scanning, file summaries, dependency/test mapping signals.
- `harness/context_engine.py`: candidate generation, scoring, selection reasons, budget trimming.
- `harness/memory.py`: memory CRUD, conflict handling, supersession, query for context.
- `harness/llm.py`: `LLMClient`, `MockLLM`, OpenAI-compatible client, credential config types.
- `harness/actions.py`: structured action schema parser and validation feedback conversion.
- `harness/guardrails.py`: path, sensitive file, overwrite, command, network, install, publish, and git-history risk checks.
- `harness/tools.py`: controlled read, write, search, list, command, diff, and memory action execution.
- `harness/feedback.py`: validation discovery, command execution results to structured feedback, repeated failure detection.
- `harness/runner.py`: main agent loop, approval wait state, repair rounds, finish conditions.
- `harness/service.py`: task/run orchestration boundary used by CLI/API/WebUI.
- `harness/reports.py`: redacted Markdown and JSON report export.
- `harness/auth.py`: keyring-first credential operations plus `.env` fallback warning.
- `harness/cli.py`: Typer commands `init`, `run`, `status`, `auth`, `memory`, `export`.
- `harness/api.py`: FastAPI endpoints for tasks, runs, context, actions, feedback, approvals, reports.
- `harness/webui.py`: minimal HTML views served by FastAPI for observability and approval.
- `tests/fixtures/sample_repo/`: tiny repository used by deterministic context and runner tests.
- `tests/test_*.py`: focused unit and integration tests described by tasks below.

## Dependency And Parallelism Map

- Task 1 is the foundation for every task.
- Tasks 2, 3, 4, and 5 depend on Task 1 and can run in parallel.
- Task 6 depends on Tasks 1, 4, and 5.
- Task 7 depends on Tasks 1, 3, 4, and 5.
- Task 8 depends on Tasks 1, 2, 3, 4, 5, 6, and 7.
- Tasks 9 and 10 depend on Task 8 and can run in parallel.
- Task 11 depends on Tasks 1 and 2 and can run in parallel with Tasks 3 through 7.
- Task 12 depends on Tasks 8, 9, 10, and 11.
- Task 13 depends on all implementation tasks.

## Tasks

### Task 1: Project Skeleton, Domain Model, And Storage

**Status:** Complete.

**Parallel:** No. This is the base task.

**Depends On:** None.

**Goal:** Create the package, typed domain records, SQLite persistence, and append-only JSONL audit store used by all later tasks.

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `harness/__init__.py`
- Create: `harness/domain.py`
- Create: `harness/storage.py`
- Create: `tests/test_storage.py`

**Implementation Points:**
- Define enums for task/run/action/guardrail/approval/report statuses exactly matching `SPEC.md`.
- Use dataclasses for `Task`, `TaskRun`, `ContextItem`, `ContextPackage`, `Action`, `ToolResult`, `Feedback`, `ApprovalRequest`, and `MemoryEntry`.
- Initialize SQLite tables for every data model in section 8.
- Write audit events as one JSON object per line with event type and timestamp.
- Ensure invalid actions can be stored with `schema_status="invalid"` and no tool result.

**First Failing Test:**
- Write `tests/test_storage.py::test_storage_creates_task_run_and_audit_event`.
- It should create a temp `.harness` directory, initialize storage, create a task and run, append `task.created`, and assert both SQLite rows and the JSONL event exist.
- Initial expected failure: import error for `harness.storage` or missing `HarnessStorage`.

**Validation Commands:**
- `python -m pytest tests/test_storage.py::test_storage_creates_task_run_and_audit_event -q`
- `python -m pytest tests/test_storage.py -q`

### Task 2: Task Profiler And Validation Discovery Hints

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Classify user requests into task profiles with likely modules, symbols, validation requirements, and out-of-scope flags.

**Files:**
- Create: `harness/profiler.py`
- Create: `tests/test_profiler.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Add `TaskProfile` with task type, keywords, symbols, likely modules, validation requirements, `out_of_scope`, and `decomposition_reason`.
- Detect cross-repository, external deployment, and large architecture rewrite requests as out of scope.
- Infer validation requirements from request wording such as tests, lint, typecheck, build, Docker, CLI, API, WebUI, guardrail, memory, and report.
- Keep logic deterministic with keyword and path-like signal extraction.

**First Failing Test:**
- Write `tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope`.
- It should pass a request mentioning two repositories and production deployment, then assert `out_of_scope is True` and the decomposition reason names both cross-repository work and deployment.
- Initial expected failure: `TaskProfiler` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope -q`
- `python -m pytest tests/test_profiler.py -q`

### Task 3: Repository Index, Project Conventions, And Fixture Repo

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Scan a repository into structured context items for files, modules, tests, dependency signals, and project conventions.

**Files:**
- Create: `harness/repo_index.py`
- Create: `tests/fixtures/sample_repo/README.md`
- Create: `tests/fixtures/sample_repo/pyproject.toml`
- Create: `tests/fixtures/sample_repo/src/calculator.py`
- Create: `tests/fixtures/sample_repo/tests/test_calculator.py`
- Create: `tests/test_repo_index.py`

**Implementation Points:**
- Ignore `.git`, `.harness`, virtualenvs, caches, build outputs, and binary files.
- Produce `ContextItem` records for code structure, project conventions, and test mappings.
- Extract Python functions/classes with `ast` when parsing succeeds; fall back to file-level summaries when parsing fails.
- Map tests to source files by path naming and symbol keywords.

**First Failing Test:**
- Write `tests/test_repo_index.py::test_repository_index_maps_source_file_to_related_test`.
- It should index `tests/fixtures/sample_repo`, locate `src/calculator.py`, and assert a `test_mapping` item points to `tests/test_calculator.py` with a non-empty selection reason.
- Initial expected failure: `RepositoryIndex` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_repo_index.py::test_repository_index_maps_source_file_to_related_test -q`
- `python -m pytest tests/test_repo_index.py -q`

### Task 4: Decision Memory Store

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Implement long-term repository memory with confidence, source task, timestamps, conflict-safe supersession, and query support for context retrieval.

**Files:**
- Create: `harness/memory.py`
- Create: `tests/test_memory.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Store `MemoryEntry` rows in SQLite with `superseded_by` rather than destructive updates.
- Query by repository path, kind, and keyword matches against content.
- Mark conflicting new memory as superseding matching active entries when caller explicitly provides the old entry id.
- Preserve old entries for auditability.

**First Failing Test:**
- Write `tests/test_memory.py::test_memory_supersession_preserves_old_entry`.
- It should create an original decision, supersede it with a newer decision, and assert the old row still exists with `superseded_by` set.
- Initial expected failure: `MemoryStore` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_memory.py::test_memory_supersession_preserves_old_entry -q`
- `python -m pytest tests/test_memory.py -q`

### Task 5: Action Parser And Schema Feedback

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Parse LLM JSON actions, validate supported action types and argument shapes, and convert invalid output into structured feedback without execution.

**Files:**
- Create: `harness/actions.py`
- Create: `tests/test_actions.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Support `read_file`, `write_file`, `search`, `list_files`, `run_command`, `show_diff`, `record_memory`, and `finish`.
- Require `thought_summary`, `action`, and `args`.
- Validate per-action required fields and primitive types.
- Return an invalid `Action` plus `Feedback(source="schema_validation", category="invalid_action")` for invalid JSON, unknown actions, missing fields, and wrong types.

**First Failing Test:**
- Write `tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable`.
- It should parse a JSON payload with action `delete_file`, assert schema status is invalid, and assert feedback category is `invalid_action`.
- Initial expected failure: `ActionParser` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable -q`
- `python -m pytest tests/test_actions.py -q`

### Task 6: Guardrails And Approval Classification

**Parallel:** No.

**Depends On:** Tasks 1, 4, 5.

**Goal:** Evaluate every parsed action for repository boundary safety, sensitive file access, risky writes, dangerous commands, and approval requirements.

**Files:**
- Create: `harness/guardrails.py`
- Create: `tests/test_guardrails.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Canonicalize all paths and deny access outside repository root.
- Deny or require approval for `.env`, key files, credential-like paths, deletion, critical config overwrites, network, publish, install, and git history commands.
- Allow known validation commands such as `python -m pytest`, `pytest`, `ruff check`, `mypy`, and `python -m build` when configured or discovered.
- Return `allow`, `deny`, or `require_approval` with risk level and reason.

**First Failing Test:**
- Write `tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch`.
- It should build a `read_file` action for `../secret.txt`, evaluate it against a temp repo root, and assert status is `deny` with a reason mentioning repository root.
- Initial expected failure: `Guardrail` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch -q`
- `python -m pytest tests/test_guardrails.py -q`

### Task 7: Tool Dispatcher With Redaction And Limits

**Parallel:** No.

**Depends On:** Tasks 1, 3, 4, 5.

**Goal:** Execute only approved actions through controlled file, search, command, diff, and memory tools while recording redacted, truncated tool results.

**Files:**
- Create: `harness/tools.py`
- Create: `tests/test_tools.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Implement `read_file`, `write_file`, `search`, `list_files`, `run_command`, `show_diff`, and `record_memory`.
- Require caller to pass an already allowed action and repository root.
- Truncate stdout/stderr/file excerpts to configured limits.
- Redact API keys, bearer tokens, obvious secrets, and `.env`-style credential values from all stored output.
- Track changed files and command duration.

**First Failing Test:**
- Write `tests/test_tools.py::test_run_command_result_redacts_secret_like_output`.
- It should run a command that prints `OPENAI_API_KEY=sk-test-secret`, then assert the stored stdout excerpt does not contain `sk-test-secret`.
- Initial expected failure: `ToolDispatcher` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_tools.py::test_run_command_result_redacts_secret_like_output -q`
- `python -m pytest tests/test_tools.py -q`

### Task 8: Context Engine With Scoring, Reasons, And Budget Trimming

**Parallel:** No.

**Depends On:** Tasks 1, 2, 3, 4, 5, 6, 7.

**Goal:** Build auditable context packages from repository index, project conventions, test mappings, and decision memory.

**Files:**
- Create: `harness/context_engine.py`
- Create: `tests/test_context_engine.py`
- Modify: `harness/domain.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Generate candidates using static structure, dependency signals, test mappings, keyword matching, and stored memory.
- Score candidates deterministically and preserve score, source, and selection reason.
- Trim over-budget packages by priority: task-critical code and tests, conventions, historical decisions.
- Store `ContextPackage` records by task run and round.

**First Failing Test:**
- Write `tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons`.
- It should index the sample repo, add one decision memory entry, request a calculator feature, and assert the package includes at least one item from each required source with selection reasons.
- Initial expected failure: `ContextEngine` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons -q`
- `python -m pytest tests/test_context_engine.py -q`

### Task 9: Feedback Engine And Validation Loop Signals

**Parallel:** Yes, after Task 8.

**Depends On:** Task 8.

**Goal:** Discover validation commands, run configured validations, parse failures into structured feedback, and detect repeated unchanged failures.

**Files:**
- Create: `harness/feedback.py`
- Create: `tests/test_feedback.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Prefer configured validation commands and infer fallback commands from `pyproject.toml`, `package.json`, `Cargo.toml`, `pom.xml`, and common conventions.
- Parse pytest, lint, typecheck, build, schema validation, guardrail denial, approval rejection, timeout, and generic exit-code failures.
- Store category, summary, locations, and redacted raw excerpt.
- Compare consecutive failures by category and key location for early stop decisions.

**First Failing Test:**
- Write `tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence`.
- It should pass two feedback objects with category `assertion_failure` and the same file/test location, then assert the engine recommends early stop.
- Initial expected failure: `FeedbackEngine` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence -q`
- `python -m pytest tests/test_feedback.py -q`

### Task 10: LLM Clients And Agent Runner Main Loop

**Parallel:** Yes, after Task 8.

**Depends On:** Task 8.

**Goal:** Implement the model abstraction, MockLLM, OpenAI-compatible client shell, and bounded Agent Runner lifecycle.

**Files:**
- Create: `harness/llm.py`
- Create: `harness/runner.py`
- Create: `tests/test_runner.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- `LLMClient` only sends messages and returns model output.
- `MockLLM` returns a predefined sequence of structured action strings.
- OpenAI-compatible client accepts `base_url`, `model`, and API key but is not used by offline tests.
- `AgentRunner` creates model inputs from task, profile, context, prior actions, and feedback.
- Runner parses actions, applies guardrails, dispatches tools, runs validation, records audit events, respects approval wait state, and stops at success, repeated failure, or six repair rounds.

**First Failing Test:**
- Write `tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution`.
- It should configure MockLLM to return invalid JSON, run one loop, and assert schema feedback exists and no tool result exists.
- Initial expected failure: `AgentRunner` or `MockLLM` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution -q`
- `python -m pytest tests/test_runner.py -q`

### Task 11: Credentials, Reports, And Export Redaction

**Parallel:** Yes, after Tasks 1 and 2.

**Depends On:** Tasks 1, 2.

**Goal:** Add keyring-first credential management and redacted success/failure report export in Markdown and JSON.

**Files:**
- Create: `harness/auth.py`
- Create: `harness/reports.py`
- Create: `tests/test_auth_reports.py`
- Modify: `.gitignore`

**Implementation Points:**
- Implement `auth set/status/clear` operations behind a service class that can use a fake keyring in tests.
- Report `.env` fallback as plaintext development risk without printing secret values.
- Export task request, selected context, action trace, changed files, validation commands/results, repair rounds, approval decisions, final status, and stop reason.
- Redact credentials and secret-like strings from Markdown and JSON exports.

**First Failing Test:**
- Write `tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace`.
- It should build a run report containing `sk-test-secret` in a tool excerpt and assert exported Markdown and JSON do not contain the secret.
- Initial expected failure: `ReportExporter` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace -q`
- `python -m pytest tests/test_auth_reports.py -q`

### Task 12: Core Service, CLI, API, And WebUI Observability

**Parallel:** No.

**Depends On:** Tasks 8, 9, 10, 11.

**Goal:** Expose the harness through a unified service boundary, Typer CLI, FastAPI endpoints, and minimal WebUI for status, context, actions, feedback, approvals, and reports.

**Files:**
- Create: `harness/service.py`
- Create: `harness/cli.py`
- Create: `harness/api.py`
- Create: `harness/webui.py`
- Create: `tests/test_service_cli_api.py`
- Modify: `pyproject.toml`

**Implementation Points:**
- `CoreService` creates tasks and runs, starts runs, reads status, records approvals, manages memory, and exports reports.
- CLI commands include `init`, `run`, `status`, `auth set/status/clear`, `memory`, and `export`.
- API endpoints submit tasks, query runs, read context/action/feedback traces, approve/reject pending approvals, and export reports.
- WebUI renders read-only observability pages plus approval decision forms; it does not implement agent logic.

**First Failing Test:**
- Write `tests/test_service_cli_api.py::test_cli_run_with_mock_llm_creates_task_run_and_context_trace`.
- It should invoke the Typer CLI against a temp sample repo with MockLLM and assert the command exits successfully and storage contains a task run plus a context package.
- Initial expected failure: CLI entry point does not exist.

**Validation Commands:**
- `python -m pytest tests/test_service_cli_api.py::test_cli_run_with_mock_llm_creates_task_run_and_context_trace -q`
- `python -m pytest tests/test_service_cli_api.py -q`

### Task 13: Docker, CI, README, And End-To-End Mechanism Demo

**Parallel:** No.

**Depends On:** All prior tasks.

**Goal:** Provide distribution, automated verification, documentation, and a deterministic MockLLM demonstration covering the required course mechanism evidence.

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Create: `tests/test_e2e_demo.py`
- Modify: `pyproject.toml`

**Implementation Points:**
- Docker image installs the package and runs CLI/API/WebUI without embedding secrets.
- CI job named `unit-test` runs pytest with MockLLM and no real API keys.
- CI builds the Docker image after tests.
- README documents install, `harness init`, `harness run`, credential configuration, `.env` fallback risk, WebUI access, Docker build/run, report export, known limits, and demo flow.
- End-to-end test shows context package construction, guardrail interception of a dangerous action, failed implementation feedback, successful repair, and memory inclusion.

**First Failing Test:**
- Write `tests/test_e2e_demo.py::test_mockllm_demo_context_guardrail_feedback_repair_and_memory`.
- It should run a deterministic MockLLM sequence against the sample repo and assert all four required demonstration events appear in storage or audit logs.
- Initial expected failure: demo workflow cannot be imported or executed.

**Validation Commands:**
- `python -m pytest tests/test_e2e_demo.py::test_mockllm_demo_context_guardrail_feedback_repair_and_memory -q`
- `python -m pytest -q`
- `docker build -t context-aware-harness:test .`

## Final Verification Checklist

- `python -m pytest -q`
- `docker build -t context-aware-harness:test .`
- Confirm `.github/workflows/ci.yml` contains a job named `unit-test`.
- Confirm `README.md` documents install, run, key configuration, Docker distribution, WebUI/API, report export, MockLLM demo, and known limits.
- Confirm no tests require a real LLM, API key, or network access.
- Confirm `.gitignore` excludes `.harness/` and `.env`.

## Self-Review Against SPEC.md

- CLI, API, WebUI, and Core Service are covered by Task 12.
- Task Profiler is covered by Task 2.
- Repository Index, Context Engine, project conventions, and decision memory are covered by Tasks 3, 4, and 8.
- LLMClient and MockLLM are covered by Task 10.
- Agent Runner and structured action protocol are covered by Tasks 5 and 10.
- Guardrail and approval are covered by Tasks 6, 10, and 12.
- Tool Dispatcher is covered by Task 7.
- Feedback Engine and self-repair are covered by Tasks 9 and 10.
- Reports and export are covered by Task 11.
- Credential and security design are covered by Tasks 6, 7, 11, and 13.
- Data model and audit events are covered by Task 1.
- Testing strategy, MockLLM demonstration, Docker, CI, and README are covered by Task 13.

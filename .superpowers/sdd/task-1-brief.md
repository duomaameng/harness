### Task 1: Project Skeleton, Domain Model, And Storage

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



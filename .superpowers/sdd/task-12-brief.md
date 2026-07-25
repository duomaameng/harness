# Task 12: Core Service, CLI, API, And WebUI Observability

Source: `PLAN.md`

## Scope Adjustment For This Run

The user explicitly requested completing the non-`webui.py` portions only. Do not create or modify `harness/webui.py` in this task run. Implement the service, CLI, API, tests, and package metadata needed outside WebUI.

## Plan Text

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

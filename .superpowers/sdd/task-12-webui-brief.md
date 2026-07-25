# Task 12 WebUI Completion Brief

Source: `PLAN.md` Task 12 and the user's resumed instruction.

## Scope

Complete the remaining WebUI portion of Task 12 in the existing isolated worktree.

The non-WebUI Task 12 pieces already exist in:
- `harness/service.py`
- `harness/cli.py`
- `harness/api.py`
- `tests/test_service_cli_api.py`

Do not revert or overwrite existing uncommitted fixes in those files. Work with the current state.

## Plan Requirements

Task 12 goal: expose the harness through a unified service boundary, Typer CLI, FastAPI endpoints, and minimal WebUI for status, context, actions, feedback, approvals, and reports.

Files relevant to this resumed scope:
- Create: `harness/webui.py`
- Modify: `tests/test_service_cli_api.py` as needed for WebUI coverage.
- Modify `harness/api.py` only if needed to mount/include WebUI routes.

Implementation point:
- WebUI renders read-only observability pages plus approval decision forms; it does not implement agent logic.

## Expected Behavior

Implement minimal HTML views served by FastAPI:
- A run detail page showing task/run status.
- Sections for selected context, action trace, feedback, pending approvals, and report.
- Approval forms for approve/reject decisions.
- WebUI delegates all data and mutations to `CoreService`; it must not duplicate runner logic.
- Credentials/secrets must not be shown in plaintext.

## TDD Requirement

First write a failing test in `tests/test_service_cli_api.py` proving `harness.webui` is missing or WebUI routes are missing.

Suggested first failing test:
- `test_webui_run_page_renders_observability_and_approval_forms`
- Build a repo, create a `CoreService` with `MockLLM` that triggers an approval, create the FastAPI app, include/mount WebUI routes, call the route endpoint directly like existing API tests do, and assert the returned HTML contains run status, context, actions, feedback, approvals, report, and approve/reject forms.

Validation command:
- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_service_cli_api.py -q`

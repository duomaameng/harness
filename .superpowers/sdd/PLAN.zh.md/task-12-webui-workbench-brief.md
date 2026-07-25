# Task 12 WebUI Workbench Brief

Implement the remaining WebUI portion of Task 12 using TDD.

Requirements from SPEC and PLAN:
- WebUI is served by FastAPI.
- WebUI uses CoreService as the interaction boundary.
- WebUI can submit tasks, query run status, show selected context, action history, feedback, pending approvals, and final report.
- WebUI supports approval and rejection decision forms.
- WebUI must not implement agent loop logic.
- Credentials must not be shown in plaintext in WebUI.
- This slice focuses on the real workbench entry from the design prototype in `design/webui-prototype.html`: root `/` should be a workbench, not a 404.

Scope:
- Modify `harness/service.py`, `harness/webui.py`, `tests/test_service_cli_api.py`, and task logs/docs only if needed.
- Do not modify unrelated files.
- Preserve existing API routes and run detail behavior.
- Commit the completed task.

TDD:
- First add failing tests that prove `/` renders an integrated workbench and that the workbench create-and-run endpoint creates a task run and returns a detail URL.
- Show the failing test output.
- Implement the minimum code.
- Refactor and rerun the focused tests.


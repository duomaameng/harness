# Task 1 brief: 存储与服务层任务管理

Read `docs/superpowers/plans/2026-08-07-task-management.md` only if this brief conflicts with an interface below; this brief is the complete requirement for your task.

Modify `harness/storage.py`, `harness/service.py`, and `tests/test_service_cli_api.py`.

Implement `HarnessStorage.rename_task(task_id: str, title: str) -> dict | None` and `HarnessStorage.delete_task(task_id: str) -> bool`. The delete must use one SQLite transaction, collecting run ids and deleting in this order: approval requests; tool results for actions in those runs; actions; feedback; context-package items for packages in those runs; context packages; runs; task. It must never delete repository files.

Implement `CoreService.rename_task(task_id: str, title: str) -> dict` and `CoreService.delete_task(task_id: str) -> None`. Both must reject missing tasks and reject a task having any task run with `status` `running` or `waiting_approval`, raising `ValueError` with an active-task indication.

Use TDD: first write and run focused failing tests, then write only enough production code to pass. Test successful inactive rename; block active rename; cascade deletion including a stopped run, action, and tool result; block active delete. Commit only task-scoped files after tests pass.

Write a full report to `.superpowers/sdd/2026-08-07-task-management/task-1-report.md` containing: changed files, tests written, exact test command/output, commit hash, and self-review. Return only status, commit hash, one-line test summary, and concerns.

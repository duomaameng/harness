# Task 2 brief: WebUI routes and automatic titles

Implement only Task 2 in `C:\Users\duoma\java\harness\.worktrees\codex-task-management`.

Modify `harness/webui_routes.py` and `tests/test_service_cli_api.py`. The prior task already provides `CoreService.rename_task(task_id, title)` and `CoreService.delete_task(task_id)`.

Replace client-provided required title behavior for both `POST /ui/tasks` and `POST /ui/tasks/run`: derive a title from description by collapsing whitespace (`" ".join(description.split())`), then taking its first 32 characters; use the exact fallback `未命名任务` when description is blank. Keep the original description content stored as description.

Add `POST /ui/tasks/{task_id}/rename`, accepting JSON `{ "title": "..." }`, requiring nonblank normalized title, returning updated task. Add `POST /ui/tasks/{task_id}/delete`, deleting then `303` redirecting to `/`. Map service `ValueError` for active tasks to HTTP 400; unknown task should be HTTP 404.

TDD: add focused tests before production code; test automatic 32-char derived title, blank fallback, create-and-run derived title, successful inactive rename/delete, and active-task rejection. Update old WebUI tests that pass `title` so they use descriptions and assert generated titles. Run focused tests before and after implementation if an interpreter becomes available; do not install dependencies. Commit task-only source/tests if possible.

Write full report to `.superpowers/sdd/2026-08-07-task-management/task-2-report.md`: changed files, exact test commands/output, commit hash, self-review. Return concise status/commit/test/concerns only.

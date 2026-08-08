# Task 3 brief: 工作台任务菜单与表单

Implement only Task 3 in `C:\Users\duoma\java\harness\.worktrees\codex-task-management`.

Modify `harness/webui.py` and `tests/test_service_cli_api.py`. Task 2 provides routes `/ui/tasks/{task_id}/rename` and `/ui/tasks/{task_id}/delete`.

Remove the `<input name="title">` label from `#task-form`. In `_render_sidebar_tasks`, show each nonactive task as a row with status/title left and a `task-management-menu` right-side ellipsis button. It must be hidden when the task has any `running` or `waiting_approval` run; runs list may include multiple runs per task, so determine activity across all task runs. Reuse repository menu markup/style and add one rename dialog and one delete confirmation dialog. Delete text must say Harness records are permanently removed but repository files are not deleted. Dialog action buttons use `data-task-action`; JS must set `/ui/tasks/{id}/{action}`, prefill rename title, close the menu, open dialog; forms submit as JSON and reload page on success.

Add HTML tests: inactive menu visible, active menu hidden, one each dialogs, title input absent, task menu CSS aligns more control right. TDD when possible; do not install Python. Report to task-3-report.md with changes, tests, commit, blockers.

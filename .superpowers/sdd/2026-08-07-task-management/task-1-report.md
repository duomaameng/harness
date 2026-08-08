# Task 1 report: inactive task rename and deletion

## Changed files

- `harness/storage.py`
  - Added `rename_task`, returning the updated task or `None`.
  - Added transaction-scoped `delete_task`, which collects task run, action, and context package ids and deletes dependent rows in the required order before deleting the task. It uses SQLite only and never touches repository files.
- `harness/service.py`
  - Added `CoreService.rename_task` and `CoreService.delete_task`.
  - Added the shared inactive-task guard. Missing tasks raise `ValueError`; runs with `running` or `waiting_approval` status raise a `ValueError` whose message includes `active`.
- `tests/test_service_cli_api.py`
  - Added focused behavioral tests for inactive rename, active rename rejection, stopped-run cascade deletion (including an action and tool result), repository-file preservation, and active delete rejection.

## TDD record

The focused tests were written before the production methods. The initial test execution could not begin because no Python interpreter is available in this worktree environment, so a normal red/green execution could not be observed.

## Exact test command and output

Command:

```powershell
python -m pytest tests/test_service_cli_api.py -k "rename_task or delete_task" -q
```

Output:

```text
python : 无法将“python”项识别为 cmdlet、函数、脚本文件或可运行程序的名称。请检查名称的拼写，如果包括路径，请确保路径正确，然后再试一次。
所在位置 行:2 字符: 1
+ python -m pytest tests/test_service_cli_api.py -k "rename_task or del ...
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (python:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
```

`py` and `python3` are also unavailable, and this worktree has no `.venv` directory. Dependencies were not installed.

## Commit hash

`e4221fae120a4ad11514d9fb2c550d8677b2bf70`

The controller created this commit after the implementation review. Tests remained
environment-blocked; the commit does not indicate a passing test run.

## Self-review

- Confirmed the storage delete collects run ids, action ids, and package ids within one explicitly begun SQLite transaction.
- Confirmed deletion order is approval requests, tool results, actions, feedback, context-package items, context packages, runs, then task.
- Confirmed deletion uses SQLite statements only; the focused deletion test protects a repository file as a regression check.
- Confirmed the service guard checks all task runs for exactly `running` and `waiting_approval` and runs before either mutation.
- Ran `git diff --check`; it produced no whitespace errors.

## Concern

The environment has no runnable Python interpreter, so focused and full test suites remain unverified.

## Fix round 1/5

Updated only this report. Covered files: `harness/storage.py`, `harness/service.py`,
and `tests/test_service_cli_api.py`. Test status remains blocked by the missing Python
interpreter described above.

## Fix round 2/5: atomic activity checks

### Changed files

- `harness/storage.py`
  - Added `rename_task_if_inactive` and `delete_task_if_inactive`. Each starts
    `BEGIN IMMEDIATE`, checks task existence and active run statuses, and performs
    its mutation before committing.
  - Made `create_task_run` acquire `BEGIN IMMEDIATE` before inserting, so a new
    run cannot be inserted between an inactive-task check and its protected
    rename/delete mutation.
- `harness/service.py`
  - Delegates rename and delete directly to the atomic storage operations; it no
    longer makes a separate pre-mutation activity check.
- `tests/test_service_cli_api.py`
  - Added a deterministic storage-level active-run regression test for the atomic
    rename operation.
  - Expanded the deletion test to cover approval requests, feedback, context
    packages, and context-package items, while confirming context items remain.

### TDD and verification

The new storage-level regression test was run before the new storage API existed
and failed with the expected `AttributeError` for
`HarnessStorage.rename_task_if_inactive`.

Focused command:

```powershell
& 'C:\Users\duoma\java\harness\.venv\Scripts\python.exe' -m pytest tests/test_service_cli_api.py -k "rename_task or delete_task" -q --basetemp .pytest-task-management
```

Focused output: `5 passed, 60 deselected in 1.17s`.

Full-suite command:

```powershell
& 'C:\Users\duoma\java\harness\.venv\Scripts\python.exe' -m pytest -q --tb=no --disable-warnings --basetemp .pytest-task-management
```

The full suite collected 225 tests and failed in existing credential/keyring
coverage (`tests/test_auth_reports.py`) before completion of a clean run. The
task-management focused coverage passed. The full-suite failure is retained as
an environment/baseline concern rather than attributed to this change.

Committed production and test changes: `1cff7bb` (`fix: serialize inactive task mutations`).

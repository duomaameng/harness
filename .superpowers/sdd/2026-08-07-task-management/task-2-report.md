# Task 2 Report: WebUI routes and automatic titles

## Changed files

- `harness/webui_routes.py`
  - Derives task titles from normalized descriptions, truncating at 32 characters and using the required unnamed-task fallback.
  - Adds WebUI task rename and delete routes with inactive-task protection, unknown-task 404 responses, and delete redirects.
- `tests/test_service_cli_api.py`
  - Updates existing WebUI creation tests to use descriptions and assert derived titles.
  - Adds focused coverage for title derivation, blank fallback, create-and-run title derivation, inactive rename/delete, active rejection, unknown task responses, and blank rename validation.

## Test commands and output

Focused test command run before implementation:

```powershell
python -m pytest tests/test_service_cli_api.py -q -k 'webui_task_creation_derives or webui_task_creation_uses or webui_create_and_run_endpoint or webui_task_rename_and_delete or webui_task_endpoints_return_bad_request'
```

Output:

```text
python : 无法将“python”项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

The same focused test command was run after implementation and produced the same output. `Get-Command py, python3` and a check for `.venv`/`venv` found no available interpreter. No dependencies were installed.

Static verification run:

```powershell
git diff --check
```

Result: exit code 0 (only Git CRLF conversion warnings were emitted).

## Commit

`10d176616ea60bf4596c3a51218ef31815ad5a5e` — `feat: add webui task management routes`

## Self-review

- Creation preserves the original description while deriving the title from collapsed whitespace.
- Rename strips the supplied title and rejects blank values with HTTP 400.
- Rename/delete pre-check unknown task IDs for HTTP 404 and convert service active-task `ValueError`s to HTTP 400.
- Delete redirects to `/` with HTTP 303 after a successful delete.
- Automated tests could not execute because this worktree has no Python interpreter available on PATH or in a local virtual environment.

## Round 1 follow-up

- Strengthened `test_webui_create_and_run_endpoint_returns_detail_url` with a description containing leading/trailing and newline whitespace that normalizes to more than 32 characters.
- The test now asserts the exact derived 32-character title (`Create through WebUI form with e`) and that the stored description equals the original unmodified input.
- Follow-up test command attempted:

```powershell
python -m pytest tests/test_service_cli_api.py -q -k 'webui_create_and_run_endpoint_returns_detail_url'
```

- Output: `python` is not recognized as a command, so this focused test remains blocked; no dependencies or interpreter were installed.

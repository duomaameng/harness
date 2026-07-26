# Task 3: Verify WebUI and Markdown download integration

Read this first: it is the complete requirement for this task.

Modify only `tests/test_service_cli_api.py`. Do not add a second WebUI report formatter or change routes/endpoints.

Add a focused integration test using a completed task with a `finish` action. Exercise both `GET /runs/{run_id}/report` and `GET /ui/runs/{run_id}`. Assert each consumer includes the readable report headings `运行概览` and `最终结论`, and that no JSON code fence occurs before `审计原始数据`. The report endpoint returns `{"content": markdown}`; use that content for assertions.

Run only:

`& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k "webui_run_detail or report" -q -p no:cacheprovider`

This integration assertion is expected to pass because Task 2 implemented the already-tested export contract. Commit with `test: cover readable web reports`.

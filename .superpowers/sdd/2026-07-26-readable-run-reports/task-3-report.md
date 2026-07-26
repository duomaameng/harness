# Task 3 Report: WebUI and Markdown Download Integration

## Change

Added `test_report_endpoint_and_webui_render_readable_completed_run_report` to `tests/test_service_cli_api.py`.

The test creates a completed run with a `finish` action, then exercises:

- `GET /runs/{run_id}/report`, using its `content` Markdown value
- `GET /ui/runs/{run_id}`

For both consumer outputs it verifies the readable report headings `杩愯姒傝` and `鏈€缁堢粨璁篳`, and ensures no `json` code fence appears before `瀹¤鍘熷鏁版嵁`.

## Verification

Executed exactly:

```powershell
& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k "webui_run_detail or report" -q -p no:cacheprovider
```

Result: 8 passed, 1 failed, 23 deselected.

The new integration test passed. The failure was the existing `test_report_payload_includes_top_level_changed_files`, which constructed `CoreService(repo)` and attempted an external LLM request; the environment rejected its network socket with `WinError 10013`.

## Scope

No production code, routes, endpoints, or WebUI report formatter were modified.

## Commit

`91815be` — `test: cover readable web reports`

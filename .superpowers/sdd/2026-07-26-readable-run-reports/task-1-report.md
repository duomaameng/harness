# Task 1 Report: Specify readable report behavior

## Scope

Added `test_report_export_renders_readable_run_sections` to
`tests/test_auth_reports.py`. No production files were changed.

The test uses a literal run report with one context package and item,
`read_file` and `finish` actions, one tool result, changed files, feedback,
approval, final status, and stop reason. It specifies the required readable
Markdown sections, selected-context table, action text and path, placement of
the raw-data audit section, absence of JSON code fences before that section,
and JSON export round-tripping unchanged.

## Focused red-phase test

Command run:

```powershell
& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider
```

Result: failed as expected (1 failed). The assertion for `## 杩愯姒傝`
failed because the current Markdown starts with English headings such as
`## Task Request` and renders report sections as JSON code blocks.

## Commit

The test-only change is committed with message `test: specify readable run report`
as `75b6408`.

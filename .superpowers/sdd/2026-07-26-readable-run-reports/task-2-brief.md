# Task 2: Implement semantic Markdown rendering

Read this first: it is the complete requirement for this task.

Modify `harness/reports.py` only as required to make the existing `test_report_export_renders_readable_run_sections` pass. Preserve `to_json()`, `export_json`, and all `_redact()` behavior. Do not alter storage, runner behavior, or `CoreService.report_payload()`.

After calling `_redact()` once, produce Chinese semantic Markdown sections: `运行概览`, `最终结论`, `已选上下文`, `动作轨迹`, `验证与反馈`, `审批记录`, `变更文件`, and `审计原始数据`.

Render primary content as headings, tables, and lists, not JSON code blocks. For context render a table with headers `文件`, `类型`, `选择原因`, and `评分`; omit internal IDs, absolute repository paths, and timestamps. For actions parse JSON-valued arguments with `json.loads`; if parsing fails, show the already-redacted text. Render `read_file` as `读取文件：` followed by its path. Extract `finish.args.summary` and use it as `最终结论`. Render feedback and approvals as readable state/reason/result lists. Render changed files as a list. At the end, render a redacted raw-data `<details>` section headed `审计原始数据`; JSON code is permitted only there.

Use focused formatter helpers. Run only:

`& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`

The test must pass. Commit the production code and test updates, if any, with `feat: render readable run reports`.

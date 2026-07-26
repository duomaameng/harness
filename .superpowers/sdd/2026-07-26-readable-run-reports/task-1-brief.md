# Task 1: Specify readable report behavior

Read this first: it is the complete requirement for this task.

Modify only `tests/test_auth_reports.py`. Do not modify production code.

Add `test_report_export_renders_readable_run_sections` with a literal report containing one context package/item, `read_file` and `finish` actions, one tool result, changed files, feedback, approval, status, and stop reason. Assert that Markdown includes `## 运行概览`, `## 最终结论`, `项目依赖已总结。`, `## 已选上下文`, `| 文件 | 类型 | 选择原因 | 评分 |`, `pyproject.toml`, `## 动作轨迹`, and `读取文件：` plus the path. Assert `## 审计原始数据` exists and no JSON code fence occurs before that heading. Assert `json.loads(ReportExporter(report).to_json()) == report`.

Run only this test using:

`& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`

The test must fail because current output uses English headings and JSON code blocks. Commit the test with message `test: specify readable run report`.

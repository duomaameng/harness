# Web report rendering

Status: blocked on local test execution.

Implemented a safe semantic Markdown renderer for the WebUI report panel:

- Markdown headings render as HTML headings.
- Markdown tables render as HTML tables.
- The ReportExporter audit `<details>` block remains collapsed.
- Fenced JSON remains escaped code content rather than becoming executable HTML.

TDD test added:

`test_webui_run_detail_renders_report_markdown_as_semantic_html`

Focused red/green test command attempted:

`python -m pytest tests/test_service_cli_api.py -k semantic_html`

Both `py` and `python` are unavailable on PATH in this worktree (`CommandNotFoundException`), and no Python launcher or virtual environment was found. Therefore the required red failure and green pass could not be observed locally. No non-focused tests were run.

Commit status: blocked. `git add harness/webui.py tests/test_service_cli_api.py` could not create `C:/Users/duoma/java/harness/.git/worktrees/readable-run-reports/index.lock` because access was denied.

Controller-provided focused test result:

`& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k "readable_completed_run_report" -q -p no:cacheprovider`

Green: passed — 1 passed, 32 deselected in 1.25s.

Red: not observed. The original red attempt could not run because the default `py` and `python` launchers were unavailable. The controller-provided command was supplied after the implementation and selected the pre-existing `readable_completed_run_report` test rather than the newly added `semantic_html` regression test, so it does not independently prove that regression's red-to-green cycle.

Strict TDD correction using the controller-provided Python runtime:

`& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k "semantic_html" -q -p no:cacheprovider`

Red: after temporarily restoring the old escaped `<pre>{escape(report)}</pre>` implementation and removing the new helpers, the focused test failed as expected at `assert "<h1>Harness Run Report</h1>" in html` (1 failed, 32 deselected in 1.38s).

Green: after restoring the minimal semantic renderer, the same focused test passed (1 passed, 32 deselected in 1.11s).

Review follow-up:

- Table parsing now verifies that the second Markdown row is a delimiter row before beginning a table, and skips that delimiter rather than rendering it as body content.
- The semantic HTML regression now verifies unordered-list rendering, escaped report content, and absence of a delimiter cell in the table body.
- Focused test: `semantic_html` passed — 1 passed, 32 deselected in 1.14s.

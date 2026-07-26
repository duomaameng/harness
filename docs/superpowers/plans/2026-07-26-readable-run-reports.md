# Readable Run Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render completed harness runs as readable Chinese Markdown while retaining unchanged, redacted JSON export for machine use and audit.

**Architecture:** `ReportExporter.to_markdown()` will transform the existing report payload into semantic Markdown after the current redaction pass. The WebUI already embeds `CoreService.export_report(..., fmt="markdown")`, so it will consume that same output without a second formatter.

**Tech Stack:** Python 3.12, standard library `json`, pytest, FastAPI.

## Global Constraints

- Keep `ReportExporter.to_json()` output structure unchanged and redacted.
- Do not change run storage, runner behavior, or `CoreService.report_payload()` fields.
- Use Chinese user-facing headings and labels in Markdown.
- Keep all secret-redaction behavior intact.

---

### Task 1: Specify readable report behavior

**Files:**
- Modify: `tests/test_auth_reports.py:1-245`

**Interfaces:**
- Consumes: `ReportExporter(report).to_markdown()` and `.to_json()`.
- Produces: Regression coverage for semantic Markdown sections and unchanged JSON data.

- [ ] **Step 1: Write the failing test**

Add `test_report_export_renders_readable_run_sections` with a literal report containing one context package/item, `read_file` and `finish` actions, one tool result, changed files, feedback, approval, status, and stop reason. Assert `运行概览`, `最终结论`, `项目依赖已总结。`, `已选上下文`, `| 文件 | 类型 | 选择原因 | 评分 |`, `pyproject.toml`, `动作轨迹`, and `读取文件：\`pyproject.toml\`` occur in Markdown. Assert `## 审计原始数据` occurs and no `\`\`\`json` occurs before it. Assert `json.loads(ReportExporter(report).to_json()) == report`.

- [ ] **Step 2: Run the failing test**

Run `& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`.

Expected: FAIL because current output uses English headings and JSON code blocks.

- [ ] **Step 3: Commit the failing test**

Run `git add tests/test_auth_reports.py` then `git commit -m "test: specify readable run report"`.

### Task 2: Implement semantic Markdown rendering

**Files:**
- Modify: `harness/reports.py:10-79`
- Test: `tests/test_auth_reports.py:1-245`

**Interfaces:**
- Consumes: Existing keys `task_request`, `selected_context`, `action_trace`, `tool_results`, `changed_files`, `validation`, `repair_rounds`, `approval_decisions`, `final_status`, and `stop_reason`.
- Produces: `ReportExporter.to_markdown() -> str` with `运行概览`, `最终结论`, `已选上下文`, `动作轨迹`, `验证与反馈`, `审批记录`, `变更文件`, and `审计原始数据` sections.

- [ ] **Step 1: Add focused formatter helpers**

Implement `_render_overview(report)`, `_render_context(packages)`, `_render_actions(actions, results)`, `_render_feedback(feedback)`, `_render_approvals(approvals)`, and `_render_audit_data(report)`. Each receives already-redacted data and returns Markdown lines. Parse JSON-valued action arguments only with `json.loads`; on parse failure display the redacted text. Use `finish.args.summary` as the final conclusion and `read_file.args.path` as `读取文件`.

- [ ] **Step 2: Replace generic key iteration**

In `to_markdown()`, call `_redact()` once and pass its result through the helpers. Render primary sections with headings, tables, and lists rather than JSON code fences. Keep a redacted raw-data `<details>` section at the end for diagnostics.

- [ ] **Step 3: Preserve JSON export**

Leave `to_json()`, `export_json`, and `_redact()` behavior unchanged.

- [ ] **Step 4: Run focused tests**

Run `& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py::test_report_export_renders_readable_run_sections -q -p no:cacheprovider`, then `& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_auth_reports.py -q -p no:cacheprovider`.

Expected: PASS, including secret-redaction tests.

- [ ] **Step 5: Commit the implementation**

Run `git add harness/reports.py tests/test_auth_reports.py` then `git commit -m "feat: render readable run reports"`.

### Task 3: Verify WebUI and Markdown download integration

**Files:**
- Modify: `tests/test_service_cli_api.py:545-620`

**Interfaces:**
- Consumes: `GET /runs/{run_id}/report` returning `{"content": markdown}` and `GET /ui/runs/{run_id}` embedding `core.export_report(..., fmt="markdown")`.
- Produces: Integration coverage that both consumers show readable sections rather than raw report JSON.

- [ ] **Step 1: Add integration assertions**

In an existing run-detail test with a `finish` action and in the report endpoint test, assert `运行概览` and `最终结论` occur, and no `\`\`\`json` occurs before `审计原始数据`.

- [ ] **Step 2: Run WebUI report tests**

Run `& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k "webui_run_detail or report" -q -p no:cacheprovider`, then `& 'C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_service_cli_api.py -k webui -q -p no:cacheprovider`.

Expected: PASS. Do not add a separate WebUI formatter or change endpoints.

- [ ] **Step 3: Verify diff and commit**

Run `git diff --check`, `git status --short`, `git add tests/test_service_cli_api.py`, then `git commit -m "test: cover readable web reports"`.

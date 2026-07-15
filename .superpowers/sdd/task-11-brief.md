### Task 11: Credentials, Reports, And Export Redaction

**Parallel:** Yes, after Tasks 1 and 2.

**Depends On:** Tasks 1, 2.

**Goal:** Add keyring-first credential management and redacted success/failure report export in Markdown and JSON.

**Files:**
- Create: `harness/auth.py`
- Create: `harness/reports.py`
- Create: `tests/test_auth_reports.py`
- Modify: `.gitignore`

**Implementation Points:**
- Implement `auth set/status/clear` operations behind a service class that can use a fake keyring in tests.
- Report `.env` fallback as plaintext development risk without printing secret values.
- Export task request, selected context, action trace, changed files, validation commands/results, repair rounds, approval decisions, final status, and stop reason.
- Redact credentials and secret-like strings from Markdown and JSON exports.

**First Failing Test:**
- Write `tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace`.
- It should build a run report containing `sk-test-secret` in a tool excerpt and assert exported Markdown and JSON do not contain the secret.
- Initial expected failure: `ReportExporter` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace -q`
- `python -m pytest tests/test_auth_reports.py -q`


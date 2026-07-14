### Task 7: Tool Dispatcher With Redaction And Limits

**Parallel:** No.

**Depends On:** Tasks 1, 3, 4, 5.

**Goal:** Execute only approved actions through controlled file, search, command, diff, and memory tools while recording redacted, truncated tool results.

**Files:**
- Create: `harness/tools.py`
- Create: `tests/test_tools.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Implement `read_file`, `write_file`, `search`, `list_files`, `run_command`, `show_diff`, and `record_memory`.
- Require caller to pass an already allowed action and repository root.
- Truncate stdout/stderr/file excerpts to configured limits.
- Redact API keys, bearer tokens, obvious secrets, and `.env`-style credential values from all stored output.
- Track changed files and command duration.

**First Failing Test:**
- Write `tests/test_tools.py::test_run_command_result_redacts_secret_like_output`.
- It should run a command that prints `OPENAI_API_KEY=sk-test-secret`, then assert the stored stdout excerpt does not contain `sk-test-secret`.
- Initial expected failure: `ToolDispatcher` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_tools.py::test_run_command_result_redacts_secret_like_output -q`
- `python -m pytest tests/test_tools.py -q`

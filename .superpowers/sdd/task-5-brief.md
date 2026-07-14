# Task 5: Action Parser And Schema Feedback

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Parse LLM JSON actions, validate supported action types and argument shapes, and convert invalid output into structured feedback without execution.

**Files:**
- Create: `harness/actions.py`
- Create: `tests/test_actions.py`
- Modify: `harness/domain.py`

**Implementation Points:**
- Support `read_file`, `write_file`, `search`, `list_files`, `run_command`, `show_diff`, `record_memory`, and `finish`.
- Require `thought_summary`, `action`, and `args`.
- Validate per-action required fields and primitive types.
- Return an invalid `Action` plus `Feedback(source="schema_validation", category="invalid_action")` for invalid JSON, unknown actions, missing fields, and wrong types.

**First Failing Test:**
- Write `tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable`.
- It should parse a JSON payload with action `delete_file`, assert schema status is invalid, and assert feedback category is `invalid_action`.
- Initial expected failure: `ActionParser` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable -q`
- `python -m pytest tests/test_actions.py -q`

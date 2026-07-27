# Task 1 Review — `45cffd9`

## Verdict

**Findings — fix required before approval.**

## Scope reviewed

- `harness/repository_registry.py`
- `tests/test_service_cli_api.py`
- `task-1-report.md`

The focused verification command reported in the task report was rerun:

```text
C:\\Users\\duoma\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe -m pytest tests/test_service_cli_api.py -q -k repository_registry
1 passed, 33 deselected
```

No full test suite was run. No files outside the Task 1 review artifact were examined for correctness.

## Findings

### P2 — Valid but malformed registry files bypass the promised diagnostic validation

`_read()` only verifies that the decoded top-level JSON is a mapping with a `repositories` list (`harness/repository_registry.py:80-81`).  It does not validate `current_repository_id` or the records inside `repositories`, even though later operations assume both shapes.  For example, a syntactically valid registry file containing `{"repositories": []}` makes `current()` raise an uncontextualized `KeyError: 'current_repository_id'` at line 46 rather than the documented/intentional `ValueError` identifying an invalid registry file.  Similarly, an entry missing `path`, `id`, or `name` can leak a `KeyError` from duplicate detection or lookup, and `list()` can return records that violate the required `{id, path, name}` shape.

This is a realistic corruption/truncation mode: JSON may remain valid while mandatory fields are lost.  It fails the requirement that corrupt registry data produce a diagnosable exception and weakens the record-shape guarantee.

**Required fix:** validate the complete persisted schema in `_read()` before returning it: require `current_repository_id` to be `null` or a string, and every repository to be a mapping whose `id`, `path`, and `name` are strings (and preferably ensure the current id refers to a registered record when non-null).  Raise a `ValueError` including the registry path for any violation.  Add regression coverage for a valid-JSON file missing `current_repository_id` and for a malformed repository record.

## Requirements assessment

- Registration normalizes paths with `expanduser().resolve()`, rejects non-directories, and rejects exact normalized-path duplicates.
- Register/select/current behavior, rename trimming and non-empty validation, persistence, and current-repository fallback after removal follow the stated Task 1 behavior.
- Removal changes only the JSON state; it does not delete repository directories or their contents.
- Writes use a same-directory temporary file followed by `os.replace`, satisfying the required atomic-replacement approach.
- Invalid JSON syntax is converted to a path-bearing `ValueError` and is not overwritten.
- The added focused test covers the required end-to-end registration, selection, rename, persistence, deletion, and source-directory-preservation flow.  It passes, but it does not cover malformed-yet-valid persisted data, which is needed for the finding above.

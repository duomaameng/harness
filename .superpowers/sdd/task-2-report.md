# Task 2 Report: Task Profiler And Validation Discovery Hints

## What changed

- Added `TaskProfile` to `harness/domain.py`.
- Added deterministic `TaskProfiler` in `harness/profiler.py`.
- Added Task 2 tests in `tests/test_profiler.py`.

## TDD evidence

RED command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope -q`

Relevant RED output:

`ModuleNotFoundError: No module named 'harness.profiler'`

This was expected because the first test imported `TaskProfiler` before `harness/profiler.py` existed.

GREEN command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope -q`

Relevant GREEN output:

`1 passed in 0.03s`

## Refactor and validation

Task 2 suite:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Result: `5 passed in 0.04s`

Full suite:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q`

Result: `47 passed in 0.87s`

Diff check:

`git diff --check`

Result: exit code 0; only Git line-ending warning for `harness/domain.py`.

## Files changed

- `harness/domain.py`
- `harness/profiler.py`
- `tests/test_profiler.py`
- `.superpowers/sdd/task-2-report.md`

## Self-review

- Spec coverage: `TaskProfile` contains the requested fields, profiler detects cross-repository work, deployment, large architecture rewrite, validation requirements, symbols, likely modules, keywords, and task type.
- Scope: implementation is deterministic and keyword/path-signal based, with no network or LLM dependency.
- Quality: tests exercise the plan's first failing case plus validation ordering, extraction, architecture rewrite, and in-scope feature behavior.

## Concerns

- The implementation intentionally uses lightweight heuristics. Future tasks can extend vocabularies if project-specific wording appears.

## Review fix report

Quality review found three Important issues: repeated single-repository mentions
were treated as cross-repository, validation regexes could match inside unrelated
words, and scoped architecture redesign could be misclassified as a large rewrite.

Fix RED command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Relevant RED output before the fix:

- `test_profiler_keeps_repeated_mentions_of_one_repository_in_scope` failed because `out_of_scope` was `True`.
- `test_profiler_does_not_match_validation_words_inside_other_words` failed because validation requirements included false positives.
- `test_profiler_keeps_scoped_architecture_redesign_in_scope` failed because `out_of_scope` was `True`.

Fix GREEN validation:

- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q` -> `8 passed in 0.04s`
- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q` -> `50 passed in 0.88s`
- `git diff --check` -> exit code 0; only Git line-ending warnings for changed files.

Fix summary:

- Cross-repository detection now requires explicit multi-repository phrasing or
  two distinct named repository signals.
- Validation patterns now use word boundaries for token-like alternatives.
- Large architecture rewrite detection now requires a large/whole-system scope
  modifier.

## Second review fix report

Re-review found two remaining Important false positives and one Minor regex
consistency issue.

Second fix RED command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Relevant RED output before the fix:

- `test_profiler_keeps_local_deployment_request_in_scope` failed because a local Docker preview deploy was marked `external deployment`.
- `test_profiler_keeps_non_architecture_rewrite_in_scope` failed because rewriting the entire README was marked `large architecture rewrite`.

Second fix GREEN validation:

- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q` -> `10 passed in 0.06s`
- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q` -> `52 passed in 0.86s`
- `git diff --check` -> exit code 0; only Git line-ending warnings for changed files.

Second fix summary:

- External deployment now requires deployment wording plus an external target
  such as production, staging, remote, cloud, or prod.
- Large architecture rewrite now requires both an architecture/system-design
  signal and a large-scope modifier.
- Refactor task-type rewrite/reorganize alternatives now use word boundaries.

## Third review fix report

Final re-review found one remaining Important false negative: plural repository
lists such as `payments and billing repositories` were not recognized.

Third fix RED command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Relevant RED output before the fix:

- `test_profiler_marks_plural_repository_list_out_of_scope` failed because `out_of_scope` was `False`.

Third fix GREEN validation:

- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q` -> `11 passed in 0.05s`
- `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q` -> `53 passed in 0.87s`
- `git diff --check` -> exit code 0; only Git line-ending warnings for changed files.

Third fix summary:

- `_cross_repository()` now recognizes two distinct names in plural repository
  lists such as `payments and billing repositories`.

## Code quality review fixes

### TDD evidence

RED command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Relevant RED output:

`3 failed, 5 passed in 0.19s`

The failures covered repeated mentions of one repository, validation-word false positives, and scoped architecture redesign.

GREEN command:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_profiler.py -q`

Relevant GREEN output:

`8 passed in 0.05s`

### Final verification

Full suite:

`C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -q` -> `50 passed in 0.77s`

Diff check:

`git diff --check` -> exit code 0; only LF/CRLF conversion warnings.

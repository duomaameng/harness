### Task 8: Context Engine With Scoring, Reasons, And Budget Trimming

**Parallel:** No.

**Depends On:** Tasks 1, 2, 3, 4, 5, 6, 7.

**Goal:** Build auditable context packages from repository index, project conventions, test mappings, and decision memory.

**Files:**
- Create: `harness/context_engine.py`
- Create: `tests/test_context_engine.py`
- Modify: `harness/domain.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Generate candidates using static structure, dependency signals, test mappings, keyword matching, and stored memory.
- Score candidates deterministically and preserve score, source, and selection reason.
- Trim over-budget packages by priority: task-critical code and tests, conventions, historical decisions.
- Store `ContextPackage` records by task run and round.

**First Failing Test:**
- Write `tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons`.
- It should index the sample repo, add one decision memory entry, request a calculator feature, and assert the package includes at least one item from each required source with selection reasons.
- Initial expected failure: `ContextEngine` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons -q`
- `python -m pytest tests/test_context_engine.py -q`

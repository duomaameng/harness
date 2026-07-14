### Task 4: Decision Memory Store

**Parallel:** Yes, after Task 1.

**Depends On:** Task 1.

**Goal:** Implement long-term repository memory with confidence, source task, timestamps, conflict-safe supersession, and query support for context retrieval.

**Files:**
- Create: `harness/memory.py`
- Create: `tests/test_memory.py`
- Modify: `harness/storage.py`

**Implementation Points:**
- Store `MemoryEntry` rows in SQLite with `superseded_by` rather than destructive updates.
- Query by repository path, kind, and keyword matches against content.
- Mark conflicting new memory as superseding matching active entries when caller explicitly provides the old entry id.
- Preserve old entries for auditability.

**First Failing Test:**
- Write `tests/test_memory.py::test_memory_supersession_preserves_old_entry`.
- It should create an original decision, supersede it with a newer decision, and assert the old row still exists with `superseded_by` set.
- Initial expected failure: `MemoryStore` does not exist.

**Validation Commands:**
- `python -m pytest tests/test_memory.py::test_memory_supersession_preserves_old_entry -q`
- `python -m pytest tests/test_memory.py -q`

